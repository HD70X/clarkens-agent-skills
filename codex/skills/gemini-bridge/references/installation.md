# 安装、设备密钥与迁移

## 安装包与前提

整个 `gemini-bridge/` 文件夹就是 skill；保留 `SKILL.md`、`agents/`、`scripts/` 和 `references/`。支持 macOS 和 Windows，需可运行 Python 3.9+，不需要 pip、Gemini CLI 或每项目依赖。使用当前设备自己准备的 [Google AI Studio Gemini API Key](https://aistudio.google.com/apikey)。这是 Gemini Developer API 的密钥，不是 Google Cloud 服务账号 JSON。

安装器优先沿用设备已存在的 `$CODEX_HOME/skills` 或 `~/.codex/skills`；否则选择官方用户目录 `~/.agents/skills`。也可以用 `--target` 指定完整目标目录，最后一级必须叫 `gemini-bridge`。同一设备只选一个加载位置，避免同名副本。

没有模型配置步骤，也不读取 `GEMINI_MODEL`、`GOOGLE_MODEL` 或项目配置来决定模型。安装器不导入密钥、不创建任务授权。

## macOS

在仓库根目录 `agent-skills/` 执行：

```bash
python3 codex/skills/gemini-bridge/scripts/install.py --configure --gui
```

解压独立安装包后，在 `gemini-bridge/` 的父目录执行：

```bash
python3 gemini-bridge/scripts/install.py --configure --gui
```

会弹出隐藏输入窗口，将这台设备的密钥粘贴进去。密钥直接存入当前用户的登录钥匙串，服务名 `codex-gemini-bridge`、账号 `google-api-key`；没有纯文本文件回退。钥匙串若要求允许 Python 访问，请核对当前本机 Python 程序后允许。Python 路径变化时系统可能再次询问访问权限。

按实际安装位置检查，例如当前设备沿用 `.codex/skills` 时：

```bash
python3 "$HOME/.codex/skills/gemini-bridge/scripts/gemini.py" doctor --online
python3 "$HOME/.codex/skills/gemini-bridge/scripts/gemini.py" models
```

如果选择了 `.agents/skills`，相应改用该路径。`doctor --online` 和 `models` 仅验证密钥并列出模型，不执行推理，不选择默认模型；列举成功不证明账号有每个模型的推理权限。

也可在终端使用隐藏输入：`python3 <安装目录>/scripts/gemini.py configure`。脚本拒绝从命令参数、管道或聊天接收密钥。

## Windows（PowerShell）

确认 `py -3 --version` 可用；如果没有 `py`，用本机可用的 `python` 替换以下 `py -3`。在仓库根目录执行：

```powershell
py -3 .\codex\skills\gemini-bridge\scripts\install.py --configure
```

独立安装包则在解压后的父目录执行：

```powershell
py -3 .\gemini-bridge\scripts\install.py --configure
```

在终端隐藏输入提示处粘贴这台设备的 Gemini API Key，回车保存。密钥通过 Win32 `CredWriteW` 保存为当前用户的普通凭据，目标名 `CodexGeminiBridge/GoogleAPIKey`，使用 `CRED_PERSIST_LOCAL_MACHINE`，不使用企业漫游存储。没有 `.env`、注册表纯文本或安装包内密钥副本。

检查实际安装位置，例如已有 `.codex\skills` 的设备：

```powershell
$bridgeScript = Join-Path $env:USERPROFILE '.codex\skills\gemini-bridge\scripts\gemini.py'
py -3 $bridgeScript doctor --online
py -3 $bridgeScript models
```

新设备若安装到 `.agents\skills` 或自定义 `CODEX_HOME`，按安装器输出修改路径。密钥必须由目标设备的实际运行用户配置，其他 Windows 用户不能复用。

## 更新、换设备与卸载

- 更新：对新源码运行同一安装命令，加 `--upgrade`。旧 skill 备份到 skill 加载目录之外的 `skill-backups/`；凭据不在 skill 文件夹内，更新不会复制或覆盖凭据。`--configure` 只在希望重新输入密钥时添加。
- 换设备：只传递 skill 文件夹或 zip，在新设备重新安装、配置自己的密钥。不要复制系统凭据、任务授权或运行记录。
- 修改密钥：运行已安装脚本的 `configure`，macOS 可加 `--gui`。
- 删除密钥：运行 `gemini.py remove-key`，只删除本 skill 对应的 OS 凭据。
- 卸载：删除已安装的 `gemini-bridge/`。如还要清理私有任务状态，在停止相关任务后删除下述用户数据目录；这与删除 OS 凭据分别处理。

用户数据位置：macOS 为 `~/Library/Application Support/CodexGeminiBridge/`；Windows 为 `%LOCALAPPDATA%\CodexGeminiBridge\`。其中 `tasks/` 保存按聊天及项目绑定的授权，`runs/` 保存执行模式上下文、工具结果与文件清单；不保存 API Key。运行上下文可能包含项目源代码，应留在当前用户目录，不加入安装包或项目仓库。

Codex 若未显示新 skill，按 [官方加载说明](https://learn.chatgpt.com/docs/build-skills) 核对加载位置并重启 Codex；安装器不创建第二个同名副本或修改其他 Codex 配置。

## 常见故障

| 现象 | 处理 |
| --- | --- |
| credential missing | 在本机当前用户下运行 `configure` |
| Keychain access failed | 解锁登录钥匙串，并核对 Python 的访问请求 |
| Windows 凭据读取失败 | 核对运行用户及交互登录状态，重新配置本用户凭据 |
| HTTP 401/403 | 核对密钥有效性、API 限制、地区、项目计费和模型权限 |
| HTTP 404 | 所选模型不可用，重新列举并由用户明确选择 |
| HTTP 429 | 检查配额或限流，之后显式重试 |
| SSL 或连接错误 | 检查本机证书和网络；不关闭 TLS 验证，不改用中转接口 |

Google 的模型可用性以当前账号和官方 API 为准。API 文档：[模型列表](https://ai.google.dev/api/models)、[Gemini 4 Argon 的 generateContent 接口](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)。Windows 存储语义见 [CREDENTIALW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw)。
