# 禅道需求管理流程

当用户提到需求相关操作时，按以下规则处理：

## 创建需求
- 必须明确：所属产品、需求标题、需求描述
- 可选：优先级、预计工时、指派人、需求类型
- 如果用户只说了需求内容没说产品，尝试从上下文推断或询问
- 需求类型：feature=功能、interface=接口、performance=性能、safe=安全、experience=体验、improve=改进、other=其他

## 查询需求
- "我的需求" → 用 zentao_my_stories 查询，account 为发消息的人
- "XX的需求" → 用对应人的 account 查询
- 可按状态筛选：active（待处理）、closed（已关闭）、all（全部）

## 更新需求
- "改一下需求标题/描述" → 用 zentao_update_story，传 title/spec
- "给需求补充说明" → 用 append_spec 追加，不覆盖原有描述
- "给需求加张截图" → 传 image_urls，图片自动追加到描述末尾
- "需求完成了" → status="closed"，closed_reason="done"
- "需求不做了" → status="closed"，closed_reason="cancel"
- "把需求指派给XX" → 传 assigned_to

## 注意事项
- 所有写操作使用 vortFlowAi 作为 actor
- 需求描述（spec）存在 zt_storyspec 表，支持 HTML
- 回复时使用中文名而非账号 ID
- 优先级：1=紧急 2=高 3=中 4=低

## 图片处理
- 当用户发送了图片，系统会自动注入 `_image_urls` 到工具参数中
- 创建或更新需求时，把 `_image_urls` 中的 URL 传入 `image_urls` 参数
- 即使用户没有明确说"附上截图"，只要上下文中有图片且与需求相关，都应传入 image_urls
