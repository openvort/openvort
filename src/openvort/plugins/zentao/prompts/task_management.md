# 禅道任务管理流程

当用户提到任务相关操作时，按以下规则处理：

## 创建任务
- 必须明确：任务名称、所属迭代
- 可选：负责人、优先级、预计工时、任务描述、关联需求
- 如果用户没指定迭代，询问确认
- 如果用户没指定负责人，可以先不指派

## 查询任务
- "我的任务" → 用 zentao_my_tasks 查询，account 为发消息的人
- "XX的任务" → 用对应人的 account 查询
- 查询结果按优先级排序展示，包含任务名、状态、迭代

## 更新任务
- "任务完成了" → 用 zentao_update_task，action=finish
- "把任务指派给XX" → action=assign
- "开始做XX任务" → action=update_status，status=doing
- "改一下任务名称/描述" → 不传 action，直接传 name/desc 字段
- "给任务补充说明" → 用 append_desc 追加，不覆盖原有描述
- "给任务加张截图" → 传 image_urls，图片自动追加到描述末尾

## 记录工时
- "今天在XX上花了4小时" → 用 zentao_log_effort
- 需要明确：任务 ID、消耗时间、剩余时间

## 注意事项
- 所有写操作使用 openVortAi 作为 actor
- 回复时使用中文名而非账号 ID
- 优先级：1=紧急 2=高 3=中 4=低
