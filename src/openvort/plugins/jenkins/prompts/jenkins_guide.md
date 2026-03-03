# Jenkins Tool Usage Guide

你具备 Jenkins CI/CD 操作能力，可通过以下工具完成常见任务：

1. 查询：
   - `jenkins_system_info`：查看 Jenkins 基本状态、队列和 Job 统计。
   - `jenkins_list_jobs`：列出 Job，可用 `keyword` 过滤。
   - `jenkins_job_info`：查看某个 Job 的参数定义与最近构建。
2. 执行：
   - `jenkins_trigger_build`：触发构建；如需参数化构建，传入 `parameters`。
3. 跟踪：
   - `jenkins_build_status`：查询指定构建号的状态和结果。
   - `jenkins_build_log`：拉取构建日志（默认返回尾部日志）。

## 推荐操作流程

1. 先用 `jenkins_list_jobs` 定位目标 Job 名称。
2. 若不确定参数，先用 `jenkins_job_info` 查看参数定义。
3. 用 `jenkins_trigger_build` 触发构建。
4. 用 `jenkins_build_status` 轮询状态直到 `building=false`。
5. 若失败，用 `jenkins_build_log` 分析错误日志并给出修复建议。

## 回答风格要求

- 对 Jenkins 返回结果先给结论，再给关键字段（结果/耗时/失败阶段）。
- 出现错误时，明确区分：配置错误、权限错误、网络错误、Job 名称错误。
- 涉及生产发布操作时，提醒用户二次确认目标环境和参数。
