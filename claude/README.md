# Claude 适配文件夹

本文件夹存放为 Claude（桌面版 / Cowork）适配的自定义 skill，用于备份和跨设备迁移。

## 目录结构

```
claude/
├── README.md                              # 本说明
├── skills/                                # skill 源文件（可直接阅读和修改）
│   ├── design-interrogator/SKILL.md       # 设计审问者（通用版）
│   └── product-design-interrogator/SKILL.md  # 产品设计审问者（产品/功能专用版）
├── design-interrogator.skill              # 一键安装包
└── product-design-interrogator.skill      # 一键安装包
```

## 两个 skill 的分工

- **design-interrogator（设计审问者）**：通用内核 + 领域透镜，分析任何原型观念、方案、计划。通过多轮提问挖掘不确定性、逻辑漏洞和思维定势之外的风险。
- **product-design-interrogator（产品设计审问者）**：专注产品/功能设计。含 10 个产品专项提问维度（需求真实性、行为假设、反向滥用等），待验证假设会附带建议的验证手段。**分析对象是产品/功能时优先用这个。**

## 在其他设备上安装

方式一（推荐）：把 `.skill` 文件发送到该设备上的 Claude 对话中，会出现"保存技能（Save skill）"按钮，点击即可安装到账户。

方式二：把对应的 `SKILL.md` 内容发给 Claude，说"请把这个保存为我的 skill"。

## 修改 skill

直接编辑 `skills/` 下的 SKILL.md 后，需要让 Claude 重新保存才会生效（对 Claude 说"用这个文件更新我的 xxx skill"）。已安装 skill 的运行副本是只读缓存，改这里的文件不会自动同步。
