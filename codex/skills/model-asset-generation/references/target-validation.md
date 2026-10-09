# 目标配置与最小引擎验收

## 配置是项目输入，不是通用风格

正式交付包含最小目标引擎验证场景。先读取项目说明/已有 profile 和可用 SDK；只问影响本次结果的未知。用户只要求粗模、规格或源文件时可缩小范围并记录，不将其伪称为完整运行时交付。

配置快照示例，示意当前可选场景，不是所有项目的默认值：

```yaml
schema_version: 1
kind: model-target-profile
profile_id: ios-character
revision: "1"
engine: {name: realitykit, version: null, renderer: null}
platform: {os: ios, minimum_version: null, test_target: null}
camera: {projection: orthographic}
materials: {system: ShaderGraph, parameters: []}
deformation: {skeleton: required, morph_weights: runtime}
conventions: {unit_meters: null, up_axis: null, forward_axis: null, origin: null}
budgets: {triangles: null, texture_size: null, bone_influences: null}
export: {format: null, settings: {}}
```

未知值用 null；无需在开始建模前逼用户填写所有字段。影响结构或导出可行性的版本、格式、形变能力要在精修前通过工具探测/最小技术探针解决；影响真机性能的预算在要求性能验收时明确。文件名、转换格式和 SDK 支持不能从作品风格猜出。

制作记录固定 profile_id、revision 和实际快照/指纹。新引擎、新渲染后端或会改变外观的配置产生新的适配及验收记录；不要修改锁定的 Pack 核心规则，也不要沿用另一配置的 passed。

## 最小场景包含什么

在本次解析的工作根内建立独立验证工程或用户指定的现有预览目标。默认不修改正式 App 的入口、依赖、业务数据或运行时状态机；用户指定现有工程时控制在验收需要的范围。

- 加载本次实际交付文件，记录版本/指纹，排除旧缓存或旧资源。
- 使用目标要求的相机、材质、光照、背景和色彩设置，并保留可复现入口。
- 展示关键视角；需要骨架/形变时提供最小按钮、滑杆或测试脚本，能修改约定通道和姿态并重置。
- 提供运行说明、实际工具/SDK/设备或模拟器信息、证据文件与通过/失败项。

界面只为检查，不扩展为正式 App 产品设计。检查资产技术行为，不要求复刻“打开应用问好”“点屏幕看向”等正式业务交互。多个独立模型可以共享验证工程，但每项结果、版本和控制合同独立记录。

## RealityKit / RealityView 分支

先查看实际 Xcode/SDK 的接口和 availability，必要时查当前官方文档，不从网络摘要猜最低 iOS 版本。RealityView 容器、相机、shader 材质、网格和变形接口是不同层次，逐项验证。

- 真实正交：按当前 SDK 使用对应相机能力，并运行确认被场景实际采用；不能用远距离/长焦透视替代明确的正交要求。[官方正交相机说明](https://developer.apple.com/documentation/realitykit/orthographiccameracomponent)
- ShaderGraph：按目标环境实现或加载需要的材质，核查参数可访问与实际画面；不假定 Blender shader 节点可直接导出为该材质。[ShaderGraphMaterial](https://developer.apple.com/documentation/realitykit/shadergraphmaterial)
- 运行时形变：检查导入资源真实保留的目标、名称/映射及权重修改效果，不能只创建一个空组件或用源文件的索引猜测。[BlendShapeWeightsComponent](https://developer.apple.com/documentation/realitykit/blendshapeweightscomponent) 与 [权重名称映射](https://developer.apple.com/documentation/realitykit/blendshapeweightsmapping)
- 骨架：验证项目需要的关节能以所需方式被驱动，并与形变同时工作；材质成功载入不证明角色绑定可用。

选择 USD/USDZ 或其他桥接路径前先做小样实测，不承诺任意格式能保存全部特性。保留各转换步骤与资源重命名关系；如果管线丢失关键形变/蒙皮，报告并调整路径，不能通过删掉需求来交付。

## Godot 分支

读取选定版本和渲染后端。例如用户指定 Forward+ 时，导入/渲染/检查均对该后端进行；不能无说明地退到 Compatibility 并宣称同等验收。

glTF/GLB 可作为待验证的交换路径。Godot 的 `.blend` 导入也经过 [Blender/glTF 链路](https://docs.godotengine.org/en/stable/classes/class_editorsceneformatimporterblend.html)，不是对源 `.blend` 完整语义的直接执行。检查材质、单位轴向、Skeleton3D/Skin 和形变目标的实际导入结果。

需要目标专有材质时在 Godot 中实现并保存。不要把一个引擎的 shader 当通用文件；例如 Godot 自身导出 glTF 时也有 [ShaderMaterial 导出限制](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/exporting_3d_scenes.html)。形变先按真实名称定位，再读写并检查效果，参考 [MeshInstance3D](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)。

这些是执行时查证的入口，不是写死的版本兼容表。新增引擎按同一验收合同扩展，不强迫用户换回 RealityKit 或 Godot。

## 分层验收，不能互相冒充

| 层级 | 需要的真实证据 | 不能替代它的东西 |
| --- | --- | --- |
| 源文件 | 搬迁副本重开、必要依赖可解析、实际源数据 | 文件存在、后缀正确 |
| 视觉 | 查看代表视角，按 Pack 比较形体/材质/光影 | 脚本成功、面数统计 |
| 引擎载入 | 目标环境加载交付版本且关键结构存在 | 导出器返回成功 |
| 运行时功能 | 姿态/权重中间值及组合的实际变化 | 仅编译成功、参数声明存在 |
| 目标画面 | 指定后端/设备或明确范围内的模拟器截图与观察 | Blender 渲染、headless 导入 |
| 用户认可 | 用户对实际预览的明确反馈 | 助手自检、没有回复 |

检查要求的真实投影、材质参数、法线/阴影、贴图、比例/轴向及适用控制；有约定预算再检查实际导出大小和目标性能，不捏造真机帧率。模拟器验证如实标注，不扩大成真机性能通过。

每项验证报告含 expected、observed、status、evidence，以及环境、运行命令/入口和实际资源指纹。对应测试未执行用 unverified；环境缺失导致无法继续用 blocked；执行但不满足用 failed。技术检查通过不自动批准审美，用户认可也不豁免技术缺陷。

无法运行指定引擎时，保留已完成源文件/导出/场景并标记部分交付，附复现步骤和明确的缺少项。若只能让用户执行必要运行检查，等待其实际结果再更新状态；不能制造截图或声称全部完成。仅在所有本次必需检查有证据通过时写 engine_validation: passed。
