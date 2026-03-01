# OpenVort 前端开发规范 (VortAdmin 风格)

## 概述

OpenVort 前端基于 vortadmin 框架，使用自研 `vort` 组件库。所有页面开发必须遵循以下规范。

## 技术栈

- Vue 3 + TypeScript (`<script setup lang="ts">`)
- Tailwind CSS + CSS Variables (`--vort-*`)
- 自研 `vort` 组件库（Ant Design Vue 风格 API，`vort-*` 前缀自动注册）
- Pinia 状态管理
- lucide-vue-next 图标
- @vueuse/core 工具函数

## 组件自动注册

`vort-*` 前缀组件在模板中自动解析，无需 import。业务组件（`vort-biz/*`）需手动 import。

已注册的全局组件见 `components.d.ts`，包括：
- 基础：VortButton, VortInput, VortSelect, VortSelectOption, VortTag, VortSpin, VortTooltip, VortDivider, VortAlert, VortCard
- 表格：VortTable, VortTableColumn, VortPagination
- 表单：VortForm, VortFormItem, VortInput, VortInputNumber, VortInputPassword, VortInputSearch, VortSelect, VortTextarea, VortSwitch, VortCheckbox, VortRadioGroup, VortRadioButton, VortDatePicker, VortRangePicker
- 弹层：VortDialog, VortDrawer, VortDropdown, VortDropdownMenuItem, VortDropdownMenuSeparator, VortPopconfirm
- 布局：VortTabs, VortTabPane, VortScrollbar
- 搜索（自动注册）：SearchToolbar, SearchForm, SearchFormItem, SearchFormActions
- 操作（自动注册）：TableActions, TableActionsItem, DeleteRecord
- AI 辅助（自动注册）：AiAssistButton

## 核心 Hooks

### useCrudPage — CRUD 列表页

```typescript
import { useCrudPage } from "@/hooks";

interface XxxItem { id: string; name: string; /* ... */ }
type FilterParams = { page: number; size: number; keyword?: string; state?: string };

const fetchList = async (params: FilterParams) => {
    const res = await getXxxList({ ...params, page_size: params.size });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination,
        rowSelection, hasSelection, selectedIds, clearSelection,
        loadData, onSearchSubmit, resetParams, deleteRow } =
    useCrudPage<XxxItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20 }
    });

loadData();
```

返回值说明：
- `listData` — 列表数据 `Ref<T[]>`
- `loading` — 加载状态
- `total` — 总条数
- `filterParams` — 筛选参数（reactive，含 page/size）
- `showPagination` — 是否显示分页（total > 0）
- `rowSelection` — 表格多选配置（直接传给 `:row-selection`）
- `hasSelection` — 是否有选中项
- `selectedIds` — 选中的 ID 数组
- `clearSelection` — 清空选中
- `loadData` — 加载数据
- `onSearchSubmit` — 搜索（重置 page=1 后加载）
- `resetParams` — 重置所有筛选参数并加载
- `deleteRow` — 删除单行（需配置 `deleteApi`）

**注意**：API 返回格式必须适配为 `{ records: T[], total: number }`。

### useDialogForm — 弹窗/抽屉表单

```typescript
import { useDialogForm, type DialogFormProps, type CommonFormParams } from "@/hooks";

const props = defineProps<DialogFormProps<CommonFormParams>>();
const formRef = ref(null);

const { loading, formState, isEdit, isAdd, onSubmit } =
    useDialogForm<FormType>({
        defaultFormState: { name: "", desc: "" },
        detailApi: (params) => request.get(`/xxx/${params.id}`),
        submitApi: (op, data) => op === "create" ? request.post("/xxx", data) : request.put(`/xxx/${data.id}`, data),
        props, formRef
    });

defineExpose({ onFormSubmit: onSubmit });
```

返回值说明：
- `loading` — 加载/提交状态
- `formState` — 表单数据 `Ref<T>`
- `isEdit` / `isAdd` — 当前模式
- `isReadonly` — 只读模式（`params.examine === 1`）
- `onSubmit` — 提交（自动校验 + 调用 submitApi + 成功回调）
- `resetFormState` — 重置表单

## 页面布局模式

### 1. 列表页（CRUD Table）— 双卡片布局

搜索区和表格分成两个独立的白色卡片，这是标准布局：

```vue
<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import { getXxxList } from "@/api";
import { Plus } from "lucide-vue-next";

interface XxxItem { id: string; name: string; state: string; createdAt: string; }
type FilterParams = { page: number; size: number; state: string; keyword: string };

const stateOptions = [
    { label: "全部", value: "" },
    { label: "启用", value: "active" },
    { label: "禁用", value: "disabled" },
];
const stateColorMap: Record<string, string> = { active: "green", disabled: "red" };
const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

const fetchList = async (params: FilterParams) => {
    const res = await getXxxList({ ...params, page_size: params.size });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<XxxItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, state: "", keyword: "" },
    });

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<XxxItem>>({});

const handleAdd = () => { drawerMode.value = "add"; drawerTitle.value = "新增"; currentRow.value = {}; drawerVisible.value = true; };
const handleEdit = (row: XxxItem) => { drawerMode.value = "edit"; drawerTitle.value = "编辑"; currentRow.value = { ...row }; drawerVisible.value = true; };
const handleView = (row: XxxItem) => { drawerMode.value = "view"; drawerTitle.value = "详情"; currentRow.value = { ...row }; drawerVisible.value = true; };
const handleSave = () => { drawerVisible.value = false; loadData(); };

loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">页面标题</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="搜索..."
                        allow-clear
                        class="flex-1 sm:w-[220px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- 表格卡片 -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false" :row-selection="rowSelection">
                <vort-table-column label="名称" prop="name" />
                <vort-table-column label="状态" :width="80">
                    <template #default="{ row }">
                        <vort-tag :color="stateColorMap[row.state] || 'default'">{{ stateLabel(row.state) }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="创建时间" prop="createdAt" :width="170" />
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="filterParams.page"
                    v-model:page-size="filterParams.size"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="loadData"
                />
            </div>
        </div>

        <!-- 抽屉 -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="550">
            <!-- 查看模式 -->
            <div v-if="drawerMode === 'view'" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <span class="text-sm text-gray-400">名称</span>
                    <div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div>
                </div>
                <div>
                    <span class="text-sm text-gray-400">状态</span>
                    <div class="mt-1">
                        <vort-tag :color="stateColorMap[currentRow.state!] || 'default'">{{ stateLabel(currentRow.state || '') }}</vort-tag>
                    </div>
                </div>
            </div>
            <!-- 编辑/新增模式 -->
            <template v-else>
                <vort-form label-width="80px">
                    <vort-form-item label="名称" required>
                        <vort-input v-model="currentRow.name" placeholder="请输入名称" />
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>
```

### 2. 操作列

两种写法均可：

方式一：手写链接 + divider（vortadmin 原生风格）：

```vue
<vort-table-column label="操作" :width="160" fixed="right">
    <template #default="{ row }">
        <div class="flex items-center gap-2 whitespace-nowrap">
            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
            <vort-divider type="vertical" />
            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
            <vort-divider type="vertical" />
            <vort-popconfirm title="确认删除？" @confirm="handleDelete(row)">
                <a class="text-sm text-red-500 cursor-pointer">删除</a>
            </vort-popconfirm>
        </div>
    </template>
</vort-table-column>
```

方式二：TableActions 组件（自动分隔线，支持更多下拉）：

```vue
<vort-table-column label="操作" :width="160" fixed="right">
    <template #default="{ row }">
        <TableActions>
            <TableActionsItem @click="handleView(row)">详情</TableActionsItem>
            <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
            <TableActionsItem danger @click="handleDelete(row)">删除</TableActionsItem>
        </TableActions>
    </template>
</vort-table-column>
```

带更多下拉菜单：

```vue
<TableActions>
    <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
    <template #more>
        <vort-dropdown-menu-item @click="handleCopy(row)">复制</vort-dropdown-menu-item>
        <vort-dropdown-menu-item danger @click="handleDelete(row)">删除</vort-dropdown-menu-item>
    </template>
</TableActions>
```

### 3. 搜索区布局

搜索区在卡片顶部，标题行 + 筛选行：

```vue
<!-- 标题行：左标题，右新增按钮 -->
<div class="flex items-center justify-between mb-4">
    <h3 class="text-base font-medium text-gray-800">页面标题</h3>
    <vort-button variant="primary" @click="handleAdd">
        <Plus :size="14" class="mr-1" /> 新增
    </vort-button>
</div>

<!-- 筛选行：标签 + 控件 横向排列，响应式换行 -->
<div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
    <div class="flex items-center gap-2 w-full sm:w-auto">
        <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
        <vort-input-search v-model="filterParams.keyword" placeholder="搜索..." allow-clear class="flex-1 sm:w-[220px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
    </div>
    <div class="flex items-center gap-2 w-full sm:w-auto">
        <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
        <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
            <vort-select-option value="active">启用</vort-select-option>
        </vort-select>
    </div>
    <div class="flex items-center gap-2">
        <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
        <vort-button @click="resetParams">重置</vort-button>
    </div>
</div>
```

也可使用 SearchToolbar 组件（更紧凑，自带查询/重置按钮）：

```vue
<SearchToolbar :on-search="onSearchSubmit" :on-reset="resetParams" :loading="loading">
    <SearchForm>
        <SearchFormItem label="状态">
            <VortSelect v-model="filterParams.state" placeholder="全部" allow-clear style="width: 180px">
                <VortSelectOption v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
            </VortSelect>
        </SearchFormItem>
        <SearchFormActions />
    </SearchForm>
</SearchToolbar>
```

### 4. 详情展示（Drawer 内 / 独立页面）

字段用 grid 布局，标签灰色小字，值黑色：

```vue
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div>
        <span class="text-sm text-gray-400">字段名</span>
        <div class="text-sm text-gray-800 mt-1">{{ value }}</div>
    </div>
    <!-- 跨列字段 -->
    <div class="sm:col-span-2">
        <span class="text-sm text-gray-400">描述</span>
        <div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ description }}</div>
    </div>
    <!-- Tag 类字段 -->
    <div>
        <span class="text-sm text-gray-400">状态</span>
        <div class="mt-1"><vort-tag :color="colorMap[state]">{{ label }}</vort-tag></div>
    </div>
</div>
```

### 5. 表单页

```vue
<div class="max-w-[800px] mx-auto">
    <div class="bg-white rounded-xl p-8">
        <h3 class="text-lg font-medium text-gray-800 mb-6">标题</h3>
        <vort-form label-width="100px" :model="formState" ref="formRef">
            <vort-form-item label="名称" required>
                <vort-input v-model="formState.name" placeholder="请输入名称" />
            </vort-form-item>
            <vort-form-item label="描述">
                <vort-textarea v-model="formState.desc" placeholder="请输入描述" :rows="4" />
            </vort-form-item>
            <vort-form-item>
                <vort-button variant="primary" :loading="loading" @click="onSubmit">提交</vort-button>
                <vort-button class="ml-3" @click="cancel">取消</vort-button>
            </vort-form-item>
        </vort-form>
    </div>
</div>
```

多区块高级表单用 grid 布局：

```vue
<div class="bg-white rounded-xl p-6 mb-6">
    <h3 class="text-base font-medium text-gray-800 mb-4">区块标题</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6">
        <vort-form-item label="字段1"><vort-input v-model="formState.field1" /></vort-form-item>
        <vort-form-item label="字段2"><vort-input v-model="formState.field2" /></vort-form-item>
    </div>
</div>
```

### 6. 抽屉（查看/编辑/新增三合一）

```vue
<vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="550">
    <!-- 查看模式 -->
    <div v-if="drawerMode === 'view'" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div><span class="text-sm text-gray-400">名称</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div></div>
        <div><span class="text-sm text-gray-400">状态</span><div class="mt-1"><vort-tag :color="colorMap[currentRow.state]">{{ label }}</vort-tag></div></div>
    </div>
    <!-- 编辑/新增模式 -->
    <template v-else>
        <vort-form label-width="80px">
            <vort-form-item label="名称" required><vort-input v-model="currentRow.name" placeholder="请输入名称" /></vort-form-item>
        </vort-form>
        <div class="flex justify-end gap-3 mt-6">
            <vort-button @click="drawerVisible = false">取消</vort-button>
            <vort-button variant="primary" @click="handleSave">确定</vort-button>
        </div>
    </template>
</vort-drawer>
```

Drawer 状态管理模板：

```typescript
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<XxxItem>>({});

const handleAdd = () => { drawerMode.value = "add"; drawerTitle.value = "新增XXX"; currentRow.value = {}; drawerVisible.value = true; };
const handleEdit = (row: XxxItem) => { drawerMode.value = "edit"; drawerTitle.value = "编辑XXX"; currentRow.value = { ...row }; drawerVisible.value = true; };
const handleView = (row: XxxItem) => { drawerMode.value = "view"; drawerTitle.value = "XXX详情"; currentRow.value = { ...row }; drawerVisible.value = true; };
const handleSave = () => { drawerVisible.value = false; loadData(); };
```

### 7. 卡片列表

```vue
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    <!-- 新增卡片（可选） -->
    <div class="bg-white rounded-xl border-2 border-dashed border-gray-200 flex items-center justify-center cursor-pointer hover:border-blue-400 transition-colors min-h-[160px]" @click="handleAdd">
        <div class="text-center text-gray-400"><Plus :size="24" class="mx-auto mb-1" /><span class="text-sm">新增</span></div>
    </div>
    <!-- 数据卡片 -->
    <div v-for="item in list" :key="item.id" class="bg-white rounded-xl overflow-hidden hover:shadow-lg transition-shadow p-4">
        <h4 class="font-medium text-gray-800 mb-1">{{ item.name }}</h4>
        <p class="text-xs text-gray-400 line-clamp-2 mb-3">{{ item.description || '暂无描述' }}</p>
        <div class="flex items-center gap-2">
            <vort-tag size="small" color="blue">{{ item.tag }}</vort-tag>
        </div>
    </div>
</div>
```

### 8. 删除确认

使用 `vort-popconfirm` 包裹删除链接：

```vue
<vort-popconfirm title="确认删除？" @confirm="handleDelete(row)">
    <a class="text-sm text-red-500 cursor-pointer">删除</a>
</vort-popconfirm>
```

或使用 `DeleteRecord` 组件（自带确认弹窗 + API 调用 + 成功提示）：

```vue
<DeleteRecord :request-api="deleteXxx" :params="{ id: row.id }" @after-delete="loadData">
    <a class="text-sm text-red-500 cursor-pointer">删除</a>
</DeleteRecord>
```

### 9. 多选与批量操作

```vue
<!-- 表格启用多选 -->
<vort-table :data-source="listData" :row-selection="rowSelection">

<!-- 批量操作栏（表格上方） -->
<div v-if="hasSelection" class="flex items-center gap-3 mb-4">
    <span class="text-sm text-gray-500">已选 {{ selectedIds.length }} 项</span>
    <vort-button size="small" @click="handleBatchDelete">批量删除</vort-button>
    <vort-button size="small" @click="clearSelection">取消选择</vort-button>
</div>
```

## 组件 API 速查

| 组件 | 关键 Props |
|------|-----------|
| `vort-button` | `variant="primary\|dashed\|text"`, `:loading`, `size="small\|large"` |
| `vort-table` | `:data-source`, `:loading`, `:pagination="false"`, `:row-selection`, `row-key`, `size="large\|middle\|small"` |
| `vort-table-column` | `label`, `prop`, `:width`, `fixed="right"`, `#default="{ row, index }"` |
| `vort-pagination` | `v-model:current`, `v-model:page-size`, `:total`, `show-total-info`, `show-size-changer`, `show-quick-jumper`, `@change` |
| `vort-form` | `label-width`, `:model`, `ref` |
| `vort-form-item` | `label`, `required` |
| `vort-input` | `v-model`, `placeholder` |
| `vort-input-search` | `v-model`, `allow-clear`, `@search`, `@keyup.enter` |
| `vort-select` | `v-model`, `placeholder`, `allow-clear`, `@change` |
| `vort-select-option` | `value` |
| `vort-drawer` | `v-model:open`, `:title`, `:width` |
| `vort-dialog` | `:open`, `:title`, `:width`, `:centered`, `@update:open`, `@ok` |
| `vort-tag` | `:color="green\|red\|blue\|orange\|cyan\|purple\|default\|processing\|geekblue\|volcano"`, `size="small"` |
| `vort-popconfirm` | `:title`, `@confirm` |
| `vort-divider` | `type="vertical"` |
| `vort-spin` | `:spinning` |
| `vort-tabs` / `vort-tab-pane` | `v-model`, `key`, `tab` |
| `vort-textarea` | `v-model`, `:rows` |
| `vort-switch` | `v-model:checked`（注意：不是 v-model）, `:disabled`, `:loading`, `size="small"`, `:before-change` |
| `vort-checkbox` | `v-model:checked`, `@update:checked` |
| `vort-date-picker` | `v-model`, `value-format`, `format`, `placeholder`, `allow-clear`, `disabled`, `:disabled-date`, `:show-time`, `picker="date\|month\|year"`, `:presets`, `@change` |
| `vort-range-picker` | `v-model`, `value-format`, `format`, `:placeholder="['开始', '结束']"`, `allow-clear`, `disabled`, `:disabled-date`, `:show-time`, `separator`, `:presets`, `@change` |
| `vort-tooltip` | `title` |

## CSS 约定

| 场景 | 类名 |
|------|------|
| 页面容器 | `div.space-y-4` |
| 卡片 | `div.bg-white.rounded-xl.p-6` |
| 区块标题 | `h3.text-base.font-medium.text-gray-800.mb-4` |
| 标题行（标题+按钮） | `div.flex.items-center.justify-between.mb-4` |
| 筛选行 | `div.flex.flex-col.sm:flex-row.items-start.sm:items-center.gap-3.sm:gap-4` |
| 筛选项 | `div.flex.items-center.gap-2.w-full.sm:w-auto` |
| 筛选标签 | `span.text-sm.text-gray-500.whitespace-nowrap` |
| 字段标签（详情） | `span.text-sm.text-gray-400` |
| 字段值（详情） | `div.text-sm.text-gray-800.mt-1` |
| 日期/次要文本 | `span.text-sm.text-gray-500` 或 `span.text-sm.text-gray-400` |
| 操作链接 | `a.text-sm.text-blue-600.cursor-pointer` |
| 危险操作链接 | `a.text-sm.text-red-500.cursor-pointer` |
| 分页容器 | `div.flex.justify-end.mt-4`（`v-if="showPagination"` 包裹） |
| 抽屉底部按钮 | `div.flex.justify-end.gap-3.mt-6` |

## 常见易错点

### vort-date-picker 日期选择（不要用 vort-input type="date"）

日期选择**必须**使用 `vort-date-picker`，**禁止**使用 `<vort-input type="date">`：

```vue
<!-- 正确 — 使用 vort-date-picker -->
<vort-date-picker v-model="formState.deadline" value-format="YYYY-MM-DD" placeholder="请选择日期" />

<!-- 错误 — 不要用 input type="date" -->
<vort-input v-model="formState.deadline" type="date" />
```

绑定字符串日期时用 `value-format="YYYY-MM-DD"`，需要时间则用 `value-format="YYYY-MM-DD HH:mm:ss"` 并开启 `:show-time`。

日期范围使用 `vort-range-picker`：

```vue
<vort-range-picker v-model="dateRange" value-format="YYYY-MM-DD" :placeholder="['开始日期', '结束日期']" />
```

### message 消息提示

导入路径是 `@/components/vort/message`，**不是** `@/utils/message`：

```typescript
import { message } from "@/components/vort/message";

message.success("操作成功");
message.error("操作失败");
message.warning("请填写必填项");
message.info("提示信息");
```

### vort-switch 用法

`vort-switch` 使用 `v-model:checked`，**不是** `v-model`：

```vue
<!-- 正确 -->
<vort-switch v-model:checked="formState.enabled" />

<!-- 错误 — 点击不会切换！ -->
<vort-switch v-model="formState.enabled" />
```

### vort-checkbox 用法

`vort-checkbox` 使用 `checked` + `@update:checked`：

```vue
<vort-checkbox :checked="checked" @update:checked="checked = $event" />
```

也可直接使用 `v-model:checked`（更不易写错）：

```vue
<vort-checkbox v-model:checked="checked" />
```

### Checkbox 点不动（高频问题排查）

出现“点击没反应”时，按下面顺序排查：

1. **先查绑定写法**
   - 必须使用 `v-model:checked` 或 `:checked + @update:checked`
   - 不要写成 `v-model`（会导致状态不同步或点击无效）

2. **再查是否被禁用**
   - 检查 `:disabled` 是否被误传
   - 检查父级是否有全局“loading 态禁用交互”的逻辑

3. **再查点击事件是否被父容器吞掉**
   - 列表行/卡片常有 `@click` 打开详情，可能与 checkbox 冲突
   - 冲突时给 checkbox 增加 `@click.stop`，阻止冒泡

```vue
<div class="row" @click="openDetail(item)">
    <vort-checkbox
        v-model:checked="item.checked"
        @click.stop
    />
</div>
```

4. **再查是否有遮挡层**
   - 用浏览器检查元素确认 checkbox 上方没有透明层
   - 重点排查：`position: absolute/fixed`、`z-index`、`pointer-events`
   - 若是装饰层，设置 `pointer-events: none`

5. **Set/Map 选中态建议“新引用赋值”**
   - 某些复杂渲染下，直接 `set.add/delete` 容易出现“数据变了但 UI 不刷新”
   - 推荐每次创建新 `Set` 后再赋值，确保视图更新稳定

```typescript
const selected = ref<Set<string>>(new Set());

const toggle = (id: string) => {
    const next = new Set(selected.value);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected.value = next;
};
```

6. **最后查列表 key**
   - `v-for` 的 `:key` 必须稳定且唯一（如 `repo.id` / `repo.full_name`）
   - 不要用 index 作为 key，避免复用错误导致“点 A 变 B”或“点击无效”

## API 调用规范

1. API 函数统一定义在 `api/index.ts`，不要在组件内直接调用 `request`
2. 列表 API 返回适配为 `{ records: T[], total: number }` 格式
3. 使用 `@/utils/request` 实例（自带 token 注入和错误处理）
4. API 函数命名：`get{Resource}` / `create{Resource}` / `update{Resource}` / `delete{Resource}`

## 命名约定

| 类型 | 规范 | 示例 |
|------|------|------|
| 视图文件 | `views/{module}/{Name}.vue` | `views/vortflow/Stories.vue` |
| 接口类型 | `{Name}Item` | `StoryItem`, `TaskItem` |
| 筛选参数类型 | `FilterParams` | `{ page: number; size: number; state: string }` |
| 事件处理 | `handle{Action}` | `handleEdit`, `handleDelete`, `handleView` |
| API 函数 | `get/create/update/delete{Resource}` | `getVortflowStories` |
| 状态映射 | `{field}ColorMap` | `stateColorMap` |
| 选项数组 | `{field}Options` | `stateOptions` |
| 标签函数 | `{field}Label` | `stateLabel(val)` |
| Drawer 状态 | `drawerVisible`, `drawerTitle`, `drawerMode`, `currentRow` | — |
