# 配置与恢复

## 本机设置

私有配置为 `~/.config/minimax/env`，目录权限 700、文件权限 600。只将 shell 赋值当作数据解析，不执行文件。环境变量优先，`MINIMAX_ENV_FILE` 或全局 `--env-file` 可指定其他文件；旧进程环境会覆盖文件更新。

| 变量 | 用途 |
| --- | --- |
| `MINIMAX_API_KEY` | 官方按量付费 API Key，由隐藏输入写入 |
| `MINIMAX_API_HOST` | 默认 `https://api.minimax.cn`；国际站 `https://api.minimax.io`，亦接受官方国内旧域 `https://api.minimaxi.com` |
| `MINIMAX_VIDEO_MODEL` | 默认 `MiniMax-H3`，不改其他应用模型配置 |
| `MINIMAX_R2_ACCOUNT_ID`、`MINIMAX_R2_BUCKET` | 可选私有 R2 桶 |
| `MINIMAX_R2_ACCESS_KEY_ID`、`MINIMAX_R2_SECRET_ACCESS_KEY` | 可选对象读写凭据 |

不设置 `ANTHROPIC_*`、`OPENAI_*` 或 shell 启动文件，不读取其他工具的聊天凭据。按量 Key 入口为[国内站接口密钥](https://platform.minimax.cn/user-center/basic-information/interface-key)或[国际站接口密钥](https://platform.minimax.io/user-center/basic-information/interface-key)。H3 文档要求按量购买 API，不把聊天订阅 Key 当成已验证的视频凭据。切换区域须使用对应账户的 Key，不自动跨区试密钥。

macOS 安全配置（命令中没有密钥）：

```sh
python3 "$SKILL_DIR/scripts/configure.py" --region cn --gui
```

其他系统在用户交互终端运行并省略 `--gui`，使用 getpass 隐藏输入。已有环境变量可加 `--from-env`；替换密钥加 `--replace-key`。取消输入不覆盖原配置。

可选 `--reuse-nxtpath-r2` 只复制四个 `NXTPATH_R2_*` 值为 `MINIMAX_R2_*`，不复制网关 API Key、不更改旧配置或上传素材。新客户端不依赖旧 skill 或旧配置文件。

## Python 环境

纯文本、HTTPS 和 `mm_file://` 输入可使用 Python 3.9+ 标准库。完整本地输入功能建议 Python 3.10+，在独立工具环境安装依赖：

```sh
python3 -m venv "$HOME/.config/minimax/venv"
"$HOME/.config/minimax/venv/bin/python" -m pip install -r "$SKILL_DIR/scripts/requirements.txt"
"$HOME/.config/minimax/venv/bin/python" "$SKILL_DIR/scripts/minimax_video.py" doctor --check-api
```

Pillow/pillow-heif 校验图片和 HEIC/HEIF，PyAV 校验音视频，boto3 仅供 R2。依赖、凭据、虚拟环境和生成任务均留在源码外。

`doctor --check-api` 只读 `GET /v2/query/video_generation?page_num=1&page_size=1`，不输出历史任务正文。成功证明 Key 可访问 V2 查询接口，不证明余额、模型权限或生成质量。`doctor --check-hosting` 仅 list R2，不上传。

## 输入交付

- `inline`：默认。保存本地副本后在提交时构造官方 data URI。请求上限 64 MB，Base64 约膨胀三分之一；prepare 和 submit 前均检查。
- `r2`：显式选择。host 使用不可变副本，以 `minimax/references/<hash>.<ext>` 复用对象，签发 24 小时 GET 并回读校验。403 不当作不存在，不公开桶或自动删除对象；链接过期不代表对象被删除。
- HTTPS / `mm_file://` 无需 host。远程输入由官方检查媒体规格，prepare 不下载或声称已审看。

R2 URL 提交前至少剩余 30 分钟；可在 submit 前重新 host 刷新，提交记录存在后不可更改。换交付方式使用新任务。

## 恢复

- 目录存在时先 inspect，不重新 prepare。任何 submission.json 都阻止再次 POST；重试 status/download 与新建付费候选是不同操作。
- 记录在 POST 前独占落盘；超时、断线、5xx 或无 ID 保留 unknown。官方文档没有确认幂等请求头，本地 UUID 不能保证服务端去重。
- 401/403、余额不足或参数错误等保留 rejected，报告错误，不自动更换密钥、区域、模型或新目录继续生成。
- 成功响应已写入 submit-response.json 时，status 能恢复缺失 ID；否则用私有时间、请求哈希、响应及只读 tasks 向提供商核对，不按相似参数自动绑定旧任务。
- `tasks --page 1 --page-size 20` 仅显示指纹。完整记录可用 `--output <尚不存在的私有文件>` 保存，不整份展示。列表覆盖最近 7 天，不自动遍历全部历史。
- 原任务冻结官方区域，续查使用相同 host。哪都通旧任务由原 nxtpath-minimax-video 处理，本客户端拒绝其 manifest。
- 下载中断保留 .part；重查原任务刷新过期 URL，再次下载检查已有文件哈希。容器检查不替代播放和视觉验收。
- 同一任务的 download 使用系统独占锁，进程退出即释放，避免并发写坏成片。download.lock 文件可持续存在，不等于任务仍被占用，不需要删除来恢复下载。
