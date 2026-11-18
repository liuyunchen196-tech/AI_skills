---
name: rea
description: 使用 REA（Reverse Engineer Anything，github.com/morluto/rea）对原生二进制、.NET/托管程序集、Electron/JavaScript 应用、APK、WASM、EVM 字节码、固件与网页目标进行反编译与逆向分析。当用户提供或指向某个已编译程序/安装包/ASAR/PE/APK/固件/网页，并想搞清其功能实现、反编译代码、比对版本、定位特征时使用。关键词：逆向、反编译、decompile、reverse engineering、Ghidra、JADX、APK、PE、ASAR、Electron、JS反混淆、REA。
license: MIT
---

# REA — Reverse Engineer Anything

本技能将 GitHub 开源项目 [morluto/rea](https://github.com/morluto/rea)（npm 包 `rea-agents`，本地 v6.7.0）部署为本机自包含技能。REA 把 JADX、Ghidra、Hopper、IDA、Kuna 等逆向引擎统一成一个 CLI（本技能用 CLI 形式调用，不依赖 MCP 注册），分析全部在本地完成，每条结论带 Evidence（证据）与局限性说明。

**自包含运行时位置**：`D:\AI技能库\skills\rea\node_modules\rea-agents`（已局部 npm 安装，无需全局安装）。

## 何时使用 / 何时不用

**使用**：当结论依赖一个已编译的二进制、安装包、ASAR、APK、固件、托管程序集，或需要反编译、被动运行时证据、版本比对、特征定位，而可用源码无法直接说明时。

**不要用**：对一份完整的**源码仓库**做普通架构/代码分析时，直接用仓库工具即可，不要运行 REA 就绪检查或 provider 命令。

## 如何调用

所有命令经本技能的启动器或直接调用运行时：

- 启动器：`D:\AI技能库\skills\rea\rea.cmd <命令> [参数]`
- 等价直接调用：`node "D:\AI技能库\skills\rea\node_modules\rea-agents\scripts\rea.mjs" <命令> [参数]`

常用顶层命令：`doctor`（就绪诊断）、`providers`（列出可用分析引擎）、`setup`（配置 Agent 集成/引擎，本机属可选项）、`decompile`、`analyze-javascript-application`、`inspect-managed-artifact`、`inspect-binary-layout` 等。完整命令见 `rea.cmd --help`（153 个 CLI 命令，207 个 MCP 工具）。

推荐给输出加 `--json` 或 `--format json` 以拿到结构化 Evidence。

## 按目标类型路由命令（先选对入口）

- **JavaScript/Electron 应用（ASAR 或已解包目录）**：`analyze-javascript-application <路径> --json`。静态分析，无需任何原生引擎。
- **归档/安装包成员清单（ZIP/APK/IPA/MSIX/DMG）**：`inspect-artifact <路径>`；需要解包时用 `extract-artifact`（指定新输出目录）。
- **Android APK 的类/方法/引用**：`inspect-android-package <apk>` → 再 `inspect-android-class` / `inspect-android-method`。⚠ 本机 JADX 原生自检当前失败（见下方 Windows 状态）。
- **托管 PE/CLI 程序集（.NET）**：`inspect-managed-artifact <路径>`。纯静态、可离线，不加载目标代码。
- **原生二进制/库（x86/x64/ARM）反编译**：需 Ghidra（本机尚未配置/原生自检受阻，见 Windows 状态）。
- **WASM 工件**：`inspect-wasm-artifact`（需设置 `REA_WABT_BIN_DIRECTORY`）。
- **EVM 字节码**：`inspect-evm-interface`。
- **Go 二进制内嵌元数据**：`inspect-go-binary`（无需安装 Go）。
- **Rust 二进制（cargo-auditable 依赖）**：`inspect-rust-binary`。
- **PE 资源树/图标**：`inspect-pe-resources`。
- **固件**：`inspect-firmware-regions` / `extract-firmware`（Linux 侧用 Binwalk/Unblob）。
- **网页**：`analyze-web-bundle` / `capture-web-screenshot` 等。
- **本地 SQLite 快照**：`inspect-sqlite-database`（需 Node 24.15+/26，本机 Node 22 不可用）。

先看 `rea.cmd --help` 和 `rea.cmd doctor` 以确认当前可用的 provider 与命令。

## 本机 Windows 状态（重要，2026-11-02 实测）

本机为 Windows x64、Node v22.23.2。`rea` CLI 可正常运行，但各分析引擎就绪度不同：

- **当前可用（无需额外配置）**：`rea-artifact-graph`（inspect-artifact / extract-artifact / 接口生成器解码）、`rea-dotnet-static`（.NET/PE/CLI 静态检查）、JavaScript/Electron 静态分析、WASM、EVM、Go/Rust 内嵌元数据、PE 资源、Web 抓取等纯 JS 类能力。
- **当前不可用 / 需配置**：
  - `ghidra`：未设置 `GHIDRA_INSTALL_DIR`，且 Windows 原生自检失败（temp 目录 DACL 访问拒绝，Win32 5）。REA 的 Windows Ghidra P0 属实验性支持。
  - `hopper`：不支持 win32。`ida`：未设 `REA_IDA_MCP_CONFIG`。`kuna`：未设 `REA_KUNA_COMMAND`。
  - `jadx`（Android APK）：同样命中 Windows 原生自检失败（DACL 拒绝）。
  - `sqlite`：需 Node 24.15+/26，本机 Node 22 不支持。

**结论**：本机最实用的是 **.NET/PE 静态检查、JS/Electron 静态反混淆、WASM/EVM/Go/Rust 内嵌元数据、PE 资源与网页抓取**。原生二进制深度反编译（Ghidra）与 Android APK 反编译（JADX）因 REA 在 Windows 上的原生自检限制暂不可用——这是环境限制而非技能缺失，文档见 `docs/installation.md`。

若要在本机启用 Ghidra/JADX：需要 Windows 上解决 REA 原生自检的 DACL/temp 权限问题，并安装对应引擎、设置环境变量；详见 `docs/installation.md`。

## 工作方式

- 先给出最小有用的概览/清单，再按问题深入；不重复已做过的相同分析。
- 每条结论区分「观察（observation）/推断（inference）/未知（unknown）」，引用 Evidence ID，保留局限性，不要用静态分析冒充观察到的执行行为。
- 跨多个子系统的大问题：把请求转成问题清单，复用已有 session/Evidence，分阶段推进，最后回看清单核对哪些已答、哪些未答。

## 参考文档

- 官方技能定义：`references/SKILL-rea-official.md`（面向 MCP 的完整版，含工具路由细节）
- `references/native-and-artifacts.md`：原生二进制、托管程序集、归档与解包
- `references/javascript-applications.md`：ASAR/JS 应用、特征追踪、版本比对
- `references/android-applications.md`：APK 声明、类、方法、静态引用
- `references/runtime-observation.md`：浏览器/Electron 被动与场景观察
- `references/evidence-workflows.md`：Evidence 分页、比对、残余未知与验证
- `docs/installation.md`：安装、Provider 配置与恢复
- `source/`：REA 项目完整源码（GitHub 参考，含 docs/tests/插件定义）

## 验证

本机部署后已通过：`rea.cmd --help`、`rea.cmd doctor`、`rea.cmd providers` 运行正常（v6.7.0）。
