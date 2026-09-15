# syqmtQQ798623

> 固定文件自动备份工具 · 专为 QMT 策略开发者打造的零依赖快照脚本

---

## 目录

- [中文介绍](#中文介绍)
  - [它能做什么](#它能做什么)
  - [它解决了什么问题](#它解决了什么问题)
  - [与同类方案的区别](#与同类方案的区别)
  - [快速上手](#快速上手)
  - [产品化亮点](#产品化亮点)
  - [参与与反馈](#参与与反馈)
- [English Introduction](#english-introduction)
  - [What It Does](#what-it-does)
  - [The Problem It Solves](#the-problem-it-solves)
  - [How It Differs](#how-it-differs)
  - [Quick Start](#quick-start)
  - [Production-Ready Features](#production-ready-features)
  - [Contributing &amp; Feedback](#contributing--feedback)
- [License](#license)

---

## 中文介绍

### 它能做什么

`syqmtQQ798623` 是一个**配置驱动**的文件快照脚本。你在 `file_list.txt` 里一行一个列出需要备份的文件路径，运行脚本后，它会：

- **只读复制**（不修改、不移动、不删除源文件）
- 全部拷贝到一个按 `yyyyMMdd_HHmmss` 命名的时间戳目录
- 每个备份文件完整名后追加 `.yyyyMMdd_HHmmss` 后缀，清晰溯源
- 自动做 SHA1 校验，确保副本与源一致

每次运行就是一次**不可逆操作之前的快照节点**。

### 它解决了什么问题

QMT 策略迭代过程里，调参、重构或上线前你大概率做过这些事情：

> "先复制一份出来以防万一" → 手动 Ctrl+C / Ctrl+V，点进备份目录再来一次 → 忘了哪份是哪份 → 干脆删了重来

`syqmtQQ798623` 把以上手动过程收拢成**一条命令（或 IDE 点一下运行）**，实现：

| 手工操作 | 本工具替代方案 |
| --- | --- |
| 记住该备份哪些文件 | `file_list.txt` 一次性写好，之后不用动 |
| 手动建文件夹、起名 | 自动生成 `20260915_161501` 格式 |
| 手动给备份文件加日期后缀 | 自动在扩展名后追加 `.20260915_161501` |
| 怀疑拷贝有损坏 | 自动做 SHA1 校验，不一致会标记失败 |
| 忘了某次备份对应什么版本 | 每次运行产出 `report.json` + `backup.log` |

**特别针对 QMT 用户**：脚本会自动检测文件是否为 QMT 平台"未开启本地编辑"时导出的乱码文本（Base64 单行），并在终端**显式告警**，备份目录名自带 `_未开启本地编辑` 后缀，一眼可辨。

### 与同类方案的区别

| | 手工复制 | git | 本工具 |
| --- | --- | --- | --- |
| 零配置上手 | N/A | 需要 init + commit | `file_list.txt` 填完即用 |
| 不改源文件 | 手动 | 不改 | **只读复制** |
| 自动命名 + 归档 | 无 | 无（git 按 commit） | 时间戳目录 + 文件名后缀 |
| SHA1 校验 | 无 | git 有校验 | 有 |
| 失败隔离 | N/A | 单文件失败会阻断 | 单文件失败不中断，记录进报告 |
| 乱码告警（QMT 特有） | 无 | 无 | **内置** |
| 依赖 | 无 | git | **仅 Python 标准库** |
| 产品化报告 | 无 | `git log` | `report.json` + `backup.log` |
| 可重入 | N/A | 有 | 同秒重复运行自动 `_retryN` |

### 快速上手

1. **配置列表**：在 `file_list.txt` 写入备份目标，一行一个绝对路径：

```txt
"D:\国金证券QMT交易端\python\wave_detector.py"
"D:\国金证券QMT交易端\python\CKLBUY.py"
"D:\国金证券QMT交易端\bin.x64\a0stock_pool.csv"
```

2. **运行**：

```powershell
cd syQMT
python syqmtQQ798623.py
```

3. **查看结果**：

```
backups/20260915_161501/
├── wave_detector.py.20260915_161501
├── CKLBUY.py.20260915_161501
├── a0stock_pool.csv.20260915_161501
└── report.json
```

**更多命令行参数**：

| 参数 | 作用 |
| --- | --- |
| `--dry-run` | 只预览计划，不实际复制 |
| `--list` | 解析并打印列表里的有效路径 |
| `--check` | 只校验文件是否存在 / 可读 |
| `--file my.txt` | 使用指定的列表文件 |

### 产品化亮点

| 特性 | 说明 |
| --- | --- |
| **只读 + 校验** | `shutil.copy2()` 以只读模式打开源，复制后 SHA1 比对 |
| **失败隔离** | 单文件不存在或权限不足不影响其余文件 |
| **可重入** | 同秒二次运行自动追加 `_retryN`，不覆盖历史 |
| **可观测** | 每次运行产出 `report.json`（机器可读）+ `backup.log`（滚动日志） |
| **零依赖** | 仅使用 Python 标准库，无需 `pip install` |
| **兼容打包** | 已兼容 PyInstaller 冻结为 .exe |

### 参与与反馈

这是 [QMT 辅助工具集](https://github.com/NobodySniper) 的一部分。如果你发现 bug、有功能建议，或想贡献代码：

- 提 [Issue](https://github.com/NobodySniper?tab=repositories)
- 提交 Pull Request
- 通过 QQ `798623` 直接联系作者 **宁尚拙**

任何来自 QMT 实战一线的反馈都是宝贵的——欢迎一起把策略迭代流程打磨得更顺滑。

---

## English Introduction

### What It Does

`syqmtQQ798623` is a **config-driven snapshot tool** — it reads a list of file paths from `file_list.txt` and, on each run:

- Performs a **read-only copy** (never modifies, moves, or deletes source files)
- Outputs all copies into a timestamp-named directory (`yyyyMMdd_HHmmss`)
- Appends `.yyyyMMdd_HHmmss` after the original file extension for traceability
- Runs an **SHA1 integrity check** on every copy to ensure it matches the source

Think of it as a one-command checkpoint before making risky edits.

### The Problem It Solves

When iterating on QMT trading strategies, your pre-change ritual probably looks like:

> Manually copy files → create a folder → name it by date → wonder which backup was which → give up and delete them all.

This tool collapses that workflow into **one command (or a single IDE click)**:

| Manual Workflow | What This Tool Does |
| --- | --- |
| Remember *which* files to back up | Write `file_list.txt` once — never touch it again |
| Create and name backup folders | Auto-generated as `20260915_161501` |
| Manually add date stamps to filenames | Auto-appended as `.20260915_161501` |
| Worry about corrupted copies | SHA1 verification; mismatch = flagged as failure |
| Forget what a backup was for | Every run produces `report.json` + rolling `backup.log` |

**QMT-specific awareness**: the script detects files exported from the QMT platform *without* local editing enabled (single-line Base64-encoded blobs), explicitly warns you in the terminal, and appends `_not-editable` to the backup folder name for instant visual recognition.

### How It Differs

| | Manual Copy | git | This Tool |
| --- | --- | --- | --- |
| Zero-config | N/A | Needs init + commit | Fill `file_list.txt` and run |
| Never touches source | Manual | Immutable | **Read-only copy** |
| Auto naming & archiving | No | No (git by commit) | Timestamp dirs + file suffix |
| SHA1 verification | No | Git has integrity check | Yes |
| Failure isolation | N/A | Single failure blocks | Fails per-file, records errors |
| Encoded-blob warning (QMT) | No | No | **Built-in** |
| Dependencies | None | git | **Python stdlib only** |
| Production report | None | `git log` | `report.json` + `backup.log` |
| Re-entrant safe | N/A | Yes | Auto `_retryN` suffix on re-runs |

### Quick Start

1. **Configure your list** — edit `file_list.txt` with absolute paths:

```txt
"D:\GuoJin\QMT\python\strategy.py"
"D:\GuoJin\QMT\bin.x64\data.csv"
```

2. **Run**:

```powershell
cd syQMT
python syqmtQQ798623.py
```

3. **Check the result**:

```
backups/20260915_161501/
├── strategy.py.20260915_161501
├── data.csv.20260915_161501
└── report.json
```

**CLI options**:

| Flag | Purpose |
| --- | --- |
| `--dry-run` | Preview plan without copying |
| `--list` | Parse and print resolved paths |
| `--check` | Validate file existence / readability only |
| `--file my.txt` | Use a custom list file |

### Production-Ready Features

| Feature | Detail |
| --- | --- |
| **Read-only + verified** | `shutil.copy2()` opens source as read-only; SHA1 check post-copy |
| **Failure isolation** | One missing file does not block the rest |
| **Re-entrant** | Concurrent runs appended with `_retryN` — no history overwritten |
| **Observable** | Each run emits `report.json` (machine-readable) + `backup.log` (rolling) |
| **Zero deps** | Only the Python standard library; no `pip install` needed |
| **PyInstaller-compatible** | Ready to be frozen into a standalone `.exe` |

### Contributing & Feedback

This tool is part of the [QMT Utilities](https://github.com/NobodySniper) family. Found a bug? Have a feature idea? Want to contribute?

- Open an [Issue](https://github.com/NobodySniper?tab=repositories)
- Submit a Pull Request
- Reach the author **宁尚拙** directly via QQ `798623`

Real-world feedback from QMT traders is gold — let's make strategy iteration smoother together.

---

## License

This project is open-sourced under the MIT License.

---

*Powered By [宁尚拙](https://github.com/NobodySniper) · QQ: 798623*
