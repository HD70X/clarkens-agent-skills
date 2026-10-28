# 哪都通 MiniMax H3 接口依据

核对日期：2026-10-26。

## 来源与验证范围

- [哪都通官方 skill](https://github.com/NaDouTongToken/nxtpath-skills/blob/main/nxtpath-minimax-video/SKILL.md)，核对时文件 Git blob SHA：`2e9efe16c6319fee83348eb8ef4ec4c07cf7135e`。
- [提供方 Python 客户端](https://github.com/NaDouTongToken/nxtpath-skills/blob/main/nxtpath-minimax-video/scripts/nxtpath_minimax_video.py)，核对时文件 Git blob SHA：`8f5128847d1dc3b9c4c87e3681c1dcf3ce946003`。
- 使用本机私有配置执行 `GET https://api.nxtpath.ai/v1/models` 成功，目录确实返回 `minimax/minimax-h3`。未在创建本 skill 时发起付费生成，因此成片质量、实际首尾帧表现与 MiniMax 媒体跳转尚未经真实生成验证。

本客户端根据上述请求结构改写自本机 `nxtpath-video` 的可恢复任务客户端。保留统一凭据与私有 R2 托管，不依赖其他 skill 的安装文件；没有沿用提供方脚本的其他应用凭证搜索、长时间单进程轮询或临时 OSS 自动上传。

## 生成请求

`POST /v1/tasks/submit`，头为 `Authorization: Bearer …`、`Content-Type: application/json`、`Idempotency-Key: <持久化 UUID>`。

```json
{
  "model": "minimax/minimax-h3",
  "input": {
    "content": [
      {"type": "text", "text": "角色缓慢转头，镜头固定。"},
      {
        "type": "image_url",
        "image_url": {"url": "https://example.com/first.png"},
        "role": "first_frame"
      }
    ]
  },
  "parameters": {"resolution": "720p", "duration": 4, "ratio": "16:9"}
}
```

| 项 | 已核对规则 |
|---|---|
| 模型 | `minimax/minimax-h3`，不使用未经核实的 Hailuo 别名 |
| 时长 | 4–12 整数秒，默认 4 |
| 分辨率 | `720p`、`960p`、`2k`，默认 `720p`；客户端忽略大小写并规范化 |
| 比例 | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16`，默认 `16:9` |
| 首尾帧 | `role` 在 image content part 的顶层，分别为 `first_frame` / `last_frame`，各至多一张；允许仅首帧或仅尾帧 |
| 普通参考图 | 相同 image part，省略 `role`；与首尾帧互斥 |
| 参考音视频 | 此通道拒绝，客户端不暴露对应参数 |

服务按秒数和分辨率档位计费，普通参考图超出免费张数可能附加计费；首尾帧不计作普通参考图。本 skill 不写死价格或承诺固定生成时间。

## 查询与下载

- 创建响应句柄：`output.task_id`，不是 OpenAI 或 MiniMax 直连接口的 `id`。
- 查询：`GET /v1/tasks/status?task_id=<URL 编码的句柄>`；状态字段为 `output.task_status`，区分大小写。
- 状态：`Pending`、`Running`、`Success`、`Failure`、`Expired`。
- `Success` 的 `output.urls[0]` 指向本网关认证下载句柄 `/v1/tasks/artifacts/{task_id}/0`。兼容以 `/v1/…` 开头的同源相对路径；拒绝外部 URL 冒充认证句柄。
- 只有第一跳本网关句柄携带 Bearer，后续跳转须为 HTTPS 且使用全新匿名请求，最多跟随五次跳转。私有记录保存跳转链。
- 提供方说明 artifact 句柄约 23 小时有效且过期后不能刷新。优先及时下载；过期时报告，不自动重新生成。

`prepare` 的 `manifest.json` 及本地快照有哈希；`submit` 先排他保留 `submission.json`，随后写冻结请求，最后只发送一次付费 POST。网络异常、5xx、408、409 或未返回句柄保留 `unknown`；不宣称网关一定未创建任务。返回已收到但最终记录未完成时，可从 `submit-response.json` 恢复句柄。

## 本地实现范围

本技能的本地图片路径支持 PNG/JPEG/WebP、单张 20 MiB，HTTPS URL 不在 prepare 时抓取。普通参考图数量上限没有在已核对资料中明确，因此不虚构限制；大批参考图应先确认费用范围。没有暴露未经核实的帧率、音频开关、seed 或像素级关键帧保证。
