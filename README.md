# API 环境切换器

一个面向 Windows 的 Codex API 环境管理工具，提供图形界面和命令行入口，可保存多个 API 配置并在它们之间切换。

## 功能

- 管理多个 API 环境配置，包括服务地址、API Key 和模型
- 测试 API 连通性并获取可用模型
- 在 Codex 配置与 Windows 环境变量之间应用所选配置
- 提供 Windows 托盘与图形界面
- 提供 `apictl` 命令行工具

## 运行

需要 Windows 和 Python 3。启动图形界面：

```powershell
python apictl_gui.py
```

命令行入口：

```powershell
python apictl.py --help
```

## 构建

项目使用 PyInstaller 生成 Windows 程序，安装包由 Inno Setup 制作。构建脚本见 `API环境切换器.spec` 和 `installer.iss`。

## 安全提示

API Key 属于敏感信息。请勿将密钥提交到版本库或公开 issue；使用本工具前请确认你信任所配置的 API 服务。
