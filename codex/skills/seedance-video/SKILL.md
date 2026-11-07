---
name: seedance-video
description: 通过火山方舟或 BytePlus ModelArk 的官方 Seedance API 生成视频，支持文生视频、首帧或首尾帧、多模态参考、任务续查和下载。用于 Seedance 官方 API 配置及恢复官方任务；明确指定哪都通或恢复哪都通任务时使用 nxtpath-video。
---

# Seedance 官方视频

从实际 Skill 安装目录调用 `scripts/seedance_video.py`，使用 Python 3.9+ 标准库。默认使用国内火山方舟 Seedance 2.5。国际站使用 BytePlus ModelArk，创建和导入时在子命令前加 `--region global`。同一任务在创建它的站点和项目下续查。

## 配置与素材

- 使用所选站点的 `ARK_API_KEY`。macOS 可运行 `configure --gui` 通过隐藏输入保存密钥；其他系统在用户终端运行 `configure`。用户应在隐藏输入框或终端录入密钥。区域与轮换方式见[配置与恢复](references/configuration.md)。
- `doctor --check-api` 仅读任务列表，用来验证连接与鉴权。用户明确要求制作视频时按约定提交，通常先做一条候选；创建 Skill、查文档、配置与检查连接都属于提交前的工作。
- 默认 4 秒、480p、MP4、有声。文本默认 16:9，有素材时默认 `adaptive`。选择其他模型、使用多模态参考或编辑／延长视频时先读[官方接口与参数](references/api.md)。
- 用 `--first-frame` 指定首帧，按需加 `--last-frame`。全模态参考使用可重复的 `--ref-image`、`--ref-video`、`--ref-audio`，与首尾帧模式分别使用。保留每类素材的输入顺序，在提示词中用 `@图像1`、`@视频1`、`@音频1` 指明用途。
- 本地图片和音频可在请求内嵌入 Base64。视频参考使用方舟可访问的 HTTPS URL 或同一项目的 `asset://` 素材 ID。对于较大文件，使用已有的 HTTPS 链接或官方素材库。已授权真人素材按官方肖像流程取得素材 ID。临时链接须在任务实际处理时仍可访问。

## 生成和续查

每条候选使用新任务目录，优先选用户指定位置或项目中被忽略的生成目录。保存 UTF-8 提示词，写清动作、镜头、需保持的角色和道具、声音要求。纯文本提供提示词，参考模式可只传素材。

1. 用 `prepare` 离线保存确切请求、内嵌素材和请求哈希。它会检查参数组合与内嵌大小，素材的编码、尺寸和时长按官方限制核对。
2. 用 `submit` 提交一次。客户端在发送付费 POST 前独占保存提交记录。同一个任务目录此后只用于续查或下载；失败或连接中断时保留原记录。
3. 用 `status` 独立查询。任务为 `queued` 或 `running` 时用宿主可中断等待，按间隔再查。成功后立即用 `download` 落盘；失败、取消或超时时查看官方错误码并保留任务记录。
4. 跨对话恢复先 `inspect` 再 `status` / `download`。如果只有从官方控制台核实的 `cgt-` 任务 ID，用 `recover --job <新目录> --task-id <官方任务ID>` 只读导入。提交结果不明时按[配置与恢复](references/configuration.md)核对。

```sh
python3 "$CLIENT" doctor --check-api
python3 "$CLIENT" prepare --job "$JOB" --prompt-file "$PROMPT" --first-frame "$FRAME"
python3 "$CLIENT" submit --job "$JOB"
python3 "$CLIENT" status --job "$JOB"
python3 "$CLIENT" download --job "$JOB"
```

`CLIENT` 为 Skill 内脚本的绝对路径。纯文本省略 `--first-frame`。通过 `prepare --help` 查看参数。

## 交付

交付本地视频与任务目录的绝对路径，按实际结果说明模型、时长、比例、分辨率和声音。说明已做的媒体验证与人工审看；结构校验和 SHA-256 用于确认文件完整性，画面和声音按实际播放验收。

任务目录含提示词、内嵌素材、签名 URL 及真实任务 ID，保存在本机私有位置。分享状态时使用控制台输出的指纹。API Key 仅用于所选官方站点，下载请求及跳转均使用匿名 HTTPS。
