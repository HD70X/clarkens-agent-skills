# Antigravity Skills

本目录保存为 Google Antigravity（Gemini 4 Argon）适配的 skill 源码。每个 `skills/<skill-name>/` 目录包含 `SKILL.md` 和配套的 `references/`、`scripts/`、`assets/` 等文件；安装时使用完整目录或符号链接。

## Skill 索引

| Skill | 用途 |
| --- | --- |
| [art-asset-generation](skills/art-asset-generation/SKILL.md) | 按已有 Style Pack（支持本平台或 Codex 跨模型创建的 Pack）生成或返工栅格素材 |
| [art-style-pack](skills/art-style-pack/SKILL.md) | 建立、校准和维护跨平台通用的栅格画风包（Style Pack） |
| [design-interrogator](skills/design-interrogator/SKILL.md) | 通用设计、方案和计划的澄清与风险审视 |
| [iterative-development](skills/iterative-development/SKILL.md) | 按目标限时自动开发、独立验收和修复，达标收尾并交付人工复核 |
| [nxtpath-minimax-video](skills/nxtpath-minimax-video/SKILL.md) | 通过哪都通 MiniMax H3 生成视频，支持首尾帧、参考图和跨对话续查下载 |
| [nxtpath-video](skills/nxtpath-video/SKILL.md) | 通过哪都通 Seedance 2.5 从参考图生成视频，保留任务并跨对话续查下载 |
| [product-design-interrogator](skills/product-design-interrogator/SKILL.md) | 产品和功能需求的分析与可验证假设 |
| [requirements-discovery](skills/requirements-discovery/SKILL.md) | 澄清模糊需求、审查 PRD 缺口，形成范围与验收标准 |
| [tripo-model](skills/tripo-model/SKILL.md) | 默认 CN，通过 Tripo 生成、处理、续查与下载三维模型，私有凭据由本机配置引用 |

## 平台适配要点

- **提问与文档交付**：使用 `read_file` 读取文档、图像和 `.mp4` 视频；有限选项提问使用 `ask_question`，开放式访谈使用正文提问并等待；超过 2–3 轮的临时笔记存放在会话 `scratch/` 目录，正式交付提供可点击的 `file://` 链接。
- **自动迭代与子智能体**：`iterative-development` 使用 `invoke_subagent`（`research` / `self` 及 `Workspace="branch" | "share"` 隔离工作区）、`send_message`、`manage_subagents`、`manage_task` 与 `schedule` 定时器，复用与 Claude / Codex 版一致的 `scripts/run_control.py` 和验收标准。
- **跨模型通用 Style Pack（`art-style-pack` & `art-asset-generation`）**：`pack.yaml`、`style.md`、`evidence.yaml` 与 `.art-workflow.yaml` 格式与 Codex 版 100% 兼容。Antigravity 版通过内置 `image-generator` 子智能体生图，并强制将 Pack 内的必需参考图与获批校准图绝对路径作为视觉锚点传入，确保跨模型（Codex <-> Antigravity）复用同一套 Style Pack 时画风一致。
- **视频与 3D 资产**：`nxtpath-video`、`nxtpath-minimax-video` 和 `tripo-model` 共享本机私有配置（`~/.config/nxtpath/env` 与 `~/.config/tripo-skill/config.json`），等待任务使用 `schedule` 定时器或后台任务唤醒机制（严禁使用 shell `sleep` 或因后台化重复提交付费请求），成片直接通过 `read_file` 多模态审看。

## 源码路径与安装位置

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 仓库源码 | `<repo>/antigravity/skills/<skill-name>` | 编辑、版本管理和跨设备同步 |
| 全局加载位置（推荐） | `~/.gemini/config/skills/<skill-name>` | 对本机所有 Antigravity 工作区生效 |
| 项目级加载位置 | `<项目根目录>/.agents/skills/<skill-name>` | 仅对单个项目生效 |

在 macOS 的仓库目录中运行以下命令，将 Antigravity 的全局 skill 指向当前 checkout。

```sh
agent_skills_repo=$(git rev-parse --show-toplevel)
mkdir -p ~/.gemini/config/skills
for s in art-asset-generation art-style-pack design-interrogator iterative-development nxtpath-minimax-video nxtpath-video product-design-interrogator requirements-discovery tripo-model; do
  ln -sfn "$agent_skills_repo/antigravity/skills/$s" "$HOME/.gemini/config/skills/$s"
done
```
