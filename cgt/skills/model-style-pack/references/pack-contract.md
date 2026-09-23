# Model Style Pack 契约（schema 1）

## 位置与项目配置

首次持久化或制作前分别明确过程文件和最终 Pack 的位置。优先级：本次明确输入 > 已确认的项目配置 > 相关记录中的明确约定。只问缺项；给了 Pack 路径不等于同意把过程文件写入那里。存在 `art/` 目录也不代表已确认用途。用户说“全部放 X”或“自行决定”时可安排内部子目录，无需逐个询问。

可选的项目根 `.model-workflow.yaml` 与生产 Skill 共用，与栅格工作流的 `.art-workflow.yaml` 分离。下面只是待接受的建议，不自动创建配置或目录；只持久化用户确认的项目级约定，单次覆盖写入本次记录。

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

相对配置路径以项目根为基准；本次相对路径以明确的项目根为基准，无项目时以当前工作目录为基准，实际操作前展示解析后的绝对路径。未约定的键省略；显式 `style_work: null` 表示草稿放在 Pack 根的 drafts/，`deliveries: null` 表示直接使用工作目录中的独立交付包，不是未回答。defaults 中的 null 仅表示没有默认选择。保留另一 Skill 使用的字段。

只确认了最终 Pack 根时，还需确认工作位置；等待答复期间可继续只读分析。指定完整 Pack 目录时直接使用，不额外追加 style-id。独立 style_work 根的草稿路径为 `<style_work>/<style-id>/<draft-id>/`。profiles 未设置时，本次配置快照放在已确认工作目录内；想保存为项目长期配置时再确定其位置。

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
      build.py
      scene.blend
      record.yaml
      renders/
      dependencies/
      runtime/                 # 本次涉及目标引擎时才创建
  versions/<version>/
    pack.yaml
    style.md
    evidence.yaml
    references/
    calibration/               # 获批样例、源文件及必要依赖
```

所有内部文件引用以包含该引用的文件所在目录为基准。锁定前把必需证据从工作目录实际复制进版本目录，修正相对引用；最终包不依赖临时目录、对话附件或包外符号链接。未获批尝试保留在工作区，不自动删除。

Blender 图片、库链接和材质节点的依赖同样检查：可打包的资源实际打包或复制为包内相对路径；不能因为 PNG 已复制，就忽略 `.blend` 仍引用原机器上的贴图/链接库。用搬到另一临时目录的副本重开验证依赖，不修改原件。

## Manifest 与证据

`index.yaml` 是可变索引，仅含 style_id、display_name、current_locked_version、草稿位置。精确版本内的 manifest 是入口：

```yaml
schema_version: 1
kind: model-style-pack
style_id: soft-miniatures
display_name: 柔和微缩风格
version: null
draft_id: d1
status: draft
style_file: style.md
evidence_file: evidence.yaml
self_contained: true
origin: null
```

以上是创建草稿的示例，不是已批准成品。status 为 draft / summary-confirmed / calibrating / locked；锁定时 version 写精确字符串，如 `"1"`，draft_id 可保留来源。ID 用稳定 slug，展示名可中文；冲突创建新 ID，不覆盖。不要把同样 schema_version 的栅格 Pack 当作此格式。

`style.md` 是唯一的视觉规则正文，包含：

- Style Spec：造型语言、表面语言、渲染观感、固定/可变/排除项，以及各自的参考依据。
- Series Scope：适用主体、附属元素及边界；不是某个角色的全部设计图或骨架合同。
- Blender Recipe：可重现样例观感的场景、材质、光照、相机和色彩管理设置，以及文件入口。
- 通俗摘要、假设、已知限制及实际校准覆盖。

`evidence.yaml` 示例：

```yaml
schema_version: 1
references:
  - id: ref-a
    file: references/ref-a.png
    storage: bundled
    source: null
    sha256: null
    role: style
    user_intent: null
    production_use: required
    observations: []
    hypotheses: []
summary_approval:
  approved: false
  user_statement: null
  recorded_at: null
calibration:
  approved_attempt: null
  record_file: null
  user_statement: null
  recorded_at: null
target_calibrations: []
feedback: []
```

role 可以是 style / identity / geometry / rendering；同一参考可拆成带不同意向的条目。production_use 为 required / optional / analysis-only，由已确认意向决定；用户明确依赖的维度不能降为可选。未经明确指定时根据实际用途解释选择，不强制用户填写。

默认把生产必需/可选参考及获批校准证据打包，记录实际 SHA-256。source 仅记录原绝对路径或 URL，不能作为自动重新下载/回退授权。仅用户明确不复制时使用 storage: external、file: 完整绝对路径、真实 sha256，并设置 self_contained: false，交付时列出依赖。失效或内容变更不能静默换图。analysis-only 材料可留在工作区并保留来源，但不得作为唯一的必要生产依据。

校准 `record.yaml` 至少保存：实际 brief、读取参考及角色、制作脚本/实际操作、source_blend、renders（视角与文件）、实际 Blender/渲染器版本、场景参数、依赖清单、自检、反馈及批准依据。每个渲染必须能追溯到具体源文件尝试；尚未产生的文件不能写成已有结果。未知工具身份、参数或版本用 null 并解释。

`target_calibrations` 的每项含 profile_id、profile_revision、profile_snapshot、record_file 和 status（unverified / passed / failed / blocked）。配置快照与验证记录实际存入包；status 描述该配置下的验证，不是所有平台的保证。

## 项目技术配置与视觉版本分离

目标配置至少记录 kind: model-target-profile、schema_version: 1、profile_id、revision，以及 engine、platform、camera、materials、deformation、conventions、budgets。只保存本项目的事实和约束；未知值为 null，不猜测 OS 支持范围或默认性能预算。生产流程会补齐影响当前交付的字段。

相机和光照可以同时有“视觉意图”和“具体实现”，两者不混写。例如 Style Spec 说明弱透视观感；项目若明确要求真实正交，就由目标配置约束实现，不能用长焦替代。Blender 节点树不被视为跨引擎 shader。

风格锁定表示用户认可了实际三维样例和规则，不等于目标引擎已验证。若本次目标包含引擎校准，缺少该验证时只能报告部分完成或受阻；可按用户认可范围交付视觉锁定版，但必须保留引擎未验证状态。未来增加新引擎适配时，保留核心版本，新增项目侧配置与验证记录，不反向写入锁定 Pack。

## 锁定与复用

锁定条件：摘要批准可追溯、真实三维样例获批、必要文件齐备、依赖及引用已检查。复制到新版本目录后才更新索引。已有 locked 目录只读；风格调整产生新草稿/版本。

- 参考重建：新 ID、新草稿，origin 记录来源；不继承旧批准来冒充新风格已验收。
- 原样复用/续作：复制指定锁定版本及全部必要依赖，保持 ID/精确版本及来源；或按用户指定只读引用共享库。
- 搬迁后核验真实文件与指纹。共享库的可变索引先解析成固定版本，本次任务不跟随 current/latest 漂移。

最终返回 Pack 绝对路径、style_id@version、风格状态、目标验证范围、规则及样例预览链接。生产 Skill 应只凭 Pack 与项目/资产输入即可工作，无需当前会话或重新运行建档。
