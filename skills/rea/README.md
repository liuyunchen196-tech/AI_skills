# REA 技能（本地部署）

将 GitHub 开源项目 **REA（Reverse Engineer Anything，`morluto/rea`）** 部署为本机自包含技能，供豆包/WorkBuddy 共享技能库调用。

- 上游仓库：<https://github.com/morluto/rea>
- npm 包：`rea-agents`（本目录安装版本 **6.7.0**）
- 部署日期：2026-11-02
- 部署方式：从 GitHub `main` 下载源码（`source/` 参考）+ 在技能目录内**局部 npm 安装**运行时（自包含，无需全局安装，规避沙箱运行时 node 不可靠问题）

## 目录结构

```
D:\AI技能库\skills\rea\
├── SKILL.md          ← 技能定义（Agent 读取，含调用方式与本机状态）
├── README.md         ← 本文件
├── rea.cmd           ← 便捷启动器（node …\rea.mjs %*）
├── package.json      ← 固定 rea-agents@6.7.0
├── node_modules\     ← 自包含运行时（rea-agents + 依赖，约 174 个包）
├── references\       ← REA 官方技能参考文档（android/js/native/runtime/evidence/connection）
├── docs\             ← 关键官方文档（installation.md、mcp-contracts.md）
└── source\           ← REA 完整源码（GitHub 参考，可重建/审阅）
```

## 使用

- 查看命令：`D:\AI技能库\skills\rea\rea.cmd --help`
- 就绪诊断：`D:\AI技能库\skills\rea\rea.cmd doctor`
- 可用引擎：`D:\AI技能库\skills\rea\rea.cmd providers`
- 示例（JS/Electron 应用静态分析）：`D:\AI技能库\skills\rea\rea.cmd analyze-javascript-application "C:\目标\app" --json`
- 示例（.NET 程序集静态检查）：`D:\AI技能库\skills\rea\rea.cmd inspect-managed-artifact "C:\目标\App.dll"`

## 本机 Windows 就绪度（2026-11-02 实测）

- ✅ 可用：CLI 正常；.NET/PE 静态检查；JS/Electron 静态反混淆；WASM、EVM、Go/Rust 内嵌元数据、PE 资源、Web 抓取、artifact 图。
- ⚠️ 暂不可用：Ghidra 原生反编译、JADX（Android APK）——REA 在 Windows 上的**原生自检失败**（temp 目录 DACL 访问拒绝，Win32 5，属实验性支持）；Hopper 不支持 win32；IDA/Kuna 未配置；SQLite 需 Node 24.15+。

详细见 `SKILL.md` 的「本机 Windows 状态」与 `docs/installation.md`。

## 维护

- 升级运行时：在技能目录执行 `npm install rea-agents@latest`，更新 `package.json` 与 `package-lock.json`。
- 更新源码参考：重新下载 GitHub `morluto/rea` 源码替换 `source\`。
- 删除本技能：删除 `D:\AI技能库\skills\rea\` 及两侧技能目录中指向它的 junction（如已建）。
