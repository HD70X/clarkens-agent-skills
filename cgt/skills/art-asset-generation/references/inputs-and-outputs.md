# 输入与产物约定

## 定位 Pack

接受 pack.yaml、版本目录，或风格根目录加版本；也接受当前项目可唯一解析的 `style-id@version`。未指定版本时可读取 index.yaml 的 current_locked_version，但执行前必须固定精确值。用户提供独立 Pack 路径即可使用，不依赖创建它的 Skill。

优先级：当次明确输入 > 已确认的项目根 `.art-workflow.yaml` 设置 > 已写明或相关历史记录确定的约定。位置未约定时先询问，不自动采用内置默认值。不要全盘搜索或凭记忆选择另一个项目的 Pack。Pack 选择与输出位置是两件事，提供了 Pack 路径不等于确认工作目录或交付位置；有多个候选 Pack 时才需澄清选择。

可选配置与 `art-style-pack` 一致（下面是建议值，只写入用户已接受的位置，未约定的键省略）：

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

配置相对路径以项目根为基准；defaults.style 是 ID@版本或 Pack 路径。用户本次的相对路径也以已确定项目根为基准，无项目则以当前工作目录为基准，并展示解析结果。mode 缺省仍为 auto；路径缺省是待确认建议。用户表达项目级或长期约定时才保存配置，临时位置只记入本次请求。读取配置时保留 style_work 等另一 Skill 的字段，不因为自己不使用就删除。

首次使用时分别明确“工作文件放哪里”和“最终图片放哪里”，把尚缺的两项合成一个简短问题并给出路径建议。工作位置可建议 art/generations/（需求清单另放 art/requests/），交付可独立指定或直接使用原始图。用户只给“图片放 assets/items”时仅已确认交付位置，还需确认工作位置；用户说“所有文件都放 X”或“沿用建议”则视为已覆盖相应位置。已有配置或明确历史记录无需重复询问；用户已授权自行选择也无需再问。等待答复时继续只读预检，但不先调用生图或持久化到未选目录。

配置显式 `deliveries: null` 表示用户选择直接交付原始图，不是缺失；省略 deliveries 且无其他约定才需询问。同理，独立工作根已明确时可按下文派生 requests/ 等内部目录，无需用户逐一指定。不可只凭项目里存在 art/、assets/ 或代码引用目录就认定其也是过程文件位置。两个 Skill 只共享有明确用途的路径，不能把 styles 自动用作正式图片的交付目录。

## 读取契约

新 Pack 的 pack.yaml 含 schema_version: 1、style_id、display_name、version、draft_id、status、style_file、evidence_file、origin。文件引用相对于所属文件目录。读取 style.md 中的 Style Spec、Series Scope、Generation Profile，以及 evidence.yaml 中参考意向、摘要批准、校准图与批准依据。除非用户明确试做，否则使用 locked 版本。

manifest 是入口，规则和视觉证据仍必须实际读取。核对路径可访问；外部 Pack 也只读。新包可额外含 self_contained，参考项可含 storage、source、sha256、generation_use。旧字段缺失时按实际文件与明确证据解析，不要求迁移；相对 file 可按 bundled 读取，绝对 file 视为外部依赖，不能臆测可移植性。没有 manifest 的旧格式读取 index.yaml、style.md、evidence.yaml；状态未知时说明，不猜测 locked。

## 参考图读取与传入

默认从 Pack 内取实际图像：evidence.references[*].file 按 evidence.yaml 所在目录解析，calibration.approved_image 同样解析。相对路径保证包可移动；传给 view_image 或生图工具时转换为当前环境的绝对路径并核验存在。遵循当前工具的真实图像输入机制；把文件路径作为普通提示词文本不等于传入图片。

结合本次主体使用获批校准图与原始参考，遵守用户对配色、笔触等特定意向。generation_use 为 required 的维度参考必须使用，optional 可选择，analysis-only 不必作为生图输入；旧包无字段时据明确意向选择，不能跳过其必要证据。工具容量不足以容纳必需图时说明并解决冲突，不静默只传文字。不要要求用户为 Pack 内已有图片重新上传。

external 引用仅按包中明确记录的完整路径读取，不自动猜替代路径。存在 sha256 时核对内容；失效或变更只阻塞受影响项并说明，不能把变更图片当成原风格证据。源路径 source 仅供追溯，不是自动回退来源。用户补充的本次构图或主体参考写入本次输入快照，不写回 Pack。外部文件允许快照时复制实际使用图；用户明确禁止复制时保留真实路径/指纹并注明本次记录含外部依赖。

## 路径与命名

用户接受建议位置后的布局示例：

```text
art/requests/<request-id>.yaml
art/generations/<run-id>/
  inputs/<pack-key>/
    # 本批次规则、证据说明和实际采用的参考图快照
  <asset-id>/<attempt-id>/
    prompt.txt
    record.yaml
    output.png
```

inputs 是生成依据快照，不是新建的 Style Pack，不附会新的批准或版本。保存规则与实际参考的关系及原 Pack 路径/ID/版本；已有同批 inputs 不重复复制。默认包含实际使用的参考图，即使源库以后移动仍能追溯；用户明确禁止复制的外部图片例外，需在记录中说明依赖。

单张也使用同一布局，逐条独立输出。request_id、run_id 使用真实日期/时间加短后缀，asset_id 用稳定简短 slug，attempt_id 递增或使用不冲突的 ID。中文原名保留在 Brief；检查路径冲突后再写，不能静默覆盖。后缀匹配真实图像格式，不通过改扩展名冒充转码。

原始图与记录始终保存到已确认的 generations 路径。交付优先级为：当次每项明确文件/目录 > 当次整批交付目录 > 已确认配置或既有交付约定。用户明确选择直接使用原始图（包括已确认配置 deliveries: null）才不另复制；没有交付约定时先询问，不能把未指定自动解释为同意直接交付原始图。

独立交付目录默认文件名为 `<asset-id>--<run-id>--<attempt-id>.<实际扩展名>`；用户给定文件名优先，但已有文件除非明确要求替换，否则创建带版本后缀的同级文件。请求把多个独立素材写到一个文件时澄清，不自行拼图。复制不包含裁剪、压缩或 SVG 转换。

用户指定本次输出根时，直接用作该次 generations 根，不额外叠加 art/generations；请求记录放在该输出根的 requests/（除非另指定）。本次覆盖不改变项目默认设置。所有记录内部引用明确基准，交付链接用绝对路径。不要把项目产物仅留在工具临时目录。

## 需求与运行记录

请求文件保存 schema_version: 1、request_id、mode 和 items。每条含 asset_id、original_request、style_id、style_version、draft_id（如试做）、subject、supporting_elements、composition、output_constraints、variants_requested（默认 1）、destination。多项不同风格各自绑定；不以 latest 写入记录。

每次尝试保存以下记录，尖括号只示意字段含义，实际用真实值：

```yaml
schema_version: 1
request_id: <request-id>
asset_id: <asset-id>
attempt_id: <attempt-id>
style:
  id: <style-id>
  version: <exact-version>
  draft_id: null
  source: <pack-path>
  input_snapshot: <snapshot-path>
brief_snapshot: {}
reference_inputs: []
prompt_file: prompt.txt
execution:
  tool: <actual-tool>
  model: null
  model_unknown_reason: null
  actual_parameters: {}
  outcome: pending
  error: null
output: null
delivery_copy: null
observed_properties: {}
self_check: []
review: {status: pending, user_statement: null}
supersedes_attempt: null
```

reference_inputs 保存真正传入的图像及角色/顺序，并引用本次快照。输出、提示词和快照路径相对于 record.yaml；外部 source 保留原始绝对路径作来源说明，不是唯一运行依据。

execution.outcome 为 pending / generated / failed / blocked / needs-clarification / scope-conflict。review.status 独立为 pending / approved / revision-requested。未尝试项在请求清单中记录状态与原因，不虚构工具调用或生成记录。工具不暴露的信息为 null；实际属性通过文件检查取得，不能复制提示词约束当成事实。

输出及状态逐项落盘。恢复时检查已有记录，只执行未完成项；选定返工建立新 attempt，保留 supersedes_attempt。反馈与用户批准保存在生产记录中，不修改输入 Pack。
