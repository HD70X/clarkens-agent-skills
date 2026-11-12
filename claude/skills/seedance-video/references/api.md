# 官方接口与参数

## 服务和模型

国内火山方舟使用 `https://ark.cn-beijing.volces.com/api/v3`，国际 BytePlus ModelArk 使用 `https://ark.ap-southeast.bytepluses.com/api/v3`。创建与查询共用 `/contents/generations/tasks` 路径，查询单个任务追加 `/{id}`。创建返回顶层 `id`，查询返回顶层 `status`，成功时从 `content.video_url` 取得视频。[火山方舟创建](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh) · [火山方舟查询](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh) · [BytePlus 创建](https://docs.byteplus.com/en/docs/modelark/create-video-generation-task-api) · [BytePlus 查询](https://docs.byteplus.com/en/docs/modelark/get-video-generation-task-api)

| `--model` | 火山方舟 Model ID | BytePlus Model ID | 时长 | 分辨率 |
| --- | --- | --- | --- | --- |
| `2.5` | `doubao-seedance-2-5-260628` | `dreamina-seedance-2-5-260628` | 4–30 秒 | 480p、720p、1080p |
| `2.0` | `doubao-seedance-2-0-260128` | `dreamina-seedance-2-0-260128` | 4–15 秒 | 480p、720p、1080p、4k |
| `2.0-fast` | `doubao-seedance-2-0-fast-260128` | `dreamina-seedance-2-0-fast-260128` | 4–15 秒 | 480p、720p |
| `2.0-mini` | `doubao-seedance-2-0-mini-260615` | `dreamina-seedance-2-0-mini-260615` | 4–15 秒 | 480p、720p |

`--model` 可填写简称或当前站点的完整 ID。已创建的推理接入点可使用 `--model 2.5 --endpoint-id ep-...`，其中 `--model` 负责选择本地校验规则，应与接入点实际模型对应。`--duration -1` 由模型根据任务类型决定时长；固定长度用整数秒。[火山方舟模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh) · [BytePlus 模型列表](https://docs.byteplus.com/en/docs/modelark/model-list)

## 输入与模式

- 图片支持 PNG、JPEG、WebP、BMP、TIFF、GIF、HEIC、HEIF。每张小于 30 MB，宽和高各 300–6000 像素，宽高比 0.4–2.5。
- 音频支持 WAV、MP3，每段不超过 15 MB。图片和音频可使用本地文件、HTTPS URL 或 `asset://` ID。本地文件按官方小写 MIME 的 data URI 内嵌，请求体连同 Base64 及 JSON 最多 64 MB。
- 视频参考使用 MP4 或 MOV 的 HTTPS URL 或 `asset://` ID。单个不超过 200 MB，24–60 fps。容器编码及像素范围见创建接口的 `content.video_url`。
- 2.5 全模态模式最多 30 张参考图、10 段视频和 10 段音频，支持只用音频。视频和音频各自总时长最多 30 秒，单段至少 2 秒，待编辑视频至少 4 秒。
- 2.0 系列最多 9 张参考图、3 段视频和 3 段音频，视频和音频各自总时长最多 15 秒，单段至少 2 秒。音频参考需搭配图片或视频。
- `--ratio` 支持 16:9、4:3、1:1、3:4、9:16、21:9、adaptive。2.5 的首帧／首尾帧模式使用 adaptive，输出比例随首帧。

客户端在本地检查模式、数量、文件扩展名和请求大小。输入的具体媒体格式、分辨率、时长、真人肖像与远程可达性由官方接口校验。[火山方舟视频教程](https://docs.volcengine.com/docs/ark/video-generation-tutorial?lang=zh) · [BytePlus 视频教程](https://docs.byteplus.com/en/docs/modelark/video-generation-tutorial)

## 2.5 参考、编辑与延长

基于素材生成新视频时可传 `--omni-type reference`。编辑和延长需要 `--ref-video`，分别用 `--omni-type edit` 和 `--omni-type extend`，比例由原视频决定。编辑自动用 `--duration -1` 跟随源视频；延长应在提示词里指定向前或向后及续写内容。显式指定任务类型可以提前校验参数，提示词意图仍须与之匹配。[火山方舟 Seedance 2.5](https://docs.volcengine.com/docs/ark/seedance-2-5?lang=zh) · [BytePlus Seedance 2.5](https://docs.byteplus.com/en/docs/modelark/seedance-2-5)

声音默认开启，可用 `--no-audio`。可选 `--watermark`、`--return-last-frame`，后者在成功时额外下载 `last-frame.jpg`。2.5 可选 `--output-format mov`。2.5 的 1080p 和 2.0 的 4k MP4 为 10-bit HEVC，播放环境需要对应解码能力。[火山方舟输出参数](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)
