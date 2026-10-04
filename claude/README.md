# Claude 适配文件夹

本文件夹存放为 Claude（桌面版 / Cowork / Claude Code）适配的自定义 skill，用于备份和跨设备迁移。

## 目录结构

```
claude/
├── README.md                              # 本说明
├── skills/                                # skill 源文件（可直接阅读和修改）
│   ├── design-interrogator/SKILL.md       # 设计审问者（通用版）
│   ├── product-design-interrogator/SKILL.md  # 产品设计审问者（产品/功能专用版）
│   └── requirements-discovery/            # 需求发现与澄清（SKILL.md + references/）
├── design-interrogator.skill              # 一键安装包
├── product-design-interrogator.skill      # 一键安装包
└── requirements-discovery.skill           # 一键安装包
```

## 三个 skill 的分工

- **design-interrogator（设计审问者）**：通用内核 + 领域透镜，分析任何原型观念、方案、计划。通过多轮提问挖掘不确定性、逻辑漏洞和思维定势之外的风险。
- **product-design-interrogator（产品设计审问者）**：专注产品/功能设计。含 10 个产品专项提问维度（需求真实性、行为假设、反向滥用等），待验证假设会附带建议的验证手段。**分析对象是产品/功能时优先用这个。**
- **requirements-discovery（需求发现与澄清）**：从模糊想法、投诉或不完整的请求出发做需求访谈，或审查 PRD / 工单的缺口，最终产出问题定义、范围、可验证的需求与验收标准。与前两者的区别：前两者审视的是"已有的方案"，本 skill 面向"方案之前"的问题澄清。与 `cgt/skills/requirements-discovery` 同源，SKILL.md 针对 Claude Code 做了适配。

## 在其他设备上安装

方式一（推荐）：把 `.skill` 文件发送到该设备上的 Claude 对话中，会出现"保存技能（Save skill）"按钮，点击即可安装到账户。

方式二：把对应的 `SKILL.md` 内容发给 Claude，说"请把这个保存为我的 skill"。

## 在 Claude Code 中安装

Claude Code 不用 `.skill` 包，而是直接读取技能文件夹，有两个位置：

- 项目级：`<项目>/.claude/skills/<name>/SKILL.md`，只在该项目的会话中可用，可随仓库提交共享。
- 个人级：`~/.claude/skills/<name>/SKILL.md`，本机所有项目可用。

两处都可以用符号链接指向本仓库的 `skills/<name>/`，这样改源文件即生效，不需要重新安装。例如在 `Developer/Agent` 项目中：

```sh
ln -s ../../agent-skills/claude/skills/requirements-discovery .claude/skills/requirements-discovery
ln -s "$PWD/agent-skills/claude/skills/requirements-discovery" ~/.claude/skills/requirements-discovery
```

同名技能在两处同时存在时只加载一次（个人级优先）。安装后在对话里输入 `/requirements-discovery <想法或 PRD 路径>` 手动调用；也可以直接用自然语言描述需求，Claude 会根据 `description` 自动匹配。新增或修改技能后无需重启会话。

为了让同一份 SKILL.md 既能在 Claude Code 使用、又能打包成 `.skill` 发到 claude.ai / Cowork，frontmatter 只写 `name` 和 `description`：claude.ai 侧遇到 `argument-hint`、`model` 等 Claude Code 专有字段会直接报错。

## 修改 skill

直接编辑 `skills/` 下的 SKILL.md 后，需要让 Claude 重新保存才会生效（对 Claude 说"用这个文件更新我的 xxx skill"）。已安装 skill 的运行副本是只读缓存，改这里的文件不会自动同步。Claude Code 侧如果是符号链接安装，则改完即生效。

重新打包 `.skill`（zip 存储模式，顶层目录为技能名）：

```sh
cd skills && rm -f ../<name>.skill && zip -0 -r -X ../<name>.skill <name> -x '*.DS_Store'
```
