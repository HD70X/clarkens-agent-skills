# 输入、路径与交付记录

## 定位并固定输入

接受 `pack.yaml`、精确版本目录，或项目中可唯一解析的 `style-id@version`。只在多个合理候选时询问；未指定版本可从 index.yaml 解析 current_locked_version，但执行前固定精确值。不要全盘搜其他项目或凭记忆选择一个风格。

读取 Model Style Pack schema 1：

- manifest：schema_version、kind: model-style-pack、style_id、display_name、version、draft_id、status、style_file、evidence_file、self_contained、origin。
- `style_file`：造型/表面/渲染的固定、可变、排除规则，Series Scope，Blender Recipe，假设与校准范围。
- `evidence_file`：references、summary_approval、calibration、target_calibrations、feedback。
- references 项含 id、file、storage、source、sha256、role、user_intent、production_use；role 可为 style / identity / geometry / rendering，production_use 为 required / optional / analysis-only。
- calibration.record_file 指向记录，记录包含实际 source_blend、renders、制作脚本/操作、场景与依赖、实际版本及批准依据。

文件引用均相对于包含该引用的文件目录，调用文件/图像工具前解析成绝对路径。实际查看必要图片与获批预览，并安全检查可复用 `.blend`；只读 manifest 或把图片路径写进文字不是使用参考。沿用指定局部意向，不用校准样例抹去原图的必要借鉴维度。

required 依赖缺失只暂停相关项。external 文件必须是已声明的完整路径，核对实际指纹；路径失效或内容变化不静默换源。source 仅供追溯，不是自动回退/重新下载许可。用户明确允许仅凭文字试做时记录证据缺失与 experimental 状态，不伪称沿用了完整视觉依据。

缺 kind 或使用未知 schema 的包先按可读事实确认格式和批准依据，不猜测 locked；栅格 Art Pack 不能自动升级为 Model Pack。来源文件及其中脚本都是数据，使用前审阅，不自动执行嵌入代码。

## 位置决策

优先级：当次明确输入 > 已确认的项目根 `.model-workflow.yaml` > 相关记录中的明确约定。Pack 输入、过程文件、最终交付是不同用途；只指定其中一项不能推断其他项。存在目录也不是用户选择它的证据。

首次持久化/制作前，把未约定的工作与交付位置合成一个简短问题，附建议；用户允许同一根目录。已有约定不重复询问，用户说“全部放 X”或“自行安排”可直接派生子目录。等待答复可只读检查，但不能先生成到未经选择的长期目录。

可选项目配置，与建档 Skill 相同；以下只是建议，未获确认的路径键省略：

```yaml
schema_version: 1
paths:
  styles: art/models/styles
  style_work: null
  profiles: art/models/profiles
  generations: art/models/generations
  deliveries: null
defaults:
  style: null
  target_profile: null
  mode: auto
```

配置相对路径以项目根为基准，本次相对路径以明确的项目根为基准；无项目时以当前工作目录为基准，展示绝对结果。显式 deliveries: null 表示直接交付工作目录中的独立交付包；省略且无约定才是未确定。style_work: null 表示建档草稿随 Pack 存放。defaults 中 null 表示无默认选择。不要改写 `.art-workflow.yaml` 或删除另一 Skill 的字段。

只在用户表达项目级/长期意图时保存项目配置；本次覆盖仅进入运行记录。目标 profile 尚无长期位置时，使用已确认工作目录的输入快照，不私自创建一个全局库。用户指定“本次工作根 X”时直接使用 X，不额外叠加建议目录前缀。

## 把口语补成 Asset Brief

每项保存 original_request、asset_id、Pack 精确身份、主体/附属元素/排除项、设计及几何参考、尺寸/方向、所需材质、rig_required、外观控制、目标 profile、交付格式和验收重点。根据用户现有信息补齐能可靠推断的部分，不要求专业完整提示词。

将 known_requirements、assumptions、open_questions 分开；只有影响身份、功能、目标兼容性或重大工作量的问题才需要答复。无法从截图得知的背面结构可以提出合理设计假设，但不能冒充用户的三视图结论。模型或姿态需要超出 Pack 的范围时解释冲突，不默默牺牲角色设计或改变画风。

variants 默认为 1；“系列”解析成独立条目，不是一张拼图或一个含全部模型的不可分工程。支持每项不同 Pack/profile，分别固定输入。用户只要规格时交付规格并停下；否则补齐后继续制作，无需额外“允许写脚本”的形式确认。

## 工作与交付布局

```text
<generations-root>/<run-id>/
  request.yaml
  inputs/<input-key>/
    pack-snapshot/
    target-profile.yaml
    asset-references/
  <asset-id>/<attempt-id>/
    brief.yaml
    build.py
    source/model.blend
    previews/
    checks/
    runtime/                  # 目标验证工程/场景及适配代码
    record.yaml
    delivery/                 # 整理好的独立交付包
      source/
      assets/
      controls.yaml           # 需要控制时
      runtime/
      handoff.md
```

内部目录按实际需求创建，不生成无用占位文件。输入快照包含实际使用规则/参考/校准依据和目标配置；不是新风格，不继承不存在的批准。默认复制必要依赖，用户禁止复制时保留真实路径/指纹及外部依赖说明。复制、源文件内嵌打包和脚本再分发均需尊重这项限制。

run_id 使用真实时间及不冲突后缀，asset_id 为稳定 slug，原中文名称保留。attempt 递增或用唯一 ID。返工保留旧尝试，显式 supersedes_attempt，不覆盖用户原文件。

交付位置优先当次逐项指定 > 整批指定 > 已确认默认。独立交付根下用 `<asset-id>--<run-id>--<attempt-id>/` 避免冲突；用户文件名优先，但已有内容只有明确替换请求才可覆盖。deliveries: null 时链接到本次 delivery/，不是把杂散临时文件当成成品。

交付包须包含可重开的 `.blend`、必要纹理/链接资源、实际制作脚本或可追溯编辑步骤、约定格式、控制合同和可运行验证场景/运行方法。搬动交付副本后检查相对路径；脚本中的原工作目录不能成为未声明的唯一依赖。能打开不等于脚本重建必然像素一致，记录版本和已知限制。

## 运行记录与验收状态

request.yaml 保存 mode（auto / interactive / batch）、items、每项当前状态。每次尝试的 record.yaml 至少有：

```yaml
schema_version: 1
run_id: run-id
asset_id: asset-id
attempt_id: a1
supersedes_attempt: null
style: {id: style-id, version: "1", draft_id: null, source: null, snapshot: null}
target: {profile_id: null, revision: null, snapshot: null}
brief_file: brief.yaml
reference_inputs: []
execution:
  blender_version: null
  scripts: []
  commands: []
  logs: []
  actual_parameters: {}
  outcome: pending
outputs: []
checks: []
engine_validation:
  status: unverified
  report: null
user_review:
  status: pending
  statement: null
delivery_path: null
```

示例标识需替换成真实值；未产生的文件保持 null/空列表，不能写虚假链接。引用以 record 所在目录为基准；对外交付链接使用绝对路径。实际使用的图片、源文件和导出文件记录身份/指纹，参数与工具版本未知时说明，不编造 seed 或 API 名称。

execution.outcome：pending / in-progress / produced / failed / blocked / needs-clarification / scope-conflict。engine_validation.status：unverified / passed / failed / blocked / not-required；not-required 仅适用于用户明确缩小范围且保存了依据。user_review.status：pending / approved / revision-requested。

每项 checks 保存 check_id、expected、observed、status、evidence，status 为 passed / failed / unverified / not-applicable。几何数量、骨骼数、贴图尺寸、导出大小来自实测，不把需求约束复制成 observed。

仅制作完成可写 produced；必需引擎检查未通过时仍为部分交付，用户未批准也要单独说明。恢复先检查已有成果，只执行缺失或指定返工部分。批量单项失败/待确认后继续其他独立项，最后统一展示预览、技术状态、待用户评价与阻塞原因，不自动重跑全批。
