---
name: nxtpath-video
description: 使用哪都通 / Nxtpath 的 Seedance 2.5 API，从参考图或文本生成视频，续查已有任务并下载成片。适用于图生视频、动画小样和视频返工；支持本地图片的私有 R2 托管。不用于静态图片生成或原生 SVG / rig 动画制作。
---

# 哪都通图生视频

用本 Skill 的独立 Python 客户端生成候选视频。默认模型为已实测的 `seedance-2.5`；制作流程不依赖 Bear 工程、其他工作树或 Claude 部署状态。

## 本机配置与执行入口

- 统一凭证为 `NXTPATH_API_KEY`，默认从环境变量或 `~/.config/nxtpath/env` 读取。环境变量优先，`NXTPATH_ENV_FILE` 可指定另一份私有配置。不要读取其他应用的聊天 token，不把密钥放入命令行、Skill、报告或任务记录。
- 新 zsh 进程由 `~/.zshenv` 加载本机配置；GUI 或旧进程没有继承环境时，客户端仍能直接读取上述文件。只报告配置是否存在，不展示内容。
- 从实际加载的 Skill 目录定位 `scripts/nxtpath_video.py`。优先使用 `~/.config/nxtpath/venv/bin/python`；其不存在时，HTTPS 参考图与视频 API 可用 Python 3.9+ 直接运行。本地图片托管还需要 `scripts/requirements.txt` 中的 boto3。
- 在目标项目先读适用的资源与隐私约定。任务默认放在该项目被忽略的 `tmp/artwork/generations/<run-id>/<asset-id>/<attempt-id>/`；无项目时用用户选定的输出目录。不要覆盖旧 attempt，不把候选自动加入构建或正式资源。

## 一次制作或恢复已有任务

用户已明确要求生成某条视频时，按该请求完成一次候选，不重复询问泛泛确认。仅询问路线、配置或 Skill 用法不授权付费生成。批量数量、返工次数和费用范围沿用本次用户约定；若未约定，先做一条，不自动扩大或重生成失败任务。

1. 运行 `doctor --check-api` 检查凭证和可用模型。这是只读请求，不生成视频。
2. 确认参考图与动作描述。明确动作阶段、镜头、构图、时长、需要保持的角色与道具；未指定的小样默认 4 秒 / 480p，不把默认低清小样当正式成片。原生帧率、角色一致性、首尾姿态和透明度以实际视频为准。
3. 把提示词保存为 UTF-8 文件，用 `prepare` 建立不可变输入。`--reference` 可重复传入本地 PNG/JPEG/WebP 或 HTTPS 图片 URL；这些是普通引导图，不能宣称 API 锁定了首尾关键帧。文本生成视频可不传参考图。
4. 存在本地图片时运行 `host`，将输入快照上传或复用在已配置的私有 R2 桶，签发 24 小时 GET 并核对下载哈希。此操作会把参考图传给托管服务及视频提供商；应在用户请求的素材范围内。托管失败时不要提交视频，不自动换账号、公开桶或服务。已有 HTTPS 参考图无需 `host`。
5. 仅运行一次 `submit`。它先持久化排他提交记录，再发出付费 POST。之后用 `status` 查询，成功后用 `download` 取得 `video.mp4`；各命令独立，不把分钟级等待藏在一个长 shell 调用里。等待期间使用宿主的可中断等待并保持进度沟通，不能因超时重发生成请求。
6. 跨对话恢复时使用原 job 路径，先 `inspect`，再 `status` / `download`。已有提交、结果不明或无任务 ID 的 attempt 均不得重复 POST；无任务 ID 时依据私有提交记录向提供方核对。下载失败只重试下载。401/403、额度不足或模型不可用时停止提交，报告原因，不自动换密钥、模型或接口。

命令示例（`CLIENT` 指实际 Skill 中的脚本；`PY` 指本机 Python；`JOB` 为此次新建任务目录）：

```sh
"$PY" "$CLIENT" doctor --check-api
"$PY" "$CLIENT" prepare --job "$JOB" --prompt-file "$PROMPT_FILE" --reference "$REFERENCE_IMAGE" --duration 4 --resolution 480p --ratio 1:1
"$PY" "$CLIENT" host --job "$JOB"
"$PY" "$CLIENT" submit --job "$JOB"
"$PY" "$CLIENT" status --job "$JOB"
"$PY" "$CLIENT" download --job "$JOB"
```

## 交付与边界

以可播放的本地视频和 job 路径交付，说明它是候选以及实际检查过的内容。用绝对路径展示视频；需要审看时通过现有媒体工具检查原速、关键动作及首尾，不把 HTTP 成功等同于动作或美术通过。

任务记录包含提示词、输入快照、精确请求、提供方任务句柄、结果和文件哈希，权限默认仅当前用户可读；这些记录可能含临时签名 URL，不能整份贴进聊天或提交 Git。控制台只展示任务句柄指纹。透明去底、SVG 衔接和 App 接入属于后续制作，按目标项目的工具与授权处理。

更换设备、更新凭证或托管失败时才读 [配置与故障恢复](references/configuration.md)。接口依据见 [提供方 Seedance Skill](https://github.com/NaDouTongToken/nxtpath-skills/tree/main/nxtpath-seedance-video)。
