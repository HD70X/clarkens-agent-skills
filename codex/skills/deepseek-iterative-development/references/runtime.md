# 执行与配置

脚本需要 Python 3.9+、Git 和支持独立 profile / codex exec 的当前 CLI。进程组停止支持 macOS/Linux；其他系统须报告能力缺口。

## 一次性准备

```bash
python3 <skill-dir>/scripts/configure_worker.py
python3 <skill-dir>/scripts/worker.py doctor
```

在用户 Codex 目录创建 `deepseek-worker.config.toml`、`model-catalogs/deepseek-worker.json` 和 `deepseek-worker.settings.json`。不改主配置、登录或原 skill。存在目标文件时默认拒绝覆盖；审查后显式传 `--replace` 才更新这三个生成文件。

从 DeepSeek 官方 Codex 页面提取模型元数据，丢弃示例系统提示并使用执行角色说明，不执行远程安装脚本。官网格式改变就失败，不猜 schema；`--catalog-source` 可使用已审阅本地目录 JSON。

macOS 默认钥匙串。用户在自己的终端运行，在隐藏输入提示中录入 key（-w 必须最后）：

```bash
security add-generic-password -U -a "$USER" -s codex-deepseek -w
```

command-backed auth 在 Codex 内部读取令牌。不要手动运行读取命令把 key 输出到聊天。首次读取可能出现系统授权提示。其他环境可配置 `--auth env`，由启动进程提供 `DEEPSEEK_API_KEY`；不写明文 key 到 skill、项目或 shell 历史。桌面进程未必继承终端环境，doctor 以实际环境为准。

`--model`、`--effort`、`--profile` 选择已确认配置。生成器验证目录支持的推理档位。执行时检查配置与目录摘要；人工修改后先核对，不默默使用不同后端。

执行器使用独立 profile，并在本进程关闭全局插件、连接器、记忆和自动 skill 说明注入，以减少主代理工具上下文的重复成本。保留配置加载，确保独立 provider 可解析；不要为省上下文直接使用 --ignore-user-config，某些 CLI 版本会同时丢失 provider 定义。项目指令和 execpolicy 仍由 CLI 处理，专业生产由 Codex 调用原 skill；确需额外工具的代码任务先明确能力和上下文成本。执行会话不另外持久化，任务证据留在输出目录。

## 每轮运行

用基础 `run_control.py` 创建唯一 state，沿用用户授权截止。未确认预算不自行指定小时数。合同和状态可放集成工作区，DeepSeek 在隔离工作树工作。

下面超时仅为格式样例，按本轮预算替换：

```bash
python3 <skill-dir>/scripts/worker.py prepare \
  --state /absolute/run/state.json --workspace /absolute/worker-worktree \
  --task-id postcards-app --attempt 1 --task-file /absolute/run/app-task.md \
  --allow RingTestApp/Postcards --allow RingTestAppTests/PostcardsTests.swift \
  --timeout-seconds 600 --output-dir /absolute/run/app-attempt-1 \
  --manifest /absolute/run/app-attempt-1.task.json
python3 <skill-dir>/scripts/worker.py run \
  --manifest /absolute/run/app-attempt-1.task.json --dry-run
python3 <skill-dir>/scripts/worker.py run \
  --manifest /absolute/run/app-attempt-1.task.json
```

prepare / dry-run 不调用模型。运行要求凭据、轮次、版本/工作区指纹有效。重试保留逻辑 task_id，增加 attempt，创建新契约及输出目录，并绑定已审查的现有成果；不覆盖旧回执，不重复派正常任务。

`receipt.json` 是结果，不是轮次 state，不自动登记验收通过。`events.jsonl`、`stderr.log`、`final.md` 保存实际执行信息，日志可能含源码，按项目证据保管。

修改审计包含 Git 状态（包括暂存变化）和未跟踪/被忽略的项目文件。大型依赖及缓存目录如 node_modules、Pods、.build、.venv、DerivedData 不遍历，但其中已跟踪文件的修改仍由 Git 检查；回执列出实际跳过目录。它不是文件级安全隔离，也不证明未发生网络或其他工作区外副作用。

运行中检查控制状态，暂停/停止/硬截止/范围改变会终止自有进程组。单任务超时若轮次仍允许工作，可返回接手信号；轮次硬截止只能收尾。完成后遗留子进程也清理，长期服务由协调者独立管理。

| 回执状态 | 行动 |
| --- | --- |
| completed_unreviewed | 查实际差异，冻结候选，独立验收 |
| needs_codex_takeover | 预算内由当前 Codex接手，检查失败与已有成果 |
| stopped | 仅收尾，不重派或接手开发 |
| stale | 审查范围变化及成果，明确新任务后执行 |

缺凭据/后端不可用会如实请求接手并标明未完成真实运行，不伪造模型调用。

## 来源

- [Codex profiles、provider 与命令凭据](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [Codex 非交互执行与 JSONL](https://learn.chatgpt.com/docs/non-interactive-mode)
- [DeepSeek 官方 Codex 接入](https://api-docs.deepseek.com/quick_start/agent_integrations/codex/)
