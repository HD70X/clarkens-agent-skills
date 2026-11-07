# 配置与恢复

## 本机配置

在所选站点的项目空间创建或取得 API Key，并开通要调用的 Seedance 模型。[火山方舟 API Key 管理](https://ark.volcengine.com/region:cn-beijing/apikey) · [BytePlus API Key 管理](https://ai.byteplus.com/ark/region:ap-southeast-1/apikey)

macOS 的隐藏输入配置与只读检查如下。`CLIENT` 为 Skill 内 `scripts/seedance_video.py` 的绝对路径。其他系统在交互终端省略 `--gui`，使用隐藏输入。

```sh
python3 "$CLIENT" configure --gui
python3 "$CLIENT" doctor --check-api

python3 "$CLIENT" --region global configure --gui
python3 "$CLIENT" --region global doctor --check-api
```

- 两站的密钥分别保存在 `~/.config/seedance/cn/api-key` 和 `~/.config/seedance/global/api-key`。POSIX 下由客户端创建为 600 权限。新任务默认国内；可在子命令前加 `--region global`，或设置 `SEEDANCE_REGION=global`。
- 当前进程的 `ARK_API_KEY` 优先用于 `SEEDANCE_REGION` 所属的站点，未设置时视为国内 Key。显式选择另一站点时使用该站点的本机文件。运行 `configure --from-env` 可将已有环境变量保存到所选站点。轮换本机密钥时加 `--replace-key`，并更新或清除进程中优先级更高的旧环境变量。
- `doctor` 可离线检查配置。加 `--check-api` 会读取一条任务列表记录以核验鉴权。所选模型的开通、项目权限及计费状态在官方控制台核对。[火山方舟任务列表接口](https://docs.volcengine.com/docs/ark/list-video-generation-tasks-api?lang=zh) · [BytePlus 任务列表接口](https://docs.byteplus.com/en/docs/modelark/list-video-generation-tasks-api)

## 续查与处理异常

| 现象 | 操作 |
| --- | --- |
| 已有本地任务目录 | 用 `inspect --job "$JOB"` 看保存的状态，再用 `status` 或 `download`。客户端沿用原站点。 |
| 只有官方任务 ID | 在原站点和项目验证 ID，用 `recover --job "$NEW_JOB" --task-id "$ARK_TASK_ID"` 导入，再续查或下载。 |
| 提交出现网络超时、5xx 或未取得有效 ID | 将 `submission.json` 视为结果未知。保留原目录，用 `tasks` 或官方控制台核对。只有在官方控制台核实对应的任务 ID 后才导入；相近的创建时间或同一模型只能作为线索。 |
| 提交被拒绝或任务失败 | 看返回的错误码，需要详细原因时在本机读 `submission.json` 或 `result.json`。401/403 核对当前项目和站点 Key；参数、素材、开通、配额问题按官方提示处理。另一次付费尝试需要使用新目录并遵循用户对次数的约定。 |
| 视频链接过期或下载中断 | 再运行 `download` 获取当前查询结果。若当前链接仍不可用，保留任务 ID 和状态，到官方控制台处理。已成功落盘的文件可以凭本地哈希复核。 |

普通任务 ID 的有效期为 7 天，成片链接通常为 24 小时。从用户提供的官方 Draft 任务 ID 导入时，按官方记录查看有效期。成功后及时保存成片。[火山方舟查询接口](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh) · [BytePlus 查询接口](https://docs.byteplus.com/en/docs/modelark/get-video-generation-task-api)
