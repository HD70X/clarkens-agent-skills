# Pack 存储与交接格式

## 路径决策

先区分过程文件（分析参考、草稿、全部校准尝试）和最终 Pack（锁定规则及后续生图所需证据）。任务需要保存且没有路径约定时，默认使用当前项目的 `art/styles/<style-id>/`，过程文件放对应 drafts/；无项目时以当前工作目录为基准。选择不冲突的新 ID 或版本，说明路径后继续。用户指定个人库或独立目录时优先遵守。

优先级为：本次明确路径 > 已确认的 `.art-workflow.yaml` 设置 > 相关记录中的明确约定 > 本次默认位置。默认只记入本次档案，不冒充用户的长期选择。只有无法确定目标项目、路径不可用或必须替换原件才能满足请求时才澄清，其他独立分析可继续。已有目录中的内容不覆盖，不向只读来源 Pack 写入草稿。

可选项目配置（与生产 Skill 共用；以下展示可选默认值，仅在用户要求保存项目级约定时写入配置）：

```yaml
schema_version: 1
paths:
  styles: art/styles
  style_work: null
  requests: art/requests
  generations: art/generations
  deliveries: null
defaults:
  style: null
  mode: auto
```

配置相对路径都相对于配置所在项目根目录；绝对路径直接使用。用户本次的相对路径以已确定项目根为基准，无项目则以当前工作目录为基准，并展示解析结果。用户明确给出某个 Pack 的完整目录时直接使用；只有“风格库根目录”才追加 style-id。`paths.style_work: null` 表示过程文件随 Pack 放在 drafts/；省略且无既有约定时本次也采用此布局，记录其为默认值。若指定独立 style_work 根，则草稿位于 `<style_work>/<style-id>/<draft-id>/`，索引记录真实路径。`defaults.style` 可为 `food@1` 或 Pack 路径，只作默认选择。仅用户表达项目级或长期约定时创建/更新配置，保留无关字段；本次路径只记入档案。

## 自包含布局

```text
<styles-root>/<style-id>/
  index.yaml
  drafts/<draft-id>/
    pack.yaml
    style.md
    evidence.yaml
    references/
    calibration/<attempt-id>/
      brief.yaml
      prompt.txt
      record.yaml
      output.png
  versions/<version>/
    pack.yaml
    style.md
    evidence.yaml
    references/
    calibration/
```

上图表示过程文件与 Pack 同根的情况。独立 style_work 只改变草稿位置；锁定时仍把必需参考、获批校准图和生成记录复制进 versions/<version>/，修正相对引用，不能让最终 Pack 依赖可清理的工作目录。其他失败尝试留在工作目录，不自动删除。输出扩展名按真实格式；包内文件引用相对于包含该引用的文件目录。路径的绝对化只发生在实际读取/调用时，不写死为运行依赖。

## 参考图资产与外部路径

默认生成自包含 Pack：原始来源图片先进入工作区，锁定时将支撑风格规则、融合意向和后续生图的必要图片复制到版本内 references/，并带上用户获批的校准图。不要只保存描述或原机器上的完整路径，也不要用指向包外的符号链接冒充内置素材。外部原路径或 URL 可记为 source，仅用于追溯。

每张参考记录用途与 generation_use：required（指定维度必须使用）、optional（按主体和工具限制选择）、analysis-only（仅分析来源，不要求生产读取）。根据用户已确认意向判断；未指定时 optional。必需与可选生产参考在锁定前实际保存，记录真实 sha256；仅分析用材料可以留在工作区并保留来源说明，不要求全部复制进最终包。获批校准图作为系列一致性的候选视觉锚点，不抹去用户对原始参考的局部借鉴要求。

仅用户明确选择不复制、使用共享图片库等场景才允许 external 引用：file 保存可访问的绝对路径，storage 写 external，记录 sha256，并将 pack.yaml 的 self_contained 设为 false，交付时列出外部依赖。使用前验证存在性与内容指纹；路径失效或内容变化时不能静默替换。用户选择打包时再复制并修正引用。外部来源字段不是可自动重下载或回退的授权。

命名默认使用简短 kebab-case ID；展示名可以中文。已有 ID 不同内容时不覆盖。草稿、校准尝试用新的稳定 ID，已存在路径产生新 ID。版本是字符串，默认首版 `"1"` 后递增；项目已有版本惯例优先。不要用标题充当唯一身份。

`index.yaml` 只保存 style_id、display_name、current_locked_version 和草稿路径等可变索引。它不是画风规则。每个草稿或锁定版本用以下 manifest：

```yaml
schema_version: 1
style_id: vector-food
display_name: 食物插画
version: null
draft_id: d1
status: draft
style_file: style.md
evidence_file: evidence.yaml
self_contained: true
origin: null
```

状态为 draft / summary-confirmed / calibrating / locked。摘要单独获批时使用 summary-confirmed；已有直接校准授权时允许 draft → calibrating，summary_approval.approved 仍保持 false，授权原话记在校准记录中。最终规则和样图可由同一次明确反馈批准后锁定；仅批准试做不能当成验收。只分析并保存可停在草稿。锁定时填写精确 version，draft_id 可保留来源。status 在 pack.yaml 中维护，不在多个文件重复维护状态。

`style.md` 是视觉规则的唯一权威文本，包含：

- Style Spec：固定特征、可变项、禁止项、自检标准。
- Series Scope：主体、条件性附属元素和排除范围。
- Generation Profile：工具偏好、提示词组织规则、输出默认值；请求约束不冒充实际参数。
- 通俗摘要及其对应的参考证据；标明候选/已确认状态及推测。
- 校准覆盖范围和已知限制。

`evidence.yaml` 保存原话、图像证据及批准依据：

```yaml
schema_version: 1
references:
  - id: ref-a
    file: references/ref-a.png
    storage: bundled
    source: null
    sha256: null
    user_intent: null
    interpreted_role: holistic
    generation_use: optional
    observations: []
    hypotheses: []
summary_approval:
  approved: false
  user_statement: null
  recorded_at: null
calibration:
  brief: null
  approved_image: null
  generation_record: null
  user_statement: null
feedback: []
```

校准记录保存实际提示词文件、实际传入参考图及其用途/顺序、工具名称、工具可见模型与参数、输出路径、自检及用户批准。未知参数用 null 并注明原因；时间从实际时钟取得。反馈记录原话、解释、作用范围、修改项、保留项和确认依据。

## 保存、锁定与复用

在本次解析的工作位置及时保存草稿，以便下次继续。锁定需要用户认可规则摘要与实际校准图，以及必需文件齐备或所选外部依赖已核验。规则与样图可合并展示和批准，并分别记录同一反馈；只认可图片而未涉及候选规则时，不伪造摘要批准，明确剩余验收项。复制规则和必要证据到新版本，核验引用后更新 index；不修改已有锁定版本。对 self_contained: true 的 Pack，检查所有生产参考与校准证据均能仅凭版本目录解析，不依赖工作目录、原图来源路径或聊天附件。不能把工具临时文件当成持久化证据。

仅保存规则的用户可得到未校准草稿，不自动生图。额外迁移样图不构成锁定必需条件。采用已生成且用户认可的生产图校准时，核对其风格/提示词来源，复制图和记录到 Pack 内，再保存批准依据。

跨项目默认采用可追溯快照：参考重建用新 ID 和新草稿，原样复用复制指定锁定版和必需证据，保留来源与版本。不反向写入源项目、不依赖可变共享文件。用户指定共享 Pack 库时可固定引用锁定版本，生产方只读；若 Pack 自身含 external 图片，迁移时另外检查并列出这些依赖，不能因复制了 Pack 就宣称已经自包含。

交接入口是版本目录或该目录的 pack.yaml；也可交付风格根目录加精确版本。交付包含“路径、style_id@version、status、style_file、evidence_file、批准图路径”。生产方只需读取这些文件。打包后的路径缺失就说明不完整，不伪造锁定成果。

旧 `art-asset-workflow` 格式若只有 index.yaml、style.md、evidence.yaml，可从原有身份、状态及批准记录中解析。读取无需迁移；用户修改或导入时可生成新 manifest，不能覆写旧锁定目录。没有身份或批准依据不能按文件夹名称臆测状态。
