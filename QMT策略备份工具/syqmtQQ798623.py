r"""
syqmtQQ798623 - 固定文件自动备份工具
=====================================

功能概述
--------
从 file_list.txt 读取需要备份的文件路径(每行一个)，每次运行时把每个源文件
**只读复制**(不修改、不移动、不删除) 到脚本目录下::

    backups/yyyyMMdd_HHmmss/

目录命名规则: 当次运行的本地时间戳。
文件命名规则: 在原文件完整名之后追加 ``.yyyyMMdd_HHmmss``(后缀之后)。例如::

    wave_detector.py                       -> wave_detector.py.20260915_160455
    a0stock_pool.csv                       -> a0stock_pool.csv.20260915_160455
    报告.xlsx                              -> 报告.xlsx.20260915_160455
    备份.tar.gz                            -> 备份.tar.gz.20260915_160455

适用场景
--------
- QMT 策略文件 / 关键配置 / DB / 报告，每次发版或调参前先留一份
- 任意"我希望文件被改之前能自动留下一份"的场合

设计要点(产品化)
----------------
1. **配置驱动**: file_list.txt 控制备份范围，新增/删除文件无需改代码
2. **只读源文件**: 全部使用 ``shutil.copy2`` + 显式以只读模式读取，源文件不变
3. **失败隔离**: 单个文件读取/复制失败不会中断后续，错误会写进 report.json
4. **可校验**: 复制后做 SHA1 校验，不一致会标记失败并保留两边文件
5. **可重入**: 同一次任务的输出目录是确定的(运行前生成时间戳)，重复运行会
   在该目录下追加 ``_retryN`` 后缀，避免覆盖历史快照
6. **可观测**: 每次运行产出 ``backups/<run_id>/report.json``(机器可读) + ``backups/backup.log``(人可读)
7. **零依赖**: 仅使用 Python 标准库

命令行用法
----------
::

    python syqmtQQ798623.py                  # 默认读 file_list.txt 并执行备份
    python syqmtQQ798623.py --dry-run        # 只打印计划，不实际复制
    python syqmtQQ798623.py --list           # 解析并打印当前配置里的有效路径
    python syqmtQQ798623.py --check          # 只校验文件是否可读，不复制
    python syqmtQQ798623.py --file my.txt    # 使用其它列表文件

文件: file_list.txt 写法
-----------------------
::

    # 以 # 开头的行视为注释
    # 空行会被忽略
    # 一行一个绝对路径；带不带引号都可以
    D:\国金证券QMT交易端\python\wave_detector.py
    "D:\国金证券QMT交易端\python\CKLBUY.py"
    # 相对路径相对脚本所在目录解析(不建议，便于一眼看清来源)
    # 文件不存在时会被记录到 report.json，但不影响其它文件
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Iterable

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

APP_NAME = "syqmtQQ798623"
APP_VERSION = "1.0.0"

_BANNER = (
    "=" * 56 + "\n"
    f"  {APP_NAME} v{APP_VERSION} - 固定文件自动备份工具\n"
    "  Powered By 宁尚拙\n"
    "  QQ: 798623\n"
    "  GitHub: https://github.com/NobodySniper\n"
    + "=" * 56
)

# 获取脚本所在目录(兼容 PyInstaller 冻结)
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _default_list_path() -> str:
    """默认列表文件: 直接使用脚本同目录下的 file_list.txt。"""
    return os.path.join(APP_DIR, "file_list.txt")


def _backup_root() -> str:
    return os.path.join(APP_DIR, "backups")


def _log_path() -> str:
    return os.path.join(_backup_root(), "backup.log")


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class BackupItem:
    """单次备份任务单元。"""

    source: str                 # 用户在 file_list.txt 里写的原始字符串
    abs_source: str             # 解析后的绝对路径(规范化)
    display_name: str           # 用于显示的源文件名
    exists: bool = False
    size: int = 0
    sha1: str = ""
    note: str = ""              # 解析阶段的提示，例如"路径不存在"

    # 复制结果
    copied: bool = False
    dest: str = ""              # 实际写入的目标路径
    copied_size: int = 0
    copied_sha1: str = ""
    copied_sha1_short: str = ""
    error: str = ""
    encoded: bool = False       # 是否疑似 QMT 未开本地编辑导出的乱码文件
    warning: str = ""           # 需要重点提示给用户的提示语


@dataclass
class BackupReport:
    """一次运行的完整报告。"""

    app: str = APP_NAME
    version: str = APP_VERSION
    started_at: str = ""                # ISO 格式
    finished_at: str = ""
    run_id: str = ""                    # yyyyMMdd_HHmmss
    out_dir: str = ""
    list_file: str = ""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    encoded_count: int = 0
    items: list = field(default_factory=list)        # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1].strip()
    return s


def parse_file_list(list_path: str) -> list[BackupItem]:
    """
    读取列表文件，每行解析成一个 BackupItem。

    支持:
    - 空行
    - 以 # 开头的注释行
    - 带 / 不带成对引号
    - 绝对路径
    - 相对脚本目录的相对路径
    """
    items: list[BackupItem] = []
    seen_keys: set[str] = set()

    if not os.path.exists(list_path):
        # 列表文件缺失不算致命错误，交由上层统一报告
        return items

    with open(list_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    for lineno, raw in enumerate(raw_lines, start=1):
        line = _strip_quotes(raw)
        if not line or line.startswith("#"):
            continue
        # 兼容行内注释: # 之后的全部当作注释(但允许盘符里的 #)
        # 简单策略: 仅处理首个未被引号包裹的 #
        if "#" in line and not (line.startswith('"') or line.startswith("'")):
            hash_idx = line.find("#")
            # 避免误杀 URL / 路径里的 # (此处业务里基本没 URL)
            line = line[:hash_idx].strip()
            if not line:
                continue

        line = _strip_quotes(line)
        if not line:
            continue

        # 路径规范化
        expanded = os.path.expandvars(os.path.expanduser(line))
        if not os.path.isabs(expanded):
            expanded = os.path.abspath(os.path.join(APP_DIR, expanded))
        abs_source = os.path.normpath(expanded)

        # 去重
        key = abs_source.lower()
        if key in seen_keys:
            note = f"重复条目(行 {lineno})，已忽略"
        else:
            seen_keys.add(key)
            note = ""

        item = BackupItem(
            source=line,
            abs_source=abs_source,
            display_name=os.path.basename(abs_source),
            note=note,
        )

        if os.path.exists(abs_source):
            item.exists = True
            try:
                item.size = os.path.getsize(abs_source)
            except OSError as e:
                item.note = f"无法访问文件大小: {e}"
        else:
            item.exists = False
            if not item.note:
                item.note = "文件不存在"

        items.append(item)

    return items


# ---------------------------------------------------------------------------
# 校验与复制
# ---------------------------------------------------------------------------


def _sha1_of(path: str, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _make_dest_path(out_dir: str, source_path: str, run_id: str) -> str:
    """在 out_dir 下生成目标路径，时间戳追加到完整文件名末尾。

    例如:
        wave_detector.py              -> wave_detector.py.20260915_160455
        a0stock_pool.csv              -> a0stock_pool.csv.20260915_160455
        备份.tar.gz                   -> 备份.tar.gz.20260915_160455
        无后缀文件                    -> 文件名.20260915_160455
    """
    parent, name = os.path.split(source_path)
    new_name = f"{name}.{run_id}"
    return os.path.join(out_dir, new_name)


def _ensure_unique(dest: str) -> str:
    """如果目标已存在(重入场景)，追加 _retryN。"""
    if not os.path.exists(dest):
        return dest
    # 形如 foo.py.20260915_160455 -> foo.py.20260915_160455_retry1
    for i in range(1, 1000):
        cand = f"{dest}_retry{i}"
        if not os.path.exists(cand):
            return cand
    return f"{dest}_{datetime.now().strftime('%H%M%S%f')}"


_BASE64_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)


def _looks_encoded(path: str) -> bool:
    """判断文件是否为 QMT 未开启本地编辑时导出的加密/乱码文件。

    特征: 文件头部存在超长单行，且该行几乎完全由 base64 字符组成。
    正常源码有换行、注释(#)、中文字符、关键字等，不会同时满足这两个条件。
    """
    try:
        with open(path, "rb") as f:
            head = f.read(8192)
    except OSError:
        return False
    if not head:
        return False

    lines = head.split(b"\n")
    longest = max(lines, key=len)
    # 太短的不算"一串乱码"
    if len(longest) < 300:
        return False

    stripped = longest.strip()
    if not stripped:
        return False

    base64_count = 0
    for byte in stripped:
        if chr(byte) in _BASE64_CHARS:
            base64_count += 1
    return (base64_count / len(stripped)) > 0.95


def perform_backup(items: list[BackupItem], out_dir: str, run_id: str,
                   dry_run: bool = False) -> None:
    """逐项执行复制，结果写回 items。"""
    os.makedirs(out_dir, exist_ok=True)

    for item in items:
        if not item.exists:
            item.error = item.note or "文件不存在，跳过"
            continue

        # 检测疑似乱码文件的源文件已在 main 预扫描完成，此处直接复制
        try:
            dest = _make_dest_path(out_dir, item.abs_source, run_id)
            if not dry_run:
                dest = _ensure_unique(dest)
                # shutil.copy2 以源只读模式打开；源文件不会被修改
                shutil.copy2(item.abs_source, dest)

                item.copied_size = os.path.getsize(dest)
                item.copied_sha1 = _sha1_of(dest)
                item.copied_sha1_short = item.copied_sha1  # 兼容旧字段
                item.copied = True
                item.dest = dest

                if item.copied_size != item.size:
                    item.error = (
                        f"大小不一致: 源={item.size} 目标={item.copied_size}"
                    )
                    item.copied = False
                elif item.copied_sha1 != item.sha1:
                    item.error = "SHA1 校验失败"
                    item.copied = False
                else:
                    item.error = ""
            else:
                # dry-run 时也计算 sha1 给报告预览用
                item.sha1 = _sha1_of(item.abs_source)
                item.dest = dest
                item.copied = False  # 标记未真正复制
        except Exception as e:  # noqa: BLE001 - 我们要把所有失败都收口
            item.error = f"{type(e).__name__}: {e}"
            item.copied = False


# ---------------------------------------------------------------------------
# 日志与报告
# ---------------------------------------------------------------------------


def _log(msg: str, also_print: bool = True) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    if also_print:
        print(line)
    try:
        os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        # 日志写不进也无所谓，不能再抛
        pass


def write_report(out_dir: str, report: BackupReport) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_items(items: Iterable[BackupItem]) -> None:
    for idx, it in enumerate(items, 1):
        flag = "OK " if it.exists else "MISS"
        extra = f" ({it.size} bytes)" if it.exists else ""
        print(f"  [{idx:02d}] {flag} {it.abs_source}{extra}")
        if it.note:
            print(f"        note: {it.note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="按 file_list.txt 复制指定文件到 backups/时间戳/ 目录",
    )
    parser.add_argument("--file", dest="list_file", default=_default_list_path(),
                        help="指定列表文件路径(默认 file_list.txt)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只解析与计划，不实际复制")
    parser.add_argument("--list", action="store_true",
                        help="只打印列表内容，不执行备份")
    parser.add_argument("--check", action="store_true",
                        help="只校验文件是否存在/可读，不复制")
    args = parser.parse_args(argv)

    print(_BANNER)

    list_path = os.path.abspath(args.list_file)

    # ---- 0. 列表文件本身存在性 ----
    if not os.path.exists(list_path):
        _log(f"列表文件不存在: {list_path}")
        # 仍然生成一份空的样例，避免下次用户还得手动建
        sample = os.path.join(APP_DIR, "file_list.txt")
        if not os.path.exists(sample):
            try:
                with open(sample, "w", encoding="utf-8") as f:
                    f.write(
                        "# syqmtQQ798623 备份列表\n"
                        "# 每行一个文件路径，# 开头为注释，支持 \"...\" 包裹\n"
                        "# 示例:\n"
                        '# "D:\\国金证券QMT交易端\\python\\wave_detector.py"\n'
                    )
                _log(f"已生成示例列表: {sample}")
            except OSError:
                pass
        return 2

    items = parse_file_list(list_path)
    _log(f"解析列表 {list_path} 完成，共 {len(items)} 项")

    if args.list or args.check or args.dry_run:
        _print_items(items)
        if args.list:
            return 0

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 预扫描: 检测未开启本地编辑的乱码文件，并据此决定输出目录名
    any_encoded = False
    for it in items:
        if it.exists and _looks_encoded(it.abs_source):
            it.encoded = True
            it.warning = "注意策略未开启本地编辑，请开启本地编辑后再备份"
            any_encoded = True

    folder_suffix = "_未开启本地编辑" if any_encoded else ""
    out_dir = os.path.join(_backup_root(), run_id + folder_suffix)

    # SHA1 预计算(供 dry-run / report 用)
    for it in items:
        if it.exists and not it.note.startswith("无法访问文件大小"):
            try:
                it.sha1 = _sha1_of(it.abs_source)
            except Exception as e:  # noqa: BLE001
                it.note = (it.note + " | " if it.note else "") + f"sha1 失败: {e}"

    if args.check:
        ok = sum(1 for it in items if it.exists and not it.error)
        bad = len(items) - ok
        _log(f"check 完成: ok={ok} bad={bad}")
        return 0 if bad == 0 else 1

    report = BackupReport(
        started_at=datetime.now().isoformat(timespec="seconds"),
        run_id=run_id,
        out_dir=out_dir,
        list_file=list_path,
        total=len(items),
        items=[asdict(it) for it in items],
    )

    perform_backup(items, out_dir, run_id, dry_run=args.dry_run)

    # 汇总
    success = sum(1 for it in items if it.copied)
    failed = sum(1 for it in items if (it.exists and not it.copied))
    skipped = sum(1 for it in items if not it.exists)
    encoded_count = sum(1 for it in items if it.encoded)

    report.finished_at = datetime.now().isoformat(timespec="seconds")
    report.success = success
    report.failed = failed
    report.skipped = skipped
    report.encoded_count = encoded_count
    report.items = [asdict(it) for it in items]

    if not args.dry_run:
        write_report(out_dir, report)

    mode = "DRY-RUN" if args.dry_run else "BACKUP"
    _log(f"[{mode}] run_id={run_id} out={out_dir} "
         f"total={report.total} ok={success} failed={failed} skipped={skipped}")

    # 乱码文件重点告警
    for it in items:
        if it.warning:
            _log(f"  !! [{it.display_name}] {it.warning}")

    # 失败明细(只列错误)
    for it in items:
        if it.error:
            _log(f"  ! {it.abs_source} -> {it.error}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
