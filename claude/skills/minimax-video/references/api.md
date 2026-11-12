# MiniMax 官方 H3 V2 接口依据

核对日期：2026-11-04。来源为官方[国内站创建接口](https://platform.minimax.cn/docs/api-reference/video-generation-v2-create)、[国际站创建接口](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)、[任务查询](https://platform.minimax.cn/docs/api-reference/video-generation-v2-query)、[任务列表](https://platform.minimax.cn/docs/api-reference/video-generation-v2-list)及[视频指南](https://platform.minimax.cn/docs/guides/video-generation)。本客户端覆盖生成、查询和下载；再生成、Context-IR、删除/取消不在此版本范围。

## 生成参数

`POST /v2/video_generation`，Bearer 鉴权。顶层为 model、content、duration、resolution、ratio；不使用哪都通的 input.content / parameters 包装。

```json
{
  "model": "MiniMax-H3",
  "content": [
    {"type": "text", "text": "人物缓慢转头，固定镜头，保持服饰一致。"},
    {"type": "image_url", "image_url": {"url": "https://example.com/first.png"}, "role": "first_frame"}
  ],
  "duration": 4,
  "resolution": "768P",
  "ratio": "adaptive"
}
```

成功返回顶层 task_id。所核对官方文档没有承诺 Idempotency-Key 去重，本地独占记录只防止本客户端重发。

| 模型 | 分辨率 | 整数秒数 |
| --- | --- | --- |
| MiniMax-H3 | 768P / 2K | 4–15 |
| MiniMax-H3-Highspeed | 480P / 768P | 4–15 |
| MiniMax-H3-Lite | 480P / 768P | 4–15 |
| MiniMax-H3-Max | 480P / 768P | 5–15 |

具体比例：21:9、16:9、4:3、1:1、3:4、9:16。文生视频必须具体比例；首尾帧始终由输入决定、使用 adaptive；参考生成可自适应或指定比例，Lite 参考模式必须具体比例。

文本必填且最多 7000 字符。首/尾帧各 ≤1。官方组合说明列出仅尾帧，但 role 简述同时称尾帧需成对，存在措辞不一致；客户端按组合说明接受仅尾帧，未做付费验证，不保证逐像素还原。

参考角色必须显式为 reference_image / reference_video / reference_audio，不能与 first_frame / last_frame 混用。否则无 role 单图可能被当作首帧。

## 输入媒体

| 媒体 | 格式及单文件大小 | 数量与时长 |
| --- | --- | --- |
| 图片 | JPEG/PNG/WebP/HEIC/HEIF，≤30 MB | 参考 ≤9；首/尾各 ≤1 |
| 视频 | MP4/MOV，H.264/H.265，内嵌 AAC/MP3，≤50 MB | ≤3，每段 2–15 秒、合计 ≤15 秒 |
| 音频 | WAV/MP3，≤15 MB | ≤3，每段 2–15 秒、合计 ≤15 秒 |

混合参考 ≤12 个文件。图片和视频每边 256–5760 px、宽/高 0.4–2.5；视频帧率 23.976–60。客户端按十进制 MB 检查；可读本地媒体做实际校验，远程媒体由官方最终验证。

官方接受媒体 URL、mm_file://{file_id}、data URI。本地输入由客户端构造 inline Base64 或使用显式 R2；无需把 Base64 放进命令行。官方 inline 视频声明为 data:video/mp4，本地 MOV 用 R2/HTTPS/mm_file。请求体总计 ≤64 MB，Base64 约放大三分之一。

## 可选项

- --aigc-watermark / --no-aigc-watermark：官方布尔参数，不指定时沿用服务默认。
- --callback-url：仅用用户提供的 HTTPS 地址，已有回调服务须在 3 秒内返回官方 challenge。
- --prompt-expansion-mode disabled|balanced|quality：只用于 H3-Max，写入 extra.prompt_expansion_mode，默认由官方选择 balanced。

不虚构 seed、输出帧率控制或通用音频开关。完整参数以最新官方文档为准。

## 查询与计量

- 单任务 GET /v2/query/video_generation/{task_id}，响应 task.id、task.model、task.status。客户端校验 ID、模型和状态。
- 状态 queued / running / succeeded / failed / cancelled。成功媒体在 task.content.url，限时 URL 可重查刷新；仅可查最近 7 天。
- 列表 GET /v2/query/video_generation?page_num=1&page_size=20，支持 filter.status / filter.model；仅读列表不证明生成权限。
- 成片 URL 及所有跳转均匿名 HTTPS，API Key 不发给 CDN 或回调。
- task.usage 可包含输出秒数、参考视频秒数、图片数、参考音频秒数及折算 token。参考音视频可能增加用量，不固定价格、不按聊天 token 价格推算视频费用。

## 验证范围

安装验证覆盖离线行为测试、官方任务列表只读鉴权和可选 R2 只读连通。未经付费生成，不声称已验证具体模型生成权限、声音、首尾帧、耗时或画质。真实生成证据保留在任务目录，不写入源码。
