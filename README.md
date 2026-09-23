# Agent Skills

个人 skill 源文件与安装包，按使用平台分类，便于版本管理和跨设备同步。

## 目录

```text
agent-skills/
├── cgt/
│   └── skills/
│       ├── art-asset-generation/
│       ├── art-style-pack/
│       ├── model-asset-generation/
│       ├── model-style-pack/
│       └── requirements-discovery/
└── claude/
    ├── skills/
    │   ├── design-interrogator/
    │   └── product-design-interrogator/
    ├── design-interrogator.skill
    ├── product-design-interrogator.skill
    └── README.md
```

`cgt` 保存 CGT/Codex 使用的 skill；`claude` 保存 Claude 的源文件及 `.skill` 安装包。每个 skill 的 references、scripts、agents 等配套文件都随目录一起保存。

## 跨设备同步

将仓库推送到自己的 Git 远程地址后，在其他设备执行：

```sh
git clone <仓库地址> agent-skills
cd agent-skills
```

更新前运行 `git pull --ff-only`。修改后运行：

```sh
git add .
git commit -m "Update skills"
git push
```

换设备工作前先提交并推送当前设备的修改，再在另一台设备拉取。存在未提交修改时，先提交或暂存，再同步。

## 使用与维护

- Git 同步的是源文件；应用中已安装的独立副本不会自动更新。安装或更新时请使用对应平台目录中的完整 skill 文件夹。
- Claude 的 `.skill` 文件为现有安装包；修改 `claude/skills/` 后，应重新打包并更新对应安装包，保持二者一致。
- 本仓库不包含账户凭证、应用配置或其他项目素材。
- 原项目中的 `skills/`、`claude/` 和 `.claude/skills/` 已通过相对符号链接指向本仓库，保持原路径可用。这些兼容链接在仓库外，不随克隆迁移。

所有 skill 内容保持整理前的版本。
