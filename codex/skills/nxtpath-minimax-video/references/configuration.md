# 配置与恢复

## 凭据与运行环境

统一文件为 `~/.config/nxtpath/env`，目录权限 700、文件权限 600。只解析带引号的 shell `export NXTPATH_NAME=value` 赋值，不执行文件。操作系统环境优先，`NXTPATH_ENV_FILE` 或全局 `--env-file` 可选择另一份配置。

| 变量 | 用途 |
|---|---|
| `NXTPATH_API_KEY` | 哪都通 API 密钥，与本机 Seedance skill 共享 |
| `NXTPATH_MINIMAX_MODEL` | 可选，默认且目前仅支持 `minimax/minimax-h3` |
| `NXTPATH_R2_ACCOUNT_ID`、`NXTPATH_R2_BUCKET` | 本地图片的私有 R2 桶 |
| `NXTPATH_R2_ACCESS_KEY_ID`、`NXTPATH_R2_SECRET_ACCESS_KEY` | R2 对象读写凭据 |

本机配置已存在时直接复用，不把密钥复制进 skill。不使用 `ANTHROPIC_AUTH_TOKEN` 或其他应用的设置文件。`NXTPATH_SEEDANCE_MODEL` 不影响本技能；不支持通过 `NXTPATH_BASE_URL` 改写网关。

HTTPS 图片或纯文本无需 R2 或第三方 Python 包。本地图片需要 boto3，安装在工具虚拟环境中：

```sh
python3 -m venv "$HOME/.config/nxtpath/venv"
"$HOME/.config/nxtpath/venv/bin/python" -m pip install -r "$SKILL_DIR/scripts/requirements.txt"
```

客户端自带配置文件回退，不要求更改 shell 启动脚本。环境中的旧凭据会覆盖文件更新；旋转密钥后应刷新环境或启动新的进程。

`doctor --check-api` 仅读模型列表；`doctor --check-hosting` 仅读 R2 对象列表，不上传或生成。列表失败不能直接断言密钥过期，应核对返回的 HTTP 状态及权限。

## 本地图片与隐私

`prepare` 保存不可变输入快照；`host` 上传快照而不是再读用户原图。对象按内容哈希复用，R2 桶保持私有，GET 链接有效期 24 小时。提交时要求链接至少还有 30 分钟有效；未提交前可再次 `host` 刷新链接。提交后不改引用。

本实现沿用已配置的私有 R2，并非官方脚本的临时 OSS；不会自动删除 R2 对象，也不承诺对象在一天后消失。托管记录含对象键及到期时间，仅在已授权的素材范围内上传。不自动尝试其他托管服务；已有 HTTPS 图片可省略托管。

R2 的 403 不当作对象缺失，避免在权限错误时继续写入。匿名 GET 哈希与输入不符时不提交视频。超过 20 MiB 的图片先另外缩小，不改原图。

## 恢复规则

- 任务目录已经存在时，使用 `inspect`，不再次 prepare 覆盖。
- 有 `submission.json` 时不再 submit。已有句柄用 `status`，成功后用 `download`。
- 401/403、额度不足或模型不可用时停止提交，报告本机配置或服务问题，不换密钥、通道或模型。
- 超时、断线、5xx、408、409、响应缺少句柄保留为 `unknown`。用私有提交时间、幂等键和请求哈希向提供方核对；不删除记录后重试或换新目录重发。
- `submit-response.json` 已保存句柄时，`status` 能修复尚未完成的提交记录。请求哈希或网关记录变化时拒绝续查。
- `download` 中断时保留 `.part`，重试只下载同一任务。已完成视频再次下载前核对本地哈希，不重新生成。
- `Expired` 或已过期的下载句柄可能无法恢复。保留证据并报告；新生成需要用户的生成或返工请求覆盖。

记录中的签名 URL、提示词和任务句柄可能敏感；仅提供必要摘要，不整份复制进聊天、日志或 Git。跨设备携带任务目录时保持私有权限；凭据留在各设备自己的配置中。
