---
name: minimax-video
description: 使用 MiniMax 官方 API 生成、续查和下载 H3 视频，支持文生视频、首尾帧及图片/视频/音频参考。用于 MiniMax 或海螺视频制作、官方 API 配置和已有官方任务恢复；明确指定哪都通或恢复其旧任务时使用 nxtpath-minimax-video。
---

# MiniMax 官方视频

使用本 skill 的 `scripts/minimax_video.py` 直连 MiniMax 官方 V2 接口。默认国内站 `https://api.minimax.cn`，国际站为 `https://api.minimax.io`，默认模型 `MiniMax-H3`。一般 MiniMax 新任务使用本技能；哪都通任务必须由原客户端续查，任务 ID 不跨服务迁移。

## 配置

- 从实际 skill 安装目录定位脚本。优先使用 `~/.config/minimax/venv/bin/python`；纯文本、HTTPS 或 `mm_file://` 输入仅需 Python 3.9+。本地素材校验和可选 R2 需要 `scripts/requirements.txt` 中的依赖。
- 凭据读取 `MINIMAX_API_KEY`，环境变量优先，否则解析 `~/.config/minimax/env`。不读取其他应用的聊天凭据，不把密钥写入 skill、命令行或任务记录。国内/国际站及工具环境见 [配置与恢复](references/configuration.md)。
- 缺少密钥时，用 `scripts/configure.py --region cn --gui` 在 macOS 隐藏输入框配置；其他系统在用户终端中隐藏输入。不要要求用户把密钥发进聊天。用户已有环境变量可使用 `--from-env`，轮换使用 `--replace-key`。
- `doctor --check-api` 仅读最近任务列表，验证鉴权和 V2 查询接口；不证明余额、特定模型生成权限或成片质量。安装、配置、研究接口不授权付费生成。

## 参数与输入

选择模型、非默认参数或多模态素材时，先读 [官方接口与能力](references/api.md)，不要沿用哪都通的模型 ID、720p/960p 档位或 4–12 秒限制。

- 默认小样为 H3、4 秒、768P；纯文本默认 16:9，首尾帧由输入图片决定比例。四种 H3 模型的分辨率、时长和参考比例限制不同，客户端按模型校验。
- `--first-frame`、`--last-frame` 各至多一张；多模态参考使用可重复的 `--ref-image`、`--ref-video`、`--ref-audio`。首尾帧不能与多模态参考混用。保持素材顺序，并在提示词中明确“参考图1”“参考视频1”等角色。
- 素材支持本地文件、HTTPS URL、当前官方账户的 `mm_file://` 句柄。本地输入先保存不可变副本并校验格式、尺寸、时长等；远程输入的媒体规格由官方验证，不声称已在本地审看。
- 小型本地素材默认 `--delivery inline`，按官方 data URI 格式随生成请求传入，无需第三方托管。Base64 膨胀后的请求总大小须不超过 64 MB；本地 MOV 或较大素材可显式使用 `--delivery r2`，然后执行 `host`。不自动上传、转码或修改用户原文件来绕过限制。
- R2 模式只使用已配置的私有桶，按哈希复用对象并验证匿名下载。上传前遵守目标项目的素材和隐私约定；仅在当前任务授权的素材范围内托管。配置或托管失败时报告，不自动更换图床。

## 制作与续查

用户要求生成视频时完成一条候选；批量和额外尝试遵循本次约定。每个候选使用新任务目录，优先放在项目忽略的 `tmp/artwork/generations/<run-id>/<asset-id>/<attempt-id>/`；无项目时使用工作区临时目录或用户指定位置，不覆盖旧任务。

1. 用 `doctor --check-api` 检查配置。将动作、镜头、角色/道具约束和声音要求写入 UTF-8 提示词文件，用 `prepare` 冻结提示词、官方参数、服务区域和输入副本。此步离线，不生成视频。
2. 仅在 `--delivery r2` 且含本地素材时运行 `host`。此操作把素材传到私有 R2，并让 MiniMax 使用签名链接；inline 素材直接传给 MiniMax。
3. 运行一次 `submit`。客户端在付费 POST 前独占保存提交记录和请求哈希；官方未在所核对文档中承诺幂等键，不能把本地请求 UUID 当作服务端去重保证。
4. 使用独立的 `status` 查询，状态为 `queued` / `running` / `succeeded` / `failed` / `cancelled`。用宿主可中断等待并保持进度沟通，不在长 shell 命令里轮询数分钟。
5. 成功后用 `download` 下载、校验 MP4 并保存哈希。下载失败只重试 `status` / `download`；过期媒体 URL 可重新查询刷新。官方仅提供最近 7 天任务查询，应及时落盘。
6. 跨对话恢复先 `inspect --job`，再 `status` / `download`。任何 `submission.json` 都阻止重新提交。超时、断线、5xx 或未返回 ID 为结果不明确，保留证据；可用只读 `tasks` 辅助核对，但模型和时间相近不能证明是同一任务。失败或结果不明不自动创建额外付费候选。

命令示例（变量均代表实际绝对路径；JOB 必须尚不存在）：

```sh
"$PY" "$CLIENT" doctor --check-api
"$PY" "$CLIENT" prepare --job "$JOB" --prompt-file "$PROMPT_FILE" --first-frame "$FIRST_FRAME" --duration 4 --resolution 768P
"$PY" "$CLIENT" submit --job "$JOB"
"$PY" "$CLIENT" status --job "$JOB"
"$PY" "$CLIENT" download --job "$JOB"
```

纯文本省略 `--first-frame`，按需给出 `--ratio`；首尾帧可加 `--last-frame`。多模态参考用相应 `--ref-*` 参数。R2 模式在 prepare 时加 `--delivery r2`，在 submit 前运行 `host --job "$JOB"`。完整选项可读脚本 `--help`。

## 交付

交付可播放的本地 `video.mp4` 和任务目录，用绝对路径展示视频。说明实际模型、时长、分辨率、比例和声音表现，以及是否审看了原速视频、首尾帧和角色一致性；HTTP 成功不等于视觉验收通过。

任务记录含提示词、Base64 素材、签名 URL 和真实任务 ID，仅当前用户可读，不整份贴进聊天或提交 Git。控制台显示任务指纹；官方 API Bearer 只发送到允许的官方 API 主机，成片及其所有跳转均匿名 HTTPS 下载。
