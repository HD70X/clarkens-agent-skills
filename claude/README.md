# Claude Skills

本目录保存为 Claude 桌面版 / Cowork 适配的 skill。源码位于 `skills/`，上传包位于 `packages/`。本库 Claude 与 Codex 版本分别维护，不能将 Codex 目录或指令直接作为 Claude 版本安装。

## Skill 索引与路径

| Skill | 用途 | 源码 | 上传包 |
| --- | --- | --- | --- |
| design-interrogator | 通用设计、方案和计划的澄清与风险审视 | [skills/design-interrogator/](skills/design-interrogator/) | [packages/design-interrogator.zip](packages/design-interrogator.zip) |
| product-design-interrogator | 产品和功能需求的分析与可验证假设 | [skills/product-design-interrogator/](skills/product-design-interrogator/) | [packages/product-design-interrogator.zip](packages/product-design-interrogator.zip) |

分析对象是产品或功能时优先使用 product-design-interrogator；其他方案、计划和设计使用 design-interrogator。

本机路径示例：

- 源码：`E:\Agent\agent-skills\claude\skills\design-interrogator`。
- 上传包：`E:\Agent\agent-skills\claude\packages\design-interrogator.zip`。

## 安装与更新

Claude 桌面版 / Cowork 的安装入口是应用中的 skill 上传界面，仓库源码目录用于维护。

按 [Claude 官方使用说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)，进入 **Customize > Skills**，点击 **+ Create skill**，选择 **Upload a skill**，上传 `packages/` 中对应的 ZIP，然后启用。

修改源码并重新打包后，在应用中更新或替换对应的已上传 skill，并确认启用的是新版本。拉取本仓库或修改本地源码不会自动更新已经上传的独立副本。不把单份 `SKILL.md` 当作完整安装包。

本目录面向上述 Claude 使用方式；如需用于 Claude Code 或 API，先确认并适配对应产品的加载方式、工具和执行环境。

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
