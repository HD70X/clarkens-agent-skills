# Agent Skills

个人 skill 仓库，按 Claude 和 Codex 两个平台分别维护。**本库两套 skill 分别适配各自的工具、执行环境和工作流，不能直接跨平台安装或替换。** 同一能力需要支持两个平台时，分别保留并验证各自版本。

## 目录结构

```text
agent-skills/
├── README.md
├── codex/
│   ├── README.md
│   └── skills/
│       ├── art-asset-generation/
│       ├── art-style-pack/
│       ├── deepseek-iterative-development/
│       ├── iterative-development/
│       ├── model-asset-generation/
│       ├── model-style-pack/
│       ├── nxtpath-minimax-video/
│       ├── nxtpath-video/
│       ├── requirements-discovery/
│       └── tripo-model/
└── claude/
    ├── README.md
    ├── skills/
    │   ├── design-interrogator/
    │   ├── iterative-development/
    │   ├── nxtpath-video/
    │   ├── product-design-interrogator/
    │   └── requirements-discovery/
    └── packages/
        ├── design-interrogator.zip
        ├── iterative-development.zip
        ├── nxtpath-video.zip
        ├── product-design-interrogator.zip
        └── requirements-discovery.zip
```

## 路径与使用入口

| 目的 | 仓库路径 | 使用方式 |
| --- | --- | --- |
| 查看、修改 Codex skill | [codex/skills/](codex/skills/) | 每个子目录是一份完整 skill，连同 references、scripts、agents 等文件一起使用 |
| 安装、更新 Codex skill | [codex/README.md](codex/README.md) | 将选中的完整目录复制到 Codex 实际加载路径 |
| 查看、修改 Claude skill | [claude/skills/](claude/skills/) | 修改对应 skill 的源码目录 |
| 安装、更新 Claude skill | [claude/packages/](claude/packages/) | 桌面版 / Cowork 上传 ZIP，Claude Code 安装完整源码目录；具体步骤见 [Claude 使用说明](claude/README.md) |

本机仓库位于 `E:\Agent\agent-skills`，例如：

- Codex 自动迭代开发源码：`E:\Agent\agent-skills\codex\skills\iterative-development`。
- Claude 设计审问者源码：`E:\Agent\agent-skills\claude\skills\design-interrogator`。
- Claude 设计审问者上传包：`E:\Agent\agent-skills\claude\packages\design-interrogator.zip`。

仓库目录用于保存和版本管理，应用加载路径用于运行。克隆或拉取本仓库后，还需要按对应平台安装或更新；已安装的独立副本不会随 Git 拉取自动变化。不要把整个仓库或另一个平台的 `skills/` 目录作为安装内容。

Claude 版 [requirements-discovery](claude/skills/requirements-discovery/) 与 [Codex 版](codex/skills/requirements-discovery/) 同源，Claude 版已适配 Claude Code 的输入、提问等待和报告保存方式。Claude 版 [iterative-development](claude/skills/iterative-development/) 与 [Codex 版](codex/skills/iterative-development/) 同源：两份验收参考和 `run_control.py` 相同，SKILL.md、协作、执行与运行状态参考按 Claude Code 的子智能体、worktree、定时唤醒和权限机制改写，面向 Claude Code 使用。共同参考资料的修改需检查两边是否需要同步，平台指令分别维护。

[Codex 版 nxtpath-video](codex/skills/nxtpath-video/) 与 [Claude Code 版](claude/skills/nxtpath-video/) 分别保存、验证和安装，任务客户端与离线测试保持一致，执行工具与视频交付指令按平台适配。两者读取同一套本机 `NXTPATH_` 环境配置；凭证、工具虚拟环境和生成任务记录不进入本仓库。

[Codex 版 nxtpath-minimax-video](codex/skills/nxtpath-minimax-video/) 使用哪都通 MiniMax H3，支持文生视频、首尾帧与普通参考图，复用上述本机私有配置。该技能独立保存客户端与验证，不依赖 Seedance skill 文件。

## 维护规则

1. 先选择目标平台，只修改该平台的 skill；跨平台移植需适配并分别验证。
2. 以 `<平台>/skills/<skill-name>/` 为源码，每个 skill 保留完整配套文件。
3. Claude 源码改变后，重新生成 `claude/packages/<skill-name>.zip` 并更新上传版本；不要只修改安装包。
4. Codex 源码改变后，更新已安装副本并在目标环境验证；按需保留该平台的 `agents/openai.yaml`。
5. 新增或移除 skill 时同步更新目录索引及平台说明。
6. 运行日志、测试工作区、账户配置和凭证留在仓库外。

## 跨设备同步

```sh
git clone https://github.com/HD70X/clarkens-agent-skills.git agent-skills
cd agent-skills
git pull --ff-only
```

修改完成后，检查并提交对应文件，再推送：

```sh
git status
git add <本次修改的路径>
git commit -m "Update skills"
git push
```

换设备工作前先完成当前设备的提交与推送，再到另一台设备拉取和更新该平台的安装副本。存在未提交修改时先整理本地改动，再同步。

## 旧路径迁移

| 旧路径 | 新路径 |
| --- | --- |
| `cgt/skills/<skill-name>/` | `codex/skills/<skill-name>/` |
| `claude/design-interrogator.skill` | `claude/packages/design-interrogator.zip` |
| `claude/product-design-interrogator.skill` | `claude/packages/product-design-interrogator.zip` |
| `claude/requirements-discovery.skill` | `claude/packages/requirements-discovery.zip` |

旧 `.skill` 文件本身是 ZIP，本次保留原包内容并统一为 `.zip` 后缀。引用旧仓库路径的脚本和符号链接也应更新到新路径。
