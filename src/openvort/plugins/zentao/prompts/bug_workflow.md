# 禅道 Bug 处理流程

当用户提到 Bug 相关操作时，按以下规则处理：

## 创建 Bug
- 必须明确：所属产品、Bug 标题、复现步骤
- 可选：严重程度、优先级、指派人、Bug 类型
- 如果用户只说了问题描述没说产品，尝试从上下文推断或询问

## 查询 Bug
- "我的Bug" → 用 zentao_my_bugs 查询，account 为发消息的人
- 查询结果按严重程度和优先级排序

## Bug 严重程度
- 1=致命：系统崩溃、数据丢失
- 2=严重：核心功能不可用
- 3=一般：功能异常但有替代方案
- 4=轻微：UI 问题、文案错误

## Bug 类型
- codeerror=代码错误
- config=配置相关
- performance=性能问题
- security=安全问题
- designdefect=设计缺陷
- others=其他

## Bug 已处理反馈
当用户说"修好了/处理完了/已修复"时：
- 确认 Bug ID
- resolution 判断：修好了→fixed，不是Bug→bydesign，复现不了→notrepro

## 更新 Bug
- 用 zentao_update_bug 可以：编辑标题/步骤、追加截图、修改严重程度/优先级、指派、确认、解决、关闭
- 用户说"给 Bug #xxx 加张图/补充步骤/改标题"等 → 用 zentao_update_bug
- 追加内容用 append_steps（不覆盖原有步骤），完整替换用 steps
- 解决 Bug：status="resolved" + resolution（fixed/bydesign/notrepro 等）
- 关闭 Bug：status="closed"

## 注意事项
- 创建 Bug 时 steps 字段支持 HTML，可以包含图片链接
- 所有写操作使用 openVortAi 作为 actor

## 图片处理
- 当用户发送了图片（截图），系统会自动注入 `_image_urls` 到工具参数中
- 创建或更新 Bug 时，把 `_image_urls` 中的 URL 传入 `image_urls` 参数，图片会自动嵌入 steps 字段
- 图片在 steps 中以 `<img src="url">` 形式展示，禅道可直接渲染
- 即使用户没有明确说"附上截图"，只要上下文中有图片且与 Bug 相关，都应传入 image_urls
- 给已有 Bug 追加截图：用 zentao_update_bug，传入 bug_id + image_urls 即可
