---
name: nxtpath-minimax-video
description: 通过哪都通 / Nxtpath 的 MiniMax H3 生成视频，支持文生视频、首尾帧或参考图，保存任务以便跨对话续查和下载。用于明确要求 MiniMax 视频或调用本 skill 的任务；Seedance 视频使用 nxtpath-video。
---

# 哪都通 MiniMax 视频

使用独立客户端 `scripts/nxtpath_minimax_video.py`，固定网关 `https://api.nxtpath.ai/v1`，默认模型 `minimax/minimax-h3`。参数以哪都通的 H3 通道为准，不套用 MiniMax 官方直连接口或 Seedance 参数。已核对的接口及验证范围见 [接口依据](references/api.md)。

## 配置与输入

- 复用本机 `NXTPATH_API_KEY`，环境变量优先，否则解析 `~/.config/nxtpath/env`；`NXTPATH_ENV_FILE` 可覆盖文件路径。不读取 Claude、Codex 或 Grok 的聊天凭证，不把密钥放在命令行或任务记录中。
- 从本 skill 实际目录定位客户端。优先使用 `~/.config/nxtpath/venv/bin/python`；文本或 HTTPS 图片输入仅需 Python 3.9+。本地图片托管还需要 `scripts/requirements.txt` 中的 boto3，配置说明见 [配置与恢复](references/configuration.md)。
- 先读目标项目的素材与隐私约定。每次候选使用新的任务目录，默认放在项目被忽略的 `tmp/artwork/generations/<run-id>/<asset-id>/<attempt-id>/`；无项目时使用当前工作区的临时目录或用户指定位置。不覆盖旧任务或自动替换正式资源。
- 默认小样为 4 秒、720p、16:9。时长为 4–12 整数秒，分辨率仅 720p / 960p / 2k，比例为 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16。
- 三种输入：仅文本；`--first-frame` 和/或 `--last-frame` 各至多一张；可重复的 `--ref-image` 普通参考图。首尾帧与普通参考图不能混用，不支持参考音频或参考视频。普通参考图不具有首尾帧角色。
- 图片使用 HTTPS URL，或本地 PNG/JPEG/WebP（每张至多 20 MiB）。拒绝 data URL。超大图片需要先另存缩小副本，不改用户原图。

## 制作与续查

用户明确要求生成视频时完成一条候选；批量和返工次数沿用本次约定。仅检查配置、研究接口或创建 skill 不授权付费生成。没有约定额外尝试时，不自动重生成失败任务或更换模型。

1. 用 `doctor --check-api` 只读核对凭证、`model_available` 和 `model_supported`；任一模型检查为 false 时停止提交，核实目录或配置。
2. 按用户要求整理动作、镜头、时长和需要保持的角色／道具，将提示词写入 UTF-8 文件。用 `prepare` 冻结提示词、参数与输入快照；此命令离线执行，不生成视频。
3. 有本地图片时运行 `host`，使用已配置的私有 R2，复用内容哈希对象、签发 24 小时 GET 并核对下载哈希。此操作会将输入传给 R2 和视频提供商；托管失败时停止，不自动换公开图床或账号。仅文本或已有 HTTPS 图片可跳过此步。
4. 运行一次 `submit`。它在付费 POST 前持久化排他提交记录及幂等键；随后用独立的 `status` 查询。服务状态为 `Pending` / `Running` / `Success` / `Failure` / `Expired`。等待使用宿主可中断等待并保持进度沟通，不在长 shell 调用里循环数分钟。
5. `Success` 后用 `download` 下载并校验 MP4。下载失败只重试下载；`Failure` / `Expired` 为该任务的终态，报告结果，不能因此自动新建付费任务。
6. 跨对话恢复使用原 job 路径，先 `inspect`，再 `status` / `download`。存在提交记录、超时、断线或缺少 task ID 时不得重新 POST；结果不明须按私有记录向提供方核对，不用新 attempt 绕过。

命令示例（`PY`、`CLIENT`、`JOB`、`PROMPT_FILE` 和图片变量指实际路径；JOB 必须尚不存在）：

```sh
"$PY" "$CLIENT" doctor --check-api
"$PY" "$CLIENT" prepare --job "$JOB" --prompt-file "$PROMPT_FILE" --first-frame "$FIRST_FRAME" --last-frame "$LAST_FRAME" --duration 4 --resolution 720p --ratio 16:9
"$PY" "$CLIENT" host --job "$JOB"
"$PY" "$CLIENT" submit --job "$JOB"
"$PY" "$CLIENT" status --job "$JOB"
"$PY" "$CLIENT" download --job "$JOB"
```

只有首帧时省略 `--last-frame`；普通参考图时用 `--ref-image` 替代两个帧参数；文生视频时省略全部图片参数和 `host`。本机 `NXTPATH_MINIMAX_MODEL` 或显式 `--model` 仅可选择已支持的 H3 ID，不自动回退到其他通道。

## 交付

交付可播放的本地 `video.mp4` 和任务目录，用绝对路径展示视频。说明实际参数，以及是否审看了原速、动作和首尾；HTTP 成功不能证明视觉质量或角色一致性。接口支持首尾帧不等于逐像素保证，结果以实际视频为准。

提示词、签名图片 URL、任务句柄和响应保存在仅当前用户可读的记录中；不要整份贴进聊天或提交 Git。控制台仅展示任务句柄指纹。视频 Bearer 只发送到本网关的对应 artifact 句柄，跳转后的 HTTPS 媒体下载使用匿名请求。
