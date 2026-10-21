# 使用、任务授权与恢复

## 在 Codex 中使用

安装配置完成后可在任意项目明确调用，例如：

```text
$gemini-bridge 本任务允许调用 Gemini。我选择 gemini-4-argon，帮我审查当前改动，由 Codex 判断并整理结论。
```

```text
$gemini-bridge 本任务允许 Gemini 参与执行。我选择 gemini-4-argon，请它修改当前项目的这个问题并运行相关检查，由 Codex 验收。
```

上面的模型是用户在该次使用中的显式选择示例，不是安装或运行默认值。也可先说：

```text
$gemini-bridge 列出这台设备可访问的 Gemini 模型，我选择后再开始。
```

模型选择与任务授权分别处理；没有选模型时 Codex 会询问，没有任务授权时不会发送项目内容。一个 agent run 可以多轮调用相同模型而不逐轮询问；新 run 需要显式 `--model`。用户明确说“本任务都使用 X”时，后续 run 可以使用该选择；不会跨任务继承。

## CLI 示例

以下 macOS 示例假设已经安装到 `.codex/skills`。Windows 用 PowerShell 的 `$bridgeScript` 配合 `py -3` 执行相同子命令。实际脚本路径以安装器输出为准。

```bash
python3 "$HOME/.codex/skills/gemini-bridge/scripts/gemini.py" authorize \
  --root "$PWD" --mode both --user-approved \
  --approval '用户已明确允许当前任务使用 Gemini 咨询和执行'
```

该命令只记录已有的人类授权，不能用来代替询问缺失的授权。脚本自动使用 Codex 的 `CODEX_THREAD_ID`；如果宿主未提供该值，每个相关命令都显式加 `--task-id <本任务唯一ID>`。不要修改既有 `CODEX_THREAD_ID` 来复用别的聊天授权。

咨询，输入 UTF-8 文本任务文件，显式附加项目内文件：

```bash
python3 "$HOME/.codex/skills/gemini-bridge/scripts/gemini.py" ask \
  --root "$PWD" --model gemini-4-argon \
  --prompt-file /absolute/path/to/review-request.txt --file src/example.py
```

执行模式：

```bash
python3 "$HOME/.codex/skills/gemini-bridge/scripts/gemini.py" agent start \
  --root "$PWD" --model gemini-4-argon \
  --prompt-file /absolute/path/to/delegated-task.txt
```

`--prompt '简短请求'` 可替代 `--prompt-file`。多行请求优先文件。`--file` 可重复；只读 UTF-8 文件，单文件上限 256 KiB。不要把凭据、未授权项目内容或无关目录放进任务文件。文件不会被自动整体打包上传。

可选参数：`--max-output-tokens 1..32768`、`--thinking low|medium|high`、`--timeout <秒数>`。默认不发送 thinking 参数，让所选模型使用其官方行为；若显式选的 thinking 不受模型支持，API 错误原样说明，不暗改参数。API 超时默认 1200 秒，以容纳长推理。默认最多 20 个执行轮次，可在 start 时用 `--max-turns 1..100` 设置。

## 命令交回 Codex

Gemini `run_command` 是提案，返回 `needs_host`，不会在 Python 中启动 shell。Codex 先读取 `host_requests`，核对命令参数、目录、范围和现有权限，然后用自身命令工具执行。正常权限流程仍适用。

将实际结果保存为位于项目外的本机 UTF-8 JSON 文件，例如：

```json
{"exit_code": 0, "stdout": "3 tests passed", "stderr": ""}
```

每条请求提交一次；无法执行或越界则提交说明：

```json
{"error": "这条命令访问了授权项目之外的位置，因此没有执行。"}
```

```text
python <bridge> agent reply --run-id <run-id> --index <host-request-index> --result-file <result.json>
python <bridge> agent resume --run-id <run-id>
```

多个请求分别提交，然后 resume。单个结果最多 1 MiB，过长时由 Codex 保留与判断有关的输出摘录。`agent show --run-id <run-id>` 可查看剩余请求。续跑保留完整 function call ID 和 thought signature；不向用户展示内部思考内容。

## 状态与退出码

| 状态 | 含义与处理 |
| --- | --- |
| completed | 模型正常结束；执行模式仍需 Codex 独立验收 |
| needs_host | 待 Codex 提交实际命令结果或拒绝理由 |
| pending_tools / ready | 可在当前任务内 `agent resume`，已记录的文件工具结果不会重复执行 |
| requesting | 进程可能在 API 请求时中断；核对后用 `agent resume --retry` |
| error | API 错误已保存；排查后显式 `agent resume --retry`，不自动重复请求 |
| turn_limit | 已到轮数上限；确有必要时 `agent resume --more-turns 5` |
| incomplete | 输出截断、内容拦截或其他非正常结束；不能视为成功。明确调整同一模型请求后开始新 run，或由用户选择别的模型 |

退出码：0 表示成功或正常等待宿主；2 表示配置、授权、API 或参数错误；4 表示未完成、轮数上限等非成功终态；130 表示用户中断。不要仅凭退出码 0 宣称整个委派完成，应同时检查 `status`。

`generateContent` 是 Google 当前保留的官方接口，支持包括 Argon 在内的文本/工具调用；此实现没有依赖 Gemini CLI 或 Google 托管 agent。单次推理不自动做长解码续写，不支持图像/音频生成。API 参考：[函数调用](https://ai.google.dev/gemini-api/docs/generate-content/function-calling.md)、[生成接口](https://ai.google.dev/api/generate-content)。

## 撤销与清理

```text
python <bridge> revoke
python <bridge> remove-key
```

`revoke` 只撤销当前聊天的授权，之后不能续跑；`remove-key` 删除此设备凭据。撤销不能撤回已经发送的请求或已落盘的修改。停止相关 run 后可删除用户数据目录里的旧 `runs/<id>.json` 和锁文件；不要把这些文件提交或随安装包分发。
