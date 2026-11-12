# 本机配置与区域切换

本 Skill 使用官方 `tripo-cli`；当前验证版本为 **0.7.1**，需要 Node.js 20+、Python 3.9+。无需额外 LLM API、Blender MCP 或 Tripo Studio 会员。

## 换设备使用空白模板

仓库提供两份可同步、无真实密钥的模板：

- [本机配置模板](../assets/config.example.json)：默认 CN，指向新设备自己的私有凭据文件。
- [CN 凭据文档模板](../assets/tripo-cn.example.md)：仅保留字段，密钥值为空。

在另一台设备安装完整 Skill 和下方 CLI 依赖后，把两份模板分别复制为 `~/.config/tripo-skill/config.json` 和 `~/.config/tripo-skill/tripo-cn.md`，在后者填写该设备使用的 CN 密钥。Linux/macOS 将配置目录权限设为 700、两个文件设为 600；Windows 使用当前用户私有目录。然后运行下方 `doctor` 检查。

已有本机配置时保留原文件，不用空白模板覆盖。可以选择其他私有路径，只需相应修改 `credentials_file`；CLI 和 Node 的默认位置可用时无需填写 `cli_entry`、`node`。真实密钥、账号额度和执行历史不会随 Skill 仓库同步。

## 安装依赖

将依赖安装在仓库外，不打包 node_modules、密钥或账户历史：

```sh
npm install --prefix "$HOME/.local/share/tripo-skill" --no-audit --no-fund --ignore-scripts --save-exact tripo-cli@0.7.1
```

本机设置文件为 `~/.config/tripo-skill/config.json`，是私有机器配置，不进入 Skill 源码。结构如下，路径须换成实际本机位置：

```json
{
  "region": "cn",
  "credentials_file": "/absolute/private/path/tripo-cn.md",
  "cli_entry": "~/.local/share/tripo-skill/node_modules/tripo-cli/dist/cli.js",
  "node": "/absolute/path/to/node"
}
```

当前对话约定的凭据文件是工作区外层 `.secrets/tripo-cn.md`，不是 Git 仓库内的文件。真实路径由本机设置保存，迁移设备时更新设置而非修改 Skill。

Markdown 内嵌 dotenv 赋值即可，包装器只解析字段、不执行 Shell：

```dotenv
TRIPO_REGION=cn
TRIPO_API_BASE_URL=https://openapi.tripo3d.com/v3
TRIPO_API_KEY=
```

在最后一行填写真实密钥，文件权限应为 600、私有目录为 700。不要 `cat` 文件或把其内容贴入聊天。环境变量 `TRIPO_API_KEY` 可以覆盖文件密钥；仅使用环境凭据时，设置对应的 `TRIPO_REGION`。`TRIPO_CREDENTIALS_FILE` 可替换凭据路径，`TRIPO_SKILL_CONFIG` 可替换本机设置路径，`TRIPO_CLI_ENTRY` 和 `TRIPO_NODE` 可指定运行时。

## 检查连接

```sh
python3 /absolute/path/to/tripo-model/scripts/tripo.py -- doctor --json
python3 /absolute/path/to/tripo-model/scripts/tripo.py -- balance --json
```

这两条只查询，不创建模型。包装器固定使用当前区域的官方主机；Markdown 中的 `/v3` 会转换为 CLI 需要的主机地址，避免请求变成 `/v3/v3/...`。区域与文件或地址不一致时在本地报错，不自动探测其他区。

本机 CLI 安装与历史位于 `~/.local/share/tripo-skill/`，按 `state/cn`、`state/ov` 隔离。包装器关闭匿名分析和自动更新检查，凭据仅通过子进程环境传入。官方 CLI 还可能在项目生成 `.tripo/context.json`，其中保存最近任务等上下文；将 `.tripo/` 及本次临时产物加入该项目忽略规则。

## 切换国际站

在独立的私有文件保存国际站凭据：

```dotenv
TRIPO_REGION=ov
TRIPO_API_BASE_URL=https://openapi.tripo3d.ai/v3
TRIPO_API_KEY=
```

临时调用：

```sh
python3 "$CLIENT" --region ov --credentials-file "$OV_CREDENTIALS_FILE" -- doctor --json
```

长期切换时修改本机设置的 `region` 和 `credentials_file`，无需改写 Skill。各区使用自己的账户密钥、余额和历史；切区不迁移积分、任务或 `@last`。同一任务的续查和下载必须沿用原区域及账户。包装器使用环境凭据，不依赖 CLI `login/use/config set region` 的保存值。

## 执行记录与验证范围

生成、上传和处理命令需要包装器 `--record-dir`，包括免费绑定检查；只读查询和 dry-run 不要求记录。记录包含 `invocation.json`、`stdout.ndjson`、`stderr.log`、`completion.json`。目录必须全新，启动前已存在就拒绝执行；凭据不会进入记录。退出状态不代表美术或引擎验收。CLI 的任务历史另存实际 task_id、请求和种子；下载产物目录中的 `task.json` 保存复现信息。

本次安装用真实余额查询验证 CN 鉴权；用离线模拟验证生成、续查、下载、区域匹配、脱敏及不重复提交，不以模拟模型声称真实付费生成已验收。

官方依据：

- [CLI 与地区配置](https://developers.tripo3d.ai/en/docs/cli)
- [CN 余额查询](https://developers.tripo3d.com/en/docs/account)
- [CN API 定价](https://developers.tripo3d.com/zh/pricing)
- [官方 CLI 源码](https://github.com/vast-enterprise/Tripo-API-CLI)
