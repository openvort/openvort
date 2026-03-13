---
name: vortflow-component-architecture
description: 约束 VortFlow 工作项模块的前端代码组织方式，避免把 API 请求、行内编辑、详情面板、树结构、标签管理等逻辑继续堆进 WorkItemTable、WorkItemDetail、WorkItemCreate、ProTable 等大组件。修改 VortFlow 工作项页面、ProTable 扩展、或新增工作项交互能力时使用。
---

# VortFlow 组件架构 Skill

## 适用范围

当任务涉及以下任一内容时，先使用本 Skill 再开始编码：

- `web/src/views/vortflow/WorkItemTable.vue`
- `web/src/views/vortflow/work-item/WorkItemDetail.vue`
- `web/src/views/vortflow/work-item/WorkItemCreate.vue`
- `web/src/views/vortflow/work-item/useWorkItemCommon.ts`
- `web/src/components/vort-biz/work-item/*.vue`
- `web/src/components/vort-biz/pro-table/ProTable.vue`
- 新增 VortFlow 工作项列表、详情、创建、行内编辑、表格扩展能力

## 目标

核心目标只有两个：

1. 保持页面组件是“页面壳”，负责组装，不负责堆积业务细节。
2. 让逻辑按职责落位，新增功能时优先扩展既有边界，而不是往大文件中间插 100 行。

## 当前模块边界

### 页面层

- `web/src/views/vortflow/Stories.vue`
- `web/src/views/vortflow/Tasks.vue`
- `web/src/views/vortflow/Bugs.vue`

这些文件应继续保持为轻薄入口，只负责传 `type`、标题、开关参数给 `WorkItemTable`。

### 工作项主页面

- `web/src/views/vortflow/WorkItemTable.vue`

职责只允许包含：

- 页面级状态装配
- 组合多个 composable
- 传参给 `ProTable`
- slot 模板渲染
- 抽屉开关与页面级路由联动

不应继续沉积：

- 大段 API 查询拼装
- mock 数据生成
- 各字段 setter/getter 与回滚逻辑
- 标签颜色和折叠算法
- 需求树缓存与展开加载
- 详情评论/日志/描述编辑的内部实现

### 公共逻辑层

- `web/src/views/vortflow/work-item/useWorkItemCommon.ts`
- `web/src/components/vort-biz/work-item/WorkItemTable.types.ts`

这里适合放：

- 类型定义
- 状态/优先级/成员公共映射
- 与单个页面无关的纯函数

这里不适合放：

- 页面级 `ref/reactive`
- 抽屉开关状态
- 与某个表格实例强绑定的缓存

### 交互组件层

- `web/src/components/vort-biz/work-item/WorkItemFilters.vue`
- `web/src/components/vort-biz/work-item/WorkItemPriority.vue`
- `web/src/components/vort-biz/work-item/WorkItemStatus.vue`
- `web/src/components/vort-biz/work-item/WorkItemTagPicker.vue`
- `web/src/components/vort-biz/work-item/WorkItemMemberPicker.vue`

这些组件负责“单一交互单元”，不要反向承接页面级数据请求或整页状态。

### 通用表格层

- `web/src/components/vort-biz/pro-table/ProTable.vue`

这是基础能力组件，只承载表格通用行为，不承载任何 VortFlow 业务。

## 强制拆分规则

### 规则 1：先判断职责，再写代码

收到需求后，必须先判断新增逻辑属于哪一类：

- 数据请求/响应映射
- 行内编辑
- CRUD
- 详情面板
- 标签管理
- 树结构
- 纯展示模板
- 通用表格能力

没有先判断职责边界，不得直接往 `WorkItemTable.vue` 或 `ProTable.vue` 追加实现。

### 规则 2：以下逻辑必须提取成 composable

如果新增或修改的是下面这些逻辑，必须优先落到 composable：

- 列表请求、筛选、分页、排序、后端数据映射
- 乐观更新、失败回滚、字段级同步
- 新建/删除/批量删除/表单初始化
- 评论、日志、描述编辑、关联工作项加载
- 标签颜色、折叠显示、标签弹窗
- 树形展开、子节点缓存、懒加载

推荐文件名：

- `useWorkItemRequest.ts`
- `useWorkItemInlineEdit.ts`
- `useWorkItemCrud.ts`
- `useWorkItemDetail.ts`
- `useWorkItemTags.ts`
- `useStoryTree.ts`

### 规则 3：以下逻辑允许留在页面组件

可以直接留在 `WorkItemTable.vue` 的只有：

- `computed` 后的列定义装配
- slot 模板
- 抽屉和 tab 的页面级开关
- composable 返回值的拼接和转交
- 路由 query 与页面可见状态的同步

### 规则 4：纯函数优先下沉

满足以下条件的逻辑优先提成纯函数，不要放在组件里：

- 不依赖 DOM
- 不依赖组件实例
- 只做数据映射/格式化/判定

例如：

- `mapBackendItemToRow`
- `normalizeDateValue`
- `getCollapsedTags`
- `createOwnerMatcher`

## 文件落位约定

### 新增 VortFlow 业务逻辑

默认落在：

- `web/src/views/vortflow/work-item/`

原因：

- 它是页面级业务逻辑，不应塞进 `components/vort-biz`
- 它不是全局通用逻辑，不应塞进 `hooks/`

### 新增可复用 UI 交互单元

默认落在：

- `web/src/components/vort-biz/work-item/`

例如：

- 状态选择器
- 标签选择器
- 成员选择器
- 筛选条

### 新增通用表格能力

默认落在：

- `web/src/components/vort-biz/pro-table/`

如果能力包含明显独立子问题，优先抽成：

- `useColumnResize.ts`
- `useFixedColumns.ts`
- `useScrollShadow.ts`
- `useColumnWidth.ts`

## 行数红线

这是架构预警线，不是“可以偶尔突破”的建议。

- 页面组件的 `script` 目标上限：300 行
- 页面组件的 `template` 目标上限：250 行
- 通用组件的 `script` 目标上限：500 行

当一个文件已经明显超过上限时：

1. 禁止继续在原文件中堆新职责。
2. 先拆分，再实现需求。
3. 如果用户明确要求“只做最小改动”，也应尽量把新逻辑放进新增 composable，而不是继续加深耦合。

## ProTable 特别规则

### 可放在 `ProTable.vue` 的内容

- 排序、分页、选择、固定列、滚动阴影、多级表头、列宽调整等表格共性能力
- 与 UI 结构强绑定且只服务表格的状态

### 不可放在 `ProTable.vue` 的内容

- 任何 VortFlow 专属字段逻辑
- 任何“工作项”概念
- 针对某个业务页面的临时特判

### 扩展 ProTable 的默认策略

新增表格能力时按以下顺序判断：

1. 能否只通过 `props + slot` 实现？
2. 能否新增 `types.ts` 配置项并复用已有机制？
3. 若新增独立状态机，能否抽成 composable？
4. 只有当逻辑与表格渲染生命周期强绑定时，才直接写进 `ProTable.vue`

## 开发决策树

按下面顺序判断落点：

```text
新需求
 -> 是纯展示模板吗？
    -> 是：写在页面 slot/template
    -> 否：
       -> 是字段级交互或乐观更新吗？
          -> 是：放 useWorkItemInlineEdit
          -> 否：
             -> 是列表查询/映射/分页吗？
                -> 是：放 useWorkItemRequest
                -> 否：
                   -> 是创建/删除/提交吗？
                      -> 是：放 useWorkItemCrud
                      -> 否：
                         -> 是详情评论/日志/描述吗？
                            -> 是：放 useWorkItemDetail
                            -> 否：
                               -> 是标签逻辑吗？
                                  -> 是：放 useWorkItemTags
                                  -> 否：
                                     -> 是需求树展开/缓存吗？
                                        -> 是：放 useStoryTree
                                        -> 否：
                                           -> 是通用表格能力吗？
                                              -> 是：放 ProTable 子模块
                                              -> 否：重新审视职责，不要直接堆进页面
```

## Bad Pattern

### 反例 1：在页面里继续添加字段更新逻辑

坏味道：

- 在 `WorkItemTable.vue` 新增一组 `getRowXxx` / `setRowXxx`
- 同时新增一个 `reactive<Record<string, boolean>>` 作为弹层开关
- 再加一段 API 同步和失败回滚

这类代码必须进入 `useWorkItemInlineEdit.ts`。

### 反例 2：把树结构逻辑塞进标题列 slot

坏味道：

- 点击展开
- 缓存子节点
- 懒加载
- 展开态恢复

这些不属于模板渲染，必须进入 `useStoryTree.ts`。

### 反例 3：为了一个业务需求修改 ProTable 内部判断

坏味道：

- `if (column.dataIndex === "xxx")`
- `if (record.type === "需求")`
- `if (title === "工作编号")`

这会让通用组件被业务污染，禁止。

## Good Pattern

### 正例 1：页面只负责装配

好模式：

- 页面拿到 `columns`
- 页面拿到 `request`
- 页面拿到 `rowSelection`
- 页面把 slot 渲染给 `ProTable`

而具体行为来自 composable。

### 正例 2：字段交互集中管理

好模式：

- `useWorkItemInlineEdit.ts` 对外只暴露：
  - `pickerOpenMap`
  - `getRowXxx`
  - `setRowXxx`
  - `toggle/open` 辅助方法

这样新增一个字段交互时，只扩展一个地方。

### 正例 3：请求层统一封装

好模式：

- `useWorkItemRequest.ts` 统一处理：
  - mock/API 双模式
  - 后端结构转前端行结构
  - 多状态合并
  - pinned rows 合并

页面只拿 `request(params)`。

## 执行步骤

每次修改前按这个顺序执行：

1. 先确认变更属于哪个职责域。
2. 查找是否已有对应 composable 或组件可扩展。
3. 若已有边界，优先在原边界内修改。
4. 若没有边界，先新增边界文件，再写实现。
5. 完成后检查页面组件是否仍然只是“装配层”。

## 命名约定

- composable 统一使用 `useXxx.ts`
- 纯函数文件优先用语义名，不要用 `utils.ts`
- “行内编辑”统一称为 `inline edit`
- “页面壳”统一指负责装配的顶层页面组件

## 参考文档

需要更详细的模块关系、拆分建议和 composable 签名时，读取：

- [ARCHITECTURE.md](ARCHITECTURE.md)
