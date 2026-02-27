# OpenVort 前端开发 Skill

开发 OpenVort Web 前端页面时，必须遵循以下规范。**核心原则：优先使用 Vort 组件库，禁止在有对应 Vort 组件的场景下使用原生 HTML 元素或第三方 UI 库。**

## 触发条件

- 新增/修改 `web/src/views/` 下的页面组件
- 使用 Vort / Vort-Biz 组件
- 创建列表页、表单页、详情页

## 技术栈

- Vue 3 + TypeScript + Composition API (`<script setup lang="ts">`)
- Tailwind CSS（布局和间距）
- lucide-vue-next（图标）
- Vort 组件库（通过 VortResolver 自动导入，无需手动 import）

## Vort-First 原则

**所有 UI 开发必须优先使用 Vort 组件，不允许用原生 HTML 或第三方库替代：**

| 场景 | ✅ 正确 | ❌ 错误 |
|------|---------|---------|
| 按钮 | `<VortButton>` | `<button>`, `<a-button>`, `<el-button>` |
| 输入框 | `<VortInput>` | `<input>`, `<a-input>` |
| 表格 | `<VortTable>` | `<table>`, `<a-table>`, `<el-table>` |
| 弹窗 | `<VortDialog>` / `DialogForm` | `<a-modal>`, `<el-dialog>` |
| 下拉选择 | `<VortSelect>` | `<select>`, `<a-select>` |
| 表单 | `<VortForm>` / `<VortFormItem>` | `<form>`, `<a-form>` |
| 消息提示 | `message.success()` | `ElMessage`, `antd message` |
| 确认弹窗 | `dialog.confirm()` / `<DeleteRecord>` | `ElMessageBox`, `Modal.confirm` |
| 表格操作列 | `<TableActions>` + `<TableActionsItem>` | 手写 `<a>` 链接 + `<VortDivider>` |
| 搜索栏 | `<SearchToolbar>` 组合 | 手写搜索表单布局 |
| 删除操作 | `<DeleteRecord>` | 手写 confirm + API 调用 |
| 弹窗表单 | `<DialogForm>` | 手写 Dialog + 表单逻辑 |
| 气泡编辑 | `<PopForm>` | 手写 Popover + 输入框 |
| 批量操作 | `<BatchActions>` | 手写批量删除按钮 |

## 组件自动导入

所有在 `resolver.ts` 中注册的组件均通过 `unplugin-vue-components` 自动导入，模板中直接使用，无需 import。

消息提示和命令式 API 需要手动 import：
```ts
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { notification } from "@/components/vort/notification";
```

## 基础组件 (vort/) 关键用法

### VortButton

```vue
<!-- variant: "primary" | "default" | "dashed" | "text" | "link" | "plain" | "soft" -->
<VortButton variant="primary" @click="handleSave">保存</VortButton>
<VortButton variant="primary" :loading="saving">提交</VortButton>

<!-- danger 是独立 boolean prop，不是 variant -->
<VortButton danger @click="handleDelete">删除</VortButton>
<VortButton variant="primary" danger>危险操作</VortButton>

<!-- 带图标 -->
<VortButton variant="primary">
    <Plus :size="14" class="mr-1" /> 新增
</VortButton>

<!-- size: "large" | "middle" | "small" -->
<VortButton size="small">小按钮</VortButton>
```

### VortTable + VortTableColumn

```vue
<VortTable
    :data-source="list"
    :loading="loading"
    row-key="id"
    :pagination="false"
    :row-selection="rowSelection"
>
    <VortTableColumn label="名称" prop="name" />
    <VortTableColumn label="操作" :width="160" fixed="right">
        <template #default="{ row }">
            <!-- slot 参数: { value, row, index, column }，不是 record -->
        </template>
    </VortTableColumn>
</VortTable>
```

Props 命名注意：用 `label`（不是 title）、`prop`（不是 dataIndex）。

#### 行选择（rowSelection）

```ts
const selectedIds = ref<string[]>([]);

const rowSelection = computed(() => ({
    selectedRowKeys: selectedIds.value,
    onChange: (keys: (string | number)[]) => {
        selectedIds.value = keys as string[];
    },
    // 可选配置：
    // type: "checkbox" | "radio"  // 默认 checkbox
    // fixed: true                 // 固定在左侧
    // columnWidth: "48px"
    // hideSelectAll: false
    // getCheckboxProps: (record) => ({ disabled: record.isAdmin })
}));
```

### VortTabs + VortTabPane

```vue
<VortTabs v-model:activeKey="activeTab">
    <!-- 注意：用 tab-key，不是 key（key 是 Vue 内置属性，不会传给组件） -->
    <VortTabPane tab-key="list" tab="列表">内容</VortTabPane>
    <VortTabPane tab-key="detail" tab="详情">内容</VortTabPane>
</VortTabs>
```

### VortTag

```vue
<!-- 预设颜色: red, blue, green, orange, purple, cyan, gold, magenta, volcano, lime, geekblue, teal -->
<!-- 状态颜色: success, processing, error, warning, default -->
<VortTag color="green">启用</VortTag>
<VortTag color="red">禁用</VortTag>

<!-- 可关闭 / size / 其他 props: bordered, plain, white, solid -->
<VortTag closable @close="handleClose">可关闭</VortTag>
<VortTag size="small" color="blue">小标签</VortTag>
```

### VortDrawer / VortDialog

```vue
<VortDrawer :open="drawerOpen" title="标题" :width="480" @update:open="drawerOpen = $event">
    <!-- 内容 -->
    <template #footer>底部按钮</template>
</VortDrawer>

<VortDialog :open="dialogOpen" title="标题" @update:open="dialogOpen = $event">
    <!-- 内容 -->
</VortDialog>
```

### VortForm

```vue
<VortForm label-width="100px">
    <VortFormItem label="名称" required>
        <VortInput v-model="form.name" placeholder="请输入" />
    </VortFormItem>
    <VortFormItem>
        <VortButton variant="primary" :loading="saving" @click="handleSave">提交</VortButton>
        <VortButton class="ml-3" @click="handleCancel">取消</VortButton>
    </VortFormItem>
</VortForm>
```

### VortDropdown

```vue
<VortDropdown trigger="click">
    <VortButton>操作 <ChevronDown :size="14" /></VortButton>
    <template #overlay>
        <VortDropdownMenuItem @click="handleEdit">编辑</VortDropdownMenuItem>
        <VortDropdownMenuSeparator />
        <VortDropdownMenuItem danger @click="handleDelete">删除</VortDropdownMenuItem>
    </template>
</VortDropdown>
```

## 业务组件 (vort-biz/) 关键用法

业务组件封装了常见的 CRUD 交互模式，**必须优先使用，不要手写重复逻辑**。

### TableActions + TableActionsItem（表格操作列）

替代手写 `<a>` 链接 + `<VortDivider type="vertical">`，自动处理分隔线、样式统一。

```vue
<VortTableColumn label="操作" :width="180" fixed="right">
    <template #default="{ row }">
        <TableActions>
            <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
            <TableActionsItem danger @click="handleDelete(row)">删除</TableActionsItem>

            <!-- 更多操作折叠到下拉菜单 -->
            <template #more>
                <TableActionsMoreItem @click="handleCopy(row)">复制</TableActionsMoreItem>
                <TableActionsMoreItem danger @click="handleRemove(row)">移除</TableActionsMoreItem>
            </template>
        </TableActions>
    </template>
</VortTableColumn>
```

Props：
- `type`: `"text"` (默认链接样式) | `"button"` (按钮样式)
- `divider`: 是否显示分隔线，默认 `true`
- `moreText`: 更多按钮文字，默认 `"更多"`

### DeleteRecord（删除操作）

封装了确认弹窗 + API 调用 + 成功/失败提示，替代手写 `dialog.confirm` + API 调用。

```vue
<!-- 基础用法：包裹在 TableActionsItem 中 -->
<TableActions>
    <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
    <DeleteRecord
        :request-api="api.deleteItem"
        :params="{ id: row.id }"
        @after-delete="loadData"
    >
        <TableActionsItem danger>删除</TableActionsItem>
    </DeleteRecord>
</TableActions>

<!-- 在 more 下拉菜单中使用（需要 block + onSuccess） -->
<template #more>
    <TableActionsMoreItem>
        <DeleteRecord
            block
            :request-api="api.deleteItem"
            :params="{ id: row.id }"
            :on-success="loadData"
        >删除</DeleteRecord>
    </TableActionsMoreItem>
</template>
```

Props：
- `requestApi`: 删除 API 函数 `(params) => Promise`
- `params`: 传给 API 的参数
- `title`: 确认框标题，默认 `"您确认要删除该数据吗？"`
- `successMessage`: 成功提示，默认 `"删除成功"`
- `block`: 块级模式（用于 dropdown 场景）
- `onSuccess`: 成功回调（用于 teleport 场景如 dropdown 内，替代 `@after-delete`）

### DialogForm（弹窗/抽屉表单）

封装了 触发器 → 打开弹窗/抽屉 → 渲染表单组件 → 提交/关闭 的完整流程。

```vue
<script setup lang="ts">
import EditForm from "./EditForm.vue";
</script>

<!-- 基础用法：点击触发器打开 Dialog -->
<DialogForm :component="EditForm" title="编辑" @ok="loadData">
    <VortButton variant="primary">新增</VortButton>
</DialogForm>

<!-- 传参给表单组件 -->
<DialogForm :component="EditForm" title="编辑" :params="{ id: row.id }" @ok="loadData">
    <TableActionsItem>编辑</TableActionsItem>
</DialogForm>

<!-- 抽屉模式 -->
<DialogForm :component="EditForm" title="编辑" is-drawer :width="600" @ok="loadData">
    <VortButton>打开抽屉</VortButton>
</DialogForm>
```

表单组件约定（EditForm.vue）：
```vue
<script setup lang="ts">
const props = defineProps<{
    params: Record<string, unknown>;
    okHandler: (payload?: unknown) => void;
    cancelHandler: () => void;
}>();

// 必须暴露 onFormSubmit 方法，DialogForm 的确认按钮会调用它
// 返回 Promise 时自动管理 loading 状态
const onFormSubmit = async () => {
    await api.save(form);
    props.okHandler(); // 关闭弹窗并触发 ok 事件
};

defineExpose({ onFormSubmit });
</script>
```

Props：
- `component`: 表单组件（必需）
- `params`: 传给表单组件的参数
- `isDrawer`: 是否抽屉模式，默认 `false`
- `title` / `width` / `closable` / `maskClosable`
- `showFooter` / `showCancel` / `showOk` / `okText` / `cancelText`
- `closeConfirm`: 关闭时是否确认（表单有未保存更改时提示）
- `centered` / `bodyNoPadding`（仅 Dialog）
- `placement`（仅 Drawer，默认 `"right"`）

### SearchToolbar 组合（搜索栏）

替代手写搜索表单布局，提供统一的搜索区域样式。

```vue
<SearchToolbar :on-search="handleSearch" :on-reset="handleReset" :loading="loading">
    <SearchForm :label-width="80">
        <SearchFormItem label="关键词">
            <VortInput v-model="params.keyword" placeholder="请输入" />
        </SearchFormItem>
        <SearchFormItem label="状态">
            <VortSelect v-model="params.status" placeholder="请选择" />
        </SearchFormItem>
        <SearchFormActions />
    </SearchForm>
    <template #actions>
        <VortButton variant="primary">
            <Plus :size="14" class="mr-1" /> 新增
        </VortButton>
    </template>
</SearchToolbar>
```

组件说明：
- `SearchToolbar`: 外层容器，提供 `onSearch`/`onReset` 给子组件
- `SearchForm`: 基于 VortForm inline 布局，统一 `labelWidth`
- `SearchFormItem`: 单个搜索项，`label` + 控件布局，`controlWidth` 默认 270px
- `SearchFormActions`: 搜索/重置按钮，自动从 SearchToolbar 注入回调

### BatchActions（批量操作）

```vue
<BatchActions
    :selected-count="selectedIds.length"
    @delete="handleBatchDelete"
/>
<!-- 自定义文案 -->
<BatchActions
    :selected-count="selectedIds.length"
    delete-text="批量移除"
    confirm-text="确认要批量移除所选项吗？"
    @delete="handleBatchRemove"
/>
```

### PopForm（气泡快速编辑）

用于表格内行内编辑场景，点击弹出气泡框编辑字段值。

```vue
<!-- 基础用法：调用 API 保存 -->
<PopForm
    v-model:org-value="row.name"
    label="名称"
    :params="{ id: row.id, field: 'name' }"
    :request-api="api.updateField"
    @ok="loadData"
/>

<!-- 直接模式：不调用 API，只更新值 -->
<PopForm
    v-model:org-value="form.price"
    label="价格"
    type="decimal"
    is-price
    is-direct
    @ok="handlePriceChange"
/>
```

Props：
- `orgValue`: 原始值（v-model）
- `type`: `"input"` | `"textarea"` | `"integer"` | `"decimal"`
- `label` / `extra` / `required` / `min` / `max` / `len` / `minNum` / `maxNum`
- `requestApi` / `params`: API 提交
- `isDirect`: 直接模式，不调用 API
- `isHover`: hover 时显示编辑图标（默认 true），false 时常显

### VortIcon（业务图标）

```vue
<VortIcon name="icon-name" :size="16" />
```

## 全部可用组件速查

### 基础 UI 组件 (vort/) — 全部自动导入

| 分类 | 组件 |
|------|------|
| 通用 | VortButton, VortConfigProvider |
| 布局 | VortRow, VortCol, VortDivider |
| 导航 | VortMenu, VortMenuItem, VortSubMenu, VortMenuItemGroup, VortMenuDivider, VortTabs, VortTabPane, VortSteps, VortAnchor, VortAnchorLink |
| 数据录入 | VortInput, VortInputNumber, VortInputPassword, VortInputSearch, VortTextarea, VortSelect, VortSelectOption, VortCascader, VortAutoComplete, VortCheckbox, VortCheckboxGroup, VortRadio, VortRadioGroup, VortRadioButton, VortSwitch, VortSlider, VortColorPicker, VortDatePicker, VortRangePicker, VortTimePicker, VortUpload, VortUploadDragger |
| 数据展示 | VortTable, VortTableColumn, VortTag, VortCheckableTag, VortDraggableTags, VortBadge, VortBadgeRibbon, VortStatusDot, VortCard, VortImage, VortImagePreviewGroup, VortStatistic, VortStatisticCountdown, VortTimeline, VortTimelineItem, VortSegmented |
| 反馈 | VortDialog, VortDrawer, VortSpin, VortAlert, VortSkeleton, VortSkeletonAvatar, VortSkeletonButton, VortSkeletonInput, VortSkeletonImage, VortSkeletonNode |
| 浮层 | VortTooltip, VortPopover, VortPopconfirm, VortDropdown, VortDropdownButton, VortDropdownMenuItem, VortDropdownMenuSeparator, VortDropdownMenuLabel, VortDropdownMenuGroup, VortDropdownMenuSub, VortDropdownMenuCheckboxItem, VortDropdownMenuRadioGroup, VortDropdownMenuRadioItem |
| 其他 | VortPagination, VortScrollbar |

### 业务组件 (vort-biz/) — 全部自动导入

| 组件 | 说明 |
|------|------|
| SearchToolbar | 搜索栏容器 |
| SearchForm | 搜索表单（inline 布局） |
| SearchFormItem | 搜索表单项 |
| SearchFormActions | 搜索/重置按钮 |
| DialogForm | 弹窗/抽屉表单 |
| PopForm | 气泡快速编辑 |
| TableActions | 表格操作栏容器 |
| TableActionsItem | 表格操作项 |
| TableActionsMoreItem | 表格更多操作项（dropdown 内） |
| DeleteRecord | 删除确认 + API 调用 |
| BatchActions | 批量操作按钮 |
| VortIcon | 业务图标 |

## 页面布局规范

### 列表页标准结构

```vue
<template>
    <div class="space-y-4">
        <!-- 搜索栏（有搜索条件时使用） -->
        <div class="bg-white rounded-xl p-6">
            <SearchToolbar :on-search="handleSearch" :on-reset="handleReset">
                <SearchForm>
                    <SearchFormItem label="关键词">
                        <VortInput v-model="params.keyword" placeholder="请输入" />
                    </SearchFormItem>
                    <SearchFormActions />
                </SearchForm>
                <template #actions>
                    <div class="flex items-center gap-2">
                        <DialogForm :component="EditForm" title="新增" @ok="loadData">
                            <VortButton variant="primary">
                                <Plus :size="14" class="mr-1" /> 新增
                            </VortButton>
                        </DialogForm>
                        <BatchActions :selected-count="selectedIds.length" @delete="handleBatchDelete" />
                    </div>
                </template>
            </SearchToolbar>

            <!-- 表格 -->
            <VortTable :data-source="list" :loading="loading" row-key="id"
                :pagination="false" :row-selection="rowSelection">
                <VortTableColumn label="名称" prop="name" />
                <VortTableColumn label="状态" prop="status">
                    <template #default="{ row }">
                        <VortTag :color="row.status === 1 ? 'green' : 'red'">
                            {{ row.status === 1 ? '启用' : '禁用' }}
                        </VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="180" fixed="right">
                    <template #default="{ row }">
                        <TableActions>
                            <DialogForm :component="EditForm" title="编辑" :params="{ id: row.id }" @ok="loadData">
                                <TableActionsItem>编辑</TableActionsItem>
                            </DialogForm>
                            <DeleteRecord :request-api="api.del" :params="{ id: row.id }" @after-delete="loadData">
                                <TableActionsItem danger>删除</TableActionsItem>
                            </DeleteRecord>
                        </TableActions>
                    </template>
                </VortTableColumn>
            </VortTable>

            <!-- 分页 -->
            <div class="flex justify-end mt-4">
                <VortPagination v-model:current="page" :total="total" @change="loadData" />
            </div>
        </div>
    </div>
</template>
```

### 表单页标准结构

```vue
<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6 max-w-2xl">
            <h3 class="text-base font-medium text-gray-800 mb-6">表单标题</h3>
            <VortForm label-width="100px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="form.name" placeholder="请输入" />
                </VortFormItem>
                <VortFormItem>
                    <VortButton variant="primary" :loading="saving" @click="handleSave">提交</VortButton>
                    <VortButton class="ml-3" @click="handleCancel">取消</VortButton>
                </VortFormItem>
            </VortForm>
        </div>
    </div>
</template>
```

## 注意事项

- 布局用 `<div class="bg-white rounded-xl p-6">` 白卡片，不用 `<VortCard>` 包裹列表
- `<VortCard>` 适合仪表盘统计卡片、插件卡片等小块内容
- 表格分页设 `:pagination="false"`，用外部 `VortPagination` 组件
- 状态标签用 `<VortTag :color="...">`
- 图标用 lucide-vue-next，常用：Plus, Trash2, RefreshCw, Save, Edit, Search, Shield, Check, X 等
- API 函数定义在 `web/src/api/index.ts`，请求通过 `@/utils/request` 的 axios 实例
- Pinia store 在 `web/src/stores/`，用户信息在 `useUserStore()`

## 组件 Props 易错点

使用 Vort 组件时，必须查阅对应 `types.ts` 确认 prop 名称，以下是常见易错项：

| 组件 | 正确 prop | 常见错误 |
|------|-----------|----------|
| VortSwitch | `v-model:checked` / `:checked` + `@change` | ~~`v-model`~~、~~`:model-value`~~、~~`@update:model-value`~~ |
| VortTooltip | `title` | ~~`content`~~ |
| VortTableColumn | `label`、`prop` | ~~`title`~~、~~`dataIndex`~~ |
| VortTabs / VortTabPane | `v-model:activeKey`、`tab-key` | ~~`key`~~（Vue 内置属性） |
