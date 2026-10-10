# 当前状态与运行控制

## 一份当前控制，历史只存引用

沿用项目已有布局；没有约定时可用 `.work/iterations/<run-id>/`，放 `state.json`、本轮计划、工作者结果及报告。原始证据和候选分开存储，永久规则不要混入每轮状态。

协调者是控制文件唯一写入者。工作者写自己的结果文件，协调者核对后登记；不要让多个角色各自重写全份状态。`run_control.py` 使用进程文件锁、预期 revision 和原子替换阻止并发覆盖，但不能阻止人为绕过脚本编辑。

顶层字段：schema_version、run_id、revision、coordinator_id、project_root、started_at_utc、close_at_utc、deadline_utc、status、phase、current。只有 status 是保存状态的权威；不要另外添加 active、automation_status 等同义顶层字段。

| current 字段 | 内容 |
| --- | --- |
| scope_revision / scope_path | 当前计划版本和文件引用；计划内容变化也应递增版本 |
| tasks | 当前任务 ID、角色、输入版本、结果路径与状态等简短记录 |
| latest_candidate | 最新候选 ID、精确版本、清单和运行入口等引用 |
| last_verified_candidate | 最后客观通过的精确 version、report，可加 entry、candidate_id |
| review | 当前范围和候选的评审摘要、结论及报告引用 |
| execution | 当前执行机制、自动化 ID、授权来源、停止原因或停止确认引用 |
| final_report | 本轮最终报告路径 |

历史轮次、旧报告和日志保留在原文件中，不嵌入 current。改变候选或范围时清空不再适用的 review；last_verified_candidate 仍可指向上一达标版本。控制器不验证验收报告的真实性，协调者须核对准确版本、范围和实际证据后才能登记通过。

停止原因保存在 execution.stop_reason，自动验收结论、未覆盖项和人工待评项保存在 review 及其报告中，复用现有字段即可。stopped 仅表示本轮已结束，不代表验收通过或人工认可。自动验收达标、待人工最终复核的轮次正常收尾，无需保持 active；先登记候选与评审再停止，截止后仍只整理已经存在的事实。

## 使用脚本

以下尖括号内容替换为实际值；Python 3 标准库即可运行。每轮使用独立 state 路径，init 拒绝覆盖已存在的文件。

```text
python <skill-dir>/scripts/run_control.py init --state <run-dir>/state.json --run-id <run-id> --project-root <absolute-project-root> --coordinator-id <coordinator-id> --hours 2
python <skill-dir>/scripts/run_control.py check --state <run-dir>/state.json
```

`--hours 2` 只是调用示例，不是默认预算。已有绝对截止时用 `--deadline-utc 2026-10-09T12:00:00Z` 这样的实际 UTC 时间，替代 hours；不得将示例时间直接用于新轮次。初始化后预算固定。`--closing-minutes` 默认 5，短轮次最多留总预算五分之一收尾，可在初始化时按实际成本设置。

check 只读：报告 status、effective_state、revision、remaining_seconds、closing、may_work、may_start_task。保存状态可能仍是 active，但实际 effective_state 已 expired；行动时必须使用有效状态判断。

- may_work=false：暂停、停止或到期，不做开发、测试、合并和派单。
- closing=true：允许完成来得及收尾的已有工作，准备交付；may_start_task=false，不新开改进批次。
- check 不改变状态、不唤醒任务、不结束进程。需要停止时由协调者显式 stop 并执行外部收尾。

## 更新与状态转换

写入须提供记录中的 coordinator_id 和最新 expected_revision。协调者 ID 是防误写标识，不是安全认证。update 的补丁键是 phase 或 current 中的白名单字段，脚本将其放在对应位置；预算、run_id、身份及 status 不能通过补丁改写。

在补丁文件中写：

```json
{
  "phase": "development",
  "scope_revision": 1,
  "scope_path": "本轮计划的实际路径"
}
```

然后执行：

```text
python <skill-dir>/scripts/run_control.py update --state <run-dir>/state.json --coordinator-id <coordinator-id> --expected-revision 0 --patch-file <patch-file>
python <skill-dir>/scripts/run_control.py pause --state <run-dir>/state.json --coordinator-id <coordinator-id> --expected-revision <current-revision>
python <skill-dir>/scripts/run_control.py resume --state <run-dir>/state.json --coordinator-id <coordinator-id> --expected-revision <current-revision> --authorization <human-resume-reference>
python <skill-dir>/scripts/run_control.py stop --state <run-dir>/state.json --coordinator-id <coordinator-id> --expected-revision <current-revision> --reason <stop-reason>
```

每次成功写入 revision 加一，读取最新值后再操作。scope_revision 不能回退，scope_path 改变需版本递增；同路径计划内容变化的递增由协调者负责。

pause 只响应用户明确暂停。resume 只恢复未到期的 paused 状态，必须引用用户明确恢复指令，原截止不变。stopped 为终态，不能 resume；用户启动新轮次时另建 run_id 和预算。

暂停、停止或到期后 update 只允许 phase、review、execution、final_report 的收尾元数据；不能登记新候选、达标版本或需求变更。这些收尾字段记录已有事实，不能启动新验证或伪造通过。

退出码：0 成功；2 参数或格式拒绝；3 当前不允许工作或转换；4 revision 冲突、重复初始化或范围回退；5 锁繁忙；6 文件或 JSON 错误。失败时读取 JSON 原因，不把“命令已返回”当成功。冲突先重新核对状态和行动必要性，不能盲目重复原写入。

## 恢复步骤

先读取 state 和 check，再核对准确 run_id、范围版本、候选及实际任务进度。已处理交付按任务 ID 和版本去重；不能凭旧报告触发当前通过，也不能重新派发正在正常执行的工作。到期只整理已存在结果和停止确认。

状态工具不是调度器，也不是进程守护器。后台续跑和运行中截止检查见 [持续执行与调度](execution.md)。
