# 配置与故障恢复

## 本机凭证

统一文件为 `~/.config/nxtpath/env`，目录权限 700、文件权限 600。文件使用带引号的 shell `export NAME=value` 赋值，客户端仅解析 `NXTPATH_` 变量，不执行文件内容。操作系统环境优先。

| 变量 | 用途 |
|---|---|
| `NXTPATH_API_KEY` | 哪都通视频 API 密钥，必需 |
| `NXTPATH_SEEDANCE_MODEL` | 可选；默认 `seedance-2.5`，不会自动替换模型 |
| `NXTPATH_R2_ACCOUNT_ID`、`NXTPATH_R2_BUCKET` | 本地图片的私有 R2 目标 |
| `NXTPATH_R2_ACCESS_KEY_ID`、`NXTPATH_R2_SECRET_ACCESS_KEY` | R2 S3 对象读写凭证；HTTPS 参考图不需要 |
| `NXTPATH_ENV_FILE` | 可选；配置文件位置覆盖 |

凭证通过本地编辑器维护，不在聊天、命令参数或 Skill 仓库中填写。原工程的 xcconfig 仅是迁移来源，不是 Skill 的运行依赖。

新设备可建立隔离的工具环境，上传用依赖见 Skill 的 `scripts/requirements.txt`：

```sh
python3 -m venv "$HOME/.config/nxtpath/venv"
"$HOME/.config/nxtpath/venv/bin/python" -m pip install -r "$SKILL_DIR/scripts/requirements.txt"
```

在 `~/.zshenv` 中加载私有文件可供新终端使用；客户端的文件回退覆盖未继承环境的 GUI 进程。旋转密钥后，已存在进程可能仍携带旧环境值，应启动新进程或显式刷新相应变量。

Skill 与脚本可以同步到其他设备，凭证不随之同步。这里的文件访问依赖本机执行能力，Claude Code 可用；上传 ZIP 到云端 Claude 会话不会赋予其本机环境或文件访问。

## 接口与恢复

固定网关为 `https://api.nxtpath.ai/v1`。`doctor --check-api` 只读模型列表；`doctor --check-hosting` 只读 R2 对象列表，不创建视频或上传图片。列表权限与对象读写权限有区别，R2 列表失败需要再核对权限，不能直接宣称凭证过期。

生成使用 `/tasks/submit`，查询使用 `/tasks/status`。当前支持 Seedance 2.5 的 4–30 秒及 480p / 720p / 1080p；没有暴露未经验证的 60 fps 或强制首尾帧选项。模型别名可在准备时明确选择，不能在提交失败后自动切换再付费。

`submission.json` 在 POST 前以排他方式创建，断线、5xx 和无 task ID 都保留为 unknown。已收到 task ID 但进程来不及更新最终记录时，`status` 会从 `submit-response.json` 恢复。没有 task ID 的未知请求需用私有幂等键、时间与请求哈希向提供方核对；不能靠新建 attempt 绕过未知请求。

输出下载仅向同源、匹配任务的 artifact 地址发送哪都通 Bearer。已核实的火山 TOS 跳转使用新的匿名请求，其他主机留待检查，不把 API 密钥带过去。结果链接可能过期；先重新查询同一任务并尝试下载，不能把下载失败自动变成新生成。

R2 对象按输入内容哈希复用，桶保持私有，签名图地址不会成为正式运行资源。HTTP 403 不视为对象缺失；检查到凭证或权限异常时，停止托管与后续提交，更新本机凭证或使用用户提供的有效 HTTPS 图片地址。
