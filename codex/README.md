# Codex Skills

本目录保存为 Codex 适配的 skill 源码。每个 `skills/<skill-name>/` 目录包含 `SKILL.md` 和需要的 references、scripts、agents 等文件；安装时使用完整目录。

## Skill 索引

| Skill | 用途 |
| --- | --- |
| [art-asset-generation](skills/art-asset-generation/SKILL.md) | 按已有画风包生成或返工栅格素材 |
| [art-style-pack](skills/art-style-pack/SKILL.md) | 建立、校准和维护栅格画风包 |
| [iterative-development](skills/iterative-development/SKILL.md) | 限时组织开发、独立验收和自主改进，保留达标版本 |
| [model-asset-generation](skills/model-asset-generation/SKILL.md) | 按已有模型风格包制作或返工 3D 模型 |
| [model-style-pack](skills/model-style-pack/SKILL.md) | 建立、校准和维护 3D 模型风格包 |
| [requirements-discovery](skills/requirements-discovery/SKILL.md) | 澄清需求、审查缺口并形成可验证要求 |

## 源码路径与安装路径

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 本机仓库源码 | `E:\Agent\agent-skills\codex\skills\<skill-name>` | 编辑、版本管理和跨设备同步 |
| 本机当前已使用的个人安装位置 | `C:\Users\35143\.codex\skills\<skill-name>` | 当前环境已确认从此处发现个人 skill |
| 当前官方文档的个人加载位置 | `~/.agents/skills/<skill-name>` | 在新环境中按实际版本采用 |
| 项目级加载位置 | `<项目根目录>/.agents/skills/<skill-name>` | 项目共享的 skill |

当前官方位置与本机已有安装位置分别列出，避免把仓库源码路径误当运行目录。新设备按 [OpenAI Docs：Build skills](https://learn.chatgpt.com/docs/build-skills) 核对加载路径；本机可以继续沿用已经验证的个人安装位置。同一 skill 选择一个合适的安装位置，避免多个加载目录出现同名副本。

## 安装与更新

将选中的 `codex/skills/<skill-name>/` 整个目录复制到实际加载位置，使 `SKILL.md` 位于 `<加载位置>/<skill-name>/SKILL.md`。只复制 `SKILL.md` 会遗漏脚本、参考文件或界面元数据。

下面是本机首次安装示例；若目标已存在，先将旧版本备份到加载目录外，再替换整个 skill 目录：

```powershell
$taskRepo = 'E:\Agent\agent-skills'
$taskSkillName = 'iterative-development'
$taskInstallRoot = Join-Path $env:USERPROFILE '.codex\skills'
$taskSource = Join-Path $taskRepo "codex\skills\$taskSkillName"
$taskDestination = Join-Path $taskInstallRoot $taskSkillName
if (Test-Path -LiteralPath $taskDestination) {
    throw '目标已存在：先将旧版本备份到加载目录外，再安装完整目录。'
}
New-Item -ItemType Directory -Path $taskInstallRoot -Force | Out-Null
Copy-Item -LiteralPath $taskSource -Destination $taskDestination -Recurse
```

换用官方个人位置时，将 `$taskInstallRoot` 改为 `Join-Path $env:USERPROFILE '.agents\skills'`；项目级安装则改为该项目的 `.agents\skills`。不要把 `codex/` 外层目录一起复制进去。

Git 拉取只更新仓库源码。更新已安装副本时，保留旧版本备份并替换完整目录，避免合并复制残留已删除文件。重新查看 Codex 的 skill 列表；按官方文档，若变化未显示可重启应用。

## 调用与验证

在支持的 Codex 界面中选择 skill，或在请求中明确提及名称，例如：

```text
$iterative-development 按当前项目需求自动迭代，最多2小时。
```

验证名称、触发范围、参考文件和脚本是否可用，再用一项真实任务检查结果。运行证据留在项目工作区，源码维护在本仓库。

Claude 的上传包和 Claude 专用指令属于另一套平台版本；移植到 Codex 时先适配工具、路径和工作流，再独立验证。Claude 安装说明见 [claude/README.md](../claude/README.md)。
