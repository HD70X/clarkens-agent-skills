# DSH Skills

本目录保存为 DeepSeek Harness（DSH）适配的 skill 源码。每个 `skills/<skill-name>/` 是一份完整目录，`SKILL.md` 在顶层；安装时复制或软链整个目录，不要只复制 `SKILL.md`。

## Skill 索引

| Skill | 用途 | 适配方式 |
| --- | --- | --- |
| [design-interrogator](skills/design-interrogator/SKILL.md) | 通用设计、方案和计划的澄清与风险审视 | 仅换文档保存位置与交付方式 |
| [product-design-interrogator](skills/product-design-interrogator/SKILL.md) | 产品和功能需求的分析与可验证假设 | 同上 |
| [requirements-discovery](skills/requirements-discovery/SKILL.md) | 澄清模糊需求、审查 PRD 缺口，形成范围与验收标准 | `read`、`ask_user_question` 工具名 |
| [iterative-development](skills/iterative-development/SKILL.md) | 按目标限时自动开发、独立验收和修复，达标收尾并交付人工复核 | 重写协作/执行参考，改用 goal、subagent、job、schedule |
| [minimax-video](skills/minimax-video/SKILL.md) | 通过 MiniMax 官方 H3 生成视频，支持首尾帧、多模态参考与跨对话续查下载 | 脚本原样，等待改用后台 job |
| [seedance-video](skills/seedance-video/SKILL.md) | 通过火山方舟或 BytePlus 官方 Seedance API 生成视频 | 脚本原样，等待改用后台 job |
| [tripo-model](skills/tripo-model/SKILL.md) | 通过 Tripo 生成、处理、续查与下载三维模型，默认 CN 站 | 脚本原样，长任务转后台 job |

未收录：`art-style-pack` / `art-asset-generation` 依赖生图后端，DSH 暂无内置生图能力；`deepseek-iterative-development` 的"Codex 统筹、DeepSeek 写码"前提在 DSH 中反转；`gemini-bridge` 需要本机 Gemini 凭据，暂未配置；`nxtpath-video` / `nxtpath-minimax-video` 仅用于哪都通旧任务续查，本机虽有 `~/.config/nxtpath/env`，但日常新任务用官方 minimax / seedance 版本；需要时再按同一方式移植。Office 文档能力由 DSH 内置的 `dsh-skill-office` 提供，不需要移植。

## 安装位置

DSH 的本地 skill 提供者按优先级扫描这些根：

| 优先级 | 来源 | 路径 |
| --- | --- | --- |
| 100 | 项目 DSH | `<项目根>/.dsh/skills` |
| 200 | 项目 agent 配置 | `<项目根>/.agents/skills` |
| 300 | 自定义 | `dsh-skill-filesystem` 的 `customSkillDirs` |
| 400 | 用户 DSH | `~/.dsh/skills` |
| 500 | 用户 agent 配置 | `~/.agents/skills` |

DSH 专属版本推荐放 `~/.dsh/skills`（全局）或 `<项目>/.dsh/skills`（项目级）。`.agents/skills` 是多个 agent 共用的命名空间，不要把仅适配 DSH 的指令放进去，避免与 Codex / Claude 的同名副本混用。

```sh
agent_skills_repo=$(git rev-parse --show-toplevel)
mkdir -p ~/.dsh/skills
for s in design-interrogator iterative-development minimax-video product-design-interrogator requirements-discovery seedance-video tripo-model; do
  ln -sfn "$agent_skills_repo/dsh/skills/$s" "$HOME/.dsh/skills/$s"
done
```

只识别顶层 `<name>/SKILL.md` 或 `<name>.md`，嵌套目录不会被发现。软链接可用，源码修改会直接反映到加载目录；文件监听会刷新目录，正文在每次加载时重新读取。

## 与其它平台的差异

- frontmatter 只使用 `name`、`description`、`whenToUse`、`metadata`、`disable-model-invocation`、`user-invocable`。Claude 的 `allowed-tools` 在 DSH 没有对应物，已移除。
- 工具名：读取用 `read`，提问用 `ask_user_question`，命令用 `bash`，交付用 `present`。
- 长任务：`bash` 单次调用有超时上限，超时转入后台 job；等待用 `job_output`，不把分钟级轮询塞进一个 shell 调用，也不用 `sleep` 占住回合。
- 自动续跑：`iterative-development` 用 `create_goal` 的自动续轮，定时需求才用 `schedule`；`run_control.py` 仍是预算与状态的权威。
- 子智能体：`subagent` / `subagent_fork` / `send_message` / `interrupt_agent`；模型与推理档位先用 `list_subagent_models` 核对再传参。
- 隔离：并行写代码用 `git worktree`（或环境提供的 worktree 工具），同一目录的不同子智能体不构成文件隔离。

## 验证

1. `~/.dsh/skills/<name>/SKILL.md` 存在且 frontmatter 有 `name`、`description`。
2. 新会话的 skill 目录出现该 skill，名称与目录一致。
3. 媒体/3D skill 先跑只读检查：`doctor --check-api`（MiniMax / Seedance）或 `doctor --json`（Tripo），确认凭据与连通性，不生成付费任务。
4. `iterative-development` 先跑 `python3 "<skill-dir>/scripts/run_control.py" --help`，再用一项真实小任务验证 `init` / `check` / `stop`。
5. 真实任务验证后保留证据；不要用"文件存在"代替行为验证。

## 维护规则

1. 本目录只放 DSH 版本；平台指令分别维护，不把 Codex 或 Claude 目录直接软链进来。
2. 脚本、参考和资源跟随 skill 目录整体维护，`references/` 下的共享验收标准与其它平台保持同源，改动需检查是否需要同步。
3. 新增或移除 skill 时同步更新本索引与仓库根目录 README。
4. 运行日志、生成任务、账户配置和凭证留在仓库外。
