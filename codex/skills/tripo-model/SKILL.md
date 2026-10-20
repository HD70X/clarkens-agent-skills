---
name: tripo-model
description: 使用 Tripo API 从文字、单图或多视图生成三维模型，处理已有网格并续查下载产物，默认使用 CN 国内站。适用于 Tripo 建模、贴图、重拓扑、格式转换及自动绑定；精确参数化建模使用 Blender。
---

# Tripo 建模

通过官方 Tripo CLI 生成实际模型文件。入口 `scripts/tripo.py` 自动加载本机私有凭据，默认 CN；区域、密钥和执行记录不写入 Skill 源码。已有三维风格包、参考图和目标引擎要求作为本次输入使用，不要求先创建新风格包。

## 执行入口

- `CLIENT` 指本 Skill 实际目录中的 `scripts/tripo.py`；使用 Python 3.9+，官方 CLI 需要 Node.js 20+。
- 默认读取 `~/.config/tripo-skill/config.json` 指向的 Markdown 凭据文件。只运行脚本检查配置，不在终端显示、复制或搜索密钥内容。
- 运行 `python3 "$CLIENT" -- doctor --json` 检查鉴权、网络和余额；`balance --json` 是只读余额查询，不生成或扣费。
- 缺少依赖、切换地区、移动凭据时读 [本机配置](references/configuration.md)。其他命令和参数按需通过 `python3 "$CLIENT" -- docs --topic commands/make`、`commands/generate`、`commands/process`、`commands/task` 查看已安装 CLI 的文档。

## 制作一个模型

用户明确要求生成或处理模型时，完成其授权范围内的任务，不重复要求泛泛确认。仅检查连接、安装 Skill 或咨询用法不授权付费生成。数量未指定时做一个候选；不把批量、额外候选、自动返工或付费后处理当成默认步骤。

1. 理解主体、参考图、用途、面数、贴图、尺寸与输出格式。读取用户给定的参考和既有风格规则；常规细节合理补齐，只有影响身份、成本或兼容性的关键歧义才澄清。
2. 在目标项目的已忽略工作目录建立本次输入与输出位置，例如 `tmp/tripo/<asset>/<attempt>/`，保存提示词、输入参考及制作要求。用绝对路径传本地素材；文件会上传给 Tripo，不另建公开图床。输出不要写入 Skill 目录或覆盖原模型。
3. 默认直接生成一个带标准贴图的网格，不附加处理链。高精度用 `tripo-v3.1`；明确低面数或面数预算不超过 20,000 时用 `tripo-p1`。按项目需要填写面数；不为所有项目硬套同一预算。`tripo-p2` 为 Preview，仅在用户选择或确需其四边面能力时使用，并说明版本状态。保存模型与参数；需要复现时分别固定 `model_seed`、`image_seed`、`texture_seed`，只固定几何种子不保证文字转图和材质相同。
4. 对完整命令先加 `--dry-run --json`，检查 `valid`、`steps[].payload`、`candidates`、`pending_uploads`、`warnings`。确认每个 API 调用都在本次范围内；不要忽略 CLI 删除不支持参数的警告。`--for` 预设可能包含再次贴图、绑定和转换等额外收费步骤，只有整条链符合用户要求才采用。种子、提示词、模型与参数在真正提交时保持一致。
5. 正式执行时去掉 `--dry-run`，加包装器参数 `--record-dir <全新目录>`。包装器在启动 CLI 前创建排他记录，并保存脱敏 stdout、stderr 和退出状态；同一记录目录不能再次发起操作。默认 `make` 会阻塞至完成并下载，等待 shell 会话时保持进度沟通，不因工具返回 session ID 就重发命令。
6. 读最终 JSON 和本地文件：`status=success` 只证明任务成功。检查 `model_file` 是否实际存在，查看真实预览图；没有文件时只重试下载。检查轮廓、侧背面、贴图、面数、原点和用途相关问题。需要精修时在 Blender 导入副本，保存 `.blend`；已有模型制作 Skill 可承接其风格、绑定及目标引擎验证规则。
7. 交付模型、贴图、预览、`task.json` 与执行记录位置，并报告实际消耗积分、模型版本和做过的检查。截图和官方预览不替代动画变形或目标引擎验收；没有真实测试就保留相应限制。

命令形状（路径变量由当前项目确定，`RUN` 必须是全新目录）：

```sh
# 无扣费规划；seed 和 face_limit 按本次制作选择
python3 "$CLIENT" -- make "$PROMPT" --model tripo-p1 --seed 12345 -p face_limit=3000 --dry-run --json

# 一次正式生成，默认等待并下载
python3 "$CLIENT" --record-dir "$RUN" -- make "$PROMPT" --model tripo-p1 --seed 12345 -p face_limit=3000 -o "$OUT" --json

# 单图或多视图：换成实际素材绝对路径，先执行同样的 dry-run
python3 "$CLIENT" --record-dir "$IMAGE_RUN" -- make "$FRONT_IMAGE" "$BACK_IMAGE" --model tripo-v3.1 -o "$OUT" --json
```

`make -o "$OUT"` 的实际产物一般位于 `$OUT/tripo-out/<name>-<task-prefix>/`；从结果 JSON 读取真实路径，不假设模型直接写在 `$OUT` 下。若使用 `--no-wait`，只提交一次并记住 task_id，后续用 `task watch`；不要对尚未执行完的多步处理链使用它。

## 续查、下载与后处理

```sh
python3 "$CLIENT" -- history --json
python3 "$CLIENT" -- task get "$TASK_ID" --json
python3 "$CLIENT" -- task watch "$TASK_ID" --download -o "$DOWNLOAD_DIR" --json
python3 "$CLIENT" -- task get "$TASK_ID" --download -o "$DOWNLOAD_DIR" --json
```

`task get/watch -o` 指直接下载目录，与 `make -o` 的含义不同。`watch --json` 输出 NDJSON 进度事件，最后一行是最终结果。输出下载链接会过期，重新查询后下载，不把签名 URL 当永久资产。跨对话优先使用记录中的明确 task_id；`@last` 是当前区域最近成功任务，`@last:any` 才包含未完成项。

转换、重拓扑、贴图、绑定等也会消耗积分；按需查 `commands/process`，每次付费调用使用新的 `--record-dir`。例如：

```sh
python3 "$CLIENT" --record-dir "$PROCESS_RUN" -- mesh decimate "$TASK_ID" --model v3.0 --face-limit 3000 --smart-uv -o "$OUT" --json
python3 "$CLIENT" --record-dir "$CONVERT_RUN" -- model convert "$TASK_ID" --format FBX --fbx-preset blender -o "$OUT" --json
```

绑定前先用 `anim check` 检查适用性，免费检查也使用新的 `--record-dir` 记录。静态模型不默认添加骨架或动画；四边面不能直接按 GLTF/GLB 保存，应按 CLI 规划选择 FBX 等格式。生成后还要处理时，轴向在最后一步转换，避免生成阶段轴向参数导致后续结果方向不一致。

## 失败恢复

- 退出码 2：检查参数或配置；3：鉴权；4：额度；5：内容；6：任务失败或等待超时；7：网络；8：资源不存在；9：限流。先读具体错误，不自动切区、切模型或换账号。
- 提交遇到超时、断网或 5xx，任务可能已经接受。保留该次记录，查余额冻结项、历史及控制台；没有 task_id 时不盲目重发。包装器不重试整条命令；官方 CLI 只对明确限流拒绝重试任务创建。
- 有 task_id 就续查。等待超时不代表取消，服务端仍可能继续运行；下载失败也不意味着生成失败。
- `--record-dir` 已存在则拒绝启动。续查不需要新生成；只有用户授权新的尝试时才创建新的生成记录。批处理默认禁用自动重试失败项，除非明确区分安全查询重试与新的付费生成。
