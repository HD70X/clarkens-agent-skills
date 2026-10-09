# Blender 与校准场景

## 先探测执行路径

发现当前 Blender 可执行文件并读取版本/帮助；不硬编码某台电脑的安装路径或版本。优先现有 CLI/Python 或已配置的 Blender 工具，不假定存在专用插件。检查本次操作需要的导入导出支持及渲染能力；仅有 `--version` 成功还不是完整链路验证。

Codex 根据本次候选规则和参考，在已有制作授权内编写建模/材质/渲染脚本，保留脚本与参数及未确认假设。不要求用户先写专业提示词。Blender Python 应在实际 Blender 进程中运行；外部 Python 能否 import bpy 不是必要条件。

命令形状示例，实际路径须先解析；按本机 `--help` 核对参数：

```text
<blender> --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python <build-script> -- <script-arguments>
```

命令行选项按顺序生效，加载 `.blend` 会带入场景设置，应在加载后设置本次输出。参考 [Blender 命令行文档](https://docs.blender.org/manual/en/5.1/advanced/command_line/arguments.html)，执行时仍以安装版本为准。

不启用不明 `.blend` 的自动脚本，不运行参考目录里的任意代码；仅执行当前任务编写或审阅过的脚本。已有用户场景用副本/新文件工作，不清空当前 UI 场景或覆盖原件。重试用独立 attempt；脚本尽量显式选择对象、集合和路径，避免依赖当前 UI 选中项。

## 可验收的最小样例

输出实际网格、材质及校准相机/光照。复杂形体允许先粗模再精化，但不能把默认几何体拼接、二维贴片或一个漂亮视角当作已经符合设计。根据参考确认关键轮廓、部位连接和多方向可读性；细节密度服务风格，不机械增加面数。

保存 `.blend`、实际生成脚本、贴图/链接资源和预览；记录渲染引擎、相机投影/变换、光照、背景、分辨率及色彩管理。看实际渲染文件再下视觉结论，不能只读日志或提示词。

若使用驱动、程序化材质或 modifier，记录对样例的影响和依赖；它们在 Blender 中有效不证明导出后有效。校准对象不默认需要正式角色绑定。若可调外观本身是风格要点，选择最小的变化状态作样例，并明确验证范围。

## 目标引擎校准（本次需要时）

先读取具体目标配置、SDK/引擎版本和已有项目约定。最小场景只负责载入样例、复现相机/材质/光照，并展示需验证的状态，不接入正式 App 业务逻辑。保存场景和运行方法到本次解析的工作目录；如果用户指定现有预览项目，修改仅限明确的验证范围。

不要提前承诺某个中间格式能保留全部效果。先用小样验证材料、层级及本次依赖的形变/骨架是否保留，再制作复杂适配。Blender 的 shader 节点不能被默认为 RealityKit ShaderGraph 或 Godot ShaderMaterial；需在目标环境实现并检查。

- RealityKit 项目：核对当前 SDK/最低系统版本，再实现所需 RealityView、相机、ShaderGraph 材质及权重控制。用户要求真实正交时，不能悄悄换成远距离透视；参考 [正交相机](https://developer.apple.com/documentation/realitykit/orthographiccameracomponent) 和 [ShaderGraphMaterial](https://developer.apple.com/documentation/realitykit/shadergraphmaterial)，以实际 SDK 和运行结果确认。
- Godot 项目：按选定版本及渲染后端建立最小场景；Forward+ 的视觉结果不能由另一个后端截图代替。`.blend` 的导入仍涉及 [glTF 导入链路](https://docs.godotengine.org/en/stable/classes/class_editorsceneformatimporterblend.html)，应检查真实导入结果，不只查看源文件。

参考链接用于查找当前官方资料，不是已验证版本清单。把运行环境（真机/模拟器/桌面、版本、后端）、载入的源版本、实际截图和结论记入验证记录。只编译、headless 导入或 Blender 渲染不能证明目标画面已经检查；缺少可运行环境时明确 unverified/blocked，交付已完成部分与可复现步骤，不捏造通过。
