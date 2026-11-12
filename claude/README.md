# Claude Skills

本目录保存为 Claude 桌面版 / Cowork / Claude Code 适配的 skill。源码位于 `skills/`，上传包位于 `packages/`。本库 Claude 与 Codex 版本分别维护，不能将 Codex 目录或指令直接作为 Claude 版本安装。

## Skill 索引与路径

| Skill | 用途 | 源码 | 上传包 |
| --- | --- | --- | --- |
| design-interrogator | 通用设计、方案和计划的澄清与风险审视 | [skills/design-interrogator/](skills/design-interrogator/) | [packages/design-interrogator.zip](packages/design-interrogator.zip) |
| product-design-interrogator | 产品和功能需求的分析与可验证假设 | [skills/product-design-interrogator/](skills/product-design-interrogator/) | [packages/product-design-interrogator.zip](packages/product-design-interrogator.zip) |
| requirements-discovery | 澄清模糊需求、审查 PRD 缺口，形成范围与验收标准 | [skills/requirements-discovery/](skills/requirements-discovery/) | [packages/requirements-discovery.zip](packages/requirements-discovery.zip) |
| iterative-development | 按目标限时自动开发、独立验收和修复，达标收尾并交付人工复核 | [skills/iterative-development/](skills/iterative-development/) | [packages/iterative-development.zip](packages/iterative-development.zip) |
| nxtpath-video | 哪都通 Seedance 2.5 图生视频与任务恢复，面向本机 Claude Code | [skills/nxtpath-video/](skills/nxtpath-video/) | [packages/nxtpath-video.zip](packages/nxtpath-video.zip) |
| seedance-video | 火山方舟 / BytePlus 官方 Seedance 2.5 与 2.0 视频生成和任务恢复，面向本机 Claude Code | [skills/seedance-video/](skills/seedance-video/) | [packages/seedance-video.zip](packages/seedance-video.zip) |
| minimax-video | MiniMax 官方 H3 视频生成，支持图片/视频/音频参考和任务恢复，面向本机 Claude Code | [skills/minimax-video/](skills/minimax-video/) | [packages/minimax-video.zip](packages/minimax-video.zip) |
| tripo-model | Tripo 文字/图片生成三维模型、后处理与续查下载，默认 CN，面向本机 Claude Code | [skills/tripo-model/](skills/tripo-model/) | [packages/tripo-model.zip](packages/tripo-model.zip) |

分析对象是产品或功能时优先使用 product-design-interrogator；其他方案、计划和设计使用 design-interrogator。尚未形成方案、需要澄清问题与需求时使用 requirements-discovery；该 skill 已针对 Claude Code 适配，并随包保留 references。需求明确后要让 Claude Code 自动开发、验收、修复直到达标时使用 iterative-development；它依赖 Claude Code 的子智能体、worktree 隔离和 Bash 执行能力，上传包仅作备份，不保证在桌面版 / Cowork 中完整运行。

`nxtpath-video` 使用本机环境变量 `NXTPATH_API_KEY` 或私有的 `~/.config/nxtpath/env`，凭证不随 Skill 或 ZIP 分发。它面向可运行本地 Python 的 Claude Code；云端会话不会因安装 ZIP 而获得本机环境或文件。图片托管是可选的 R2 配置，使用有效 HTTPS 参考图时不依赖 R2。调用示例：`/nxtpath-video 用这张参考图制作 4 秒动作小样`。

`seedance-video`、`minimax-video` 和 `tripo-model` 与 Codex 版共用 Python 客户端、参考资料和离线测试，SKILL.md 改为通过 `${CLAUDE_SKILL_DIR}` 定位脚本，在 Bash 后台等待任务或长时间生成，并抽帧审看视频。凭据分别读取本机 `~/.config/seedance/`、`~/.config/minimax/env` 和 `~/.config/tripo-skill/config.json`，不随 Skill 或 ZIP 分发；Claude Code 的 Bash 没有交互终端，配置密钥使用 `--gui` 隐藏输入框或用户自己的终端。Seedance 官方任务用 `seedance-video`，指定哪都通时用 `nxtpath-video`；Claude 未安装哪都通 MiniMax 版本。Tripo 的离线集成测试在设置了 `HTTPS_PROXY` 的 shell 中会绕过模拟接口，运行测试前先清除代理变量。

本机路径示例：

- 源码：`E:\Agent\agent-skills\claude\skills\design-interrogator`。
- 上传包：`E:\Agent\agent-skills\claude\packages\design-interrogator.zip`。

## 安装与更新

Claude 桌面版 / Cowork 的安装入口是应用中的 skill 上传界面，仓库源码目录用于维护。

按 [Claude 官方使用说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)，进入 **Customize > Skills**，点击 **+ Create skill**，选择 **Upload a skill**，上传 `packages/` 中对应的 ZIP，然后启用。

修改源码并重新打包后，在应用中更新或替换对应的已上传 skill，并确认启用的是新版本。拉取本仓库或修改本地源码不会自动更新已经上传的独立副本。不把单份 `SKILL.md` 当作完整安装包。

## 在 Claude Code 中安装

Claude Code 直接加载完整 skill 文件夹。根据 [Claude Code 官方说明](https://code.claude.com/docs/en/skills)，可选位置：

- 项目级：`<项目>/.claude/skills/<skill-name>/SKILL.md`。
- 个人级：`~/.claude/skills/<skill-name>/SKILL.md`。

例如，把 `E:\Agent\agent-skills\claude\skills\requirements-discovery` 整个目录复制到 `C:\Users\35143\.claude\skills\requirements-discovery`。保留 references 等配套文件；目标已存在时先备份，再更新完整目录。也可使用指向仓库源码目录的符号链接，确保目标路径在当前设备有效。

安装后输入 `/requirements-discovery <想法或 PRD 路径>` 调用，也可以用自然语言提出需求。自动迭代用 `/iterative-development <目标或需求文件> [时间预算]` 启动，`/iterative-development 恢复 <run-id>` 继续已有轮次；运行状态默认写在项目的 `.work/iterations/<run-id>/`，请把该目录加入 `.gitignore`。通过复制安装时，拉取 Git 后需更新副本；通过符号链接安装时，源码修改直接反映到加载目录。避免在多个加载位置安装同名副本。

上传包和 Claude Code 共用此处的 Claude 源码；维护时保留 `name`、`description` 等通用 frontmatter，并核对各使用环境的字段支持。API 使用需另行确认工具与执行环境。

## 包结构与重新打包

每个 ZIP 只包含对应的 skill 顶层文件夹，`SKILL.md` 位于其下；references、scripts 或其他资源随文件夹一起打包。[官方打包说明](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

```text
design-interrogator.zip
└── design-interrogator/
    └── SKILL.md
```

不要把整个 `claude/`、`skills/` 外层目录或两个 skill 一起打进同一个上传包。旧 `.skill` 文件已经统一为标准 ZIP 后缀。

从仓库源码重新生成单个包，PowerShell 示例：

```powershell
$taskRepo = 'E:\Agent\agent-skills'
$taskSkillName = 'design-interrogator'
$taskSource = Join-Path $taskRepo "claude\skills\$taskSkillName"
$taskPackage = Join-Path $taskRepo "claude\packages\$taskSkillName.zip"
Compress-Archive -LiteralPath $taskSource -DestinationPath $taskPackage -Force
```

更新另一个 skill 时替换 `$taskSkillName`。提交时把修改的源码和重新生成的 ZIP 一起提交。

## 验证与维护

1. 修改 `skills/<skill-name>/` 中的源码，核对名称、描述和相关资源。
2. 重新打包，检查解压后的目录结构与内容是否对应当前源码。
3. 在 Claude 中上传或更新，启用后用实际请求验证触发和结果。
4. 源码、上传包及对应说明一并版本管理；不要直接编辑应用的缓存副本。

Codex 的路径与使用方式见 [codex/README.md](../codex/README.md)。
