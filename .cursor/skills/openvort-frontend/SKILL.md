# OpenVort 前端开发规范

## !!! 强制规则（违反即为 BUG，必须最先阅读）

### 规则 1：必须使用 vort 组件库，禁止写原生 HTML 控件

所有 UI 元素必须使用 vort 组件库，**禁止**用原生 HTML 或自己拼 Tailwind 实现以下任何一个：

| 需求 | 必须用 | 禁止用 |
|------|--------|--------|
| 按钮 | `<vort-button variant="primary">` | `<button class="bg-blue-600 ...">` |
| 输入框 | `<vort-input>` | `<input class="border ...">` |
| 密码框 | `<vort-input-password>` | `<input type="password">` |
| 搜索框 | `<vort-input-search>` | 自制搜索框 |
| 下拉选择 | `<vort-select>` + `<vort-select-option>` | `<select>` |
| 开关 | `<vort-switch v-model:checked="xxx">` | `<input type="checkbox">` 或 toggle div |
| 复选框 | `<vort-checkbox v-model:checked="xxx">` | `<input type="checkbox">` |
| 表格 | `<vort-table>` + `<vort-table-column>` | `<table>` |
| 弹窗 | `<vort-dialog>` 或 `Dialog`（import） | 自写 modal div |
| 抽屉 | `<vort-drawer>` 或 `Drawer`（import） | 自写侧边面板 |
| 表单 | `<vort-form>` + `<vort-form-item>` | `<form>` + `<label>` + `<div>` |
| 标签 | `<vort-tag color="green">` | `<span class="bg-green-100 ...">` |
| 分页 | `<vort-pagination>` | 自写分页按钮 |
| 加载 | `<vort-spin :spinning="loading">` | 自写 spinner div |
| 提示气泡 | `<vort-tooltip>` | `title` 属性 |
| 日期选择 | `<vort-date-picker>` | `<input type="date">` |
| 消息提示 | `message.success/error/warning` | `alert()` 或 `window.confirm()` |
| 确认删除 | `<vort-popconfirm>` | `confirm()` |

### 规则 2：vort 组件在模板中用 kebab-case，不要手动 import

`vort-*` 前缀组件已全局注册（unplugin-vue-components），模板中直接写 kebab-case 即可：

```vue
<!-- 正确 -->
<template>
    <vort-button variant="primary" @click="save">保存</vort-button>
    <vort-input v-model="form.name" placeholder="请输入" />
    <vort-switch v-model:checked="form.enabled" />
</template>

<!-- 错误 -- 手动 import 后用 PascalCase -->
<script setup>
import { Button, Input, Switch } from "@/components/vort";  // 禁止！
</script>
<template>
    <Button variant="primary">保存</Button>
    <Input v-model="form.name" />
    <Switch v-model="form.enabled" />
</template>
```

**唯一例外：** `Dialog`/`Drawer` 作为独立弹窗组件的根容器时，可从 `@/components/vort` 手动 import。

### 规则 3：确认/提交按钮必须 `variant="primary"`

主操作按钮（保存、提交、确认、添加、构建）必须用 `variant="primary"`（蓝色高亮），取消按钮用默认样式。

```vue
<!-- 正确 -->
<vort-button @click="cancel">取消</vort-button>
<vort-button variant="primary" @click="save">保存</vort-button>

<!-- 错误 -- 保存按钮没有高亮，用户分不清主次 -->
<vort-button @click="cancel">取消</vort-button>
<vort-button @click="save">保存</vort-button>
```

### 规则 4：弹窗表单必须用 VortForm + zod 校验

弹窗内有表单时，**必须**用 `vort-form` + zod rules + `formRef.validate()`。**禁止**手动 `if (!xxx) { message.warning(...); return; }` 校验。

```vue
<script setup lang="ts">
import { ref } from "vue";
import { Dialog } from "@/components/vort";
import { z } from "zod";

const formRef = ref();
const saving = ref(false);
const form = ref({ name: "", url: "" });
const rules = z.object({
    name: z.string().min(1, "请输入名称"),
    url: z.string().min(1, "请输入 URL"),
});

async function handleSave() {
    try { await formRef.value?.validate(); } catch { return; }
    saving.value = true;
    // ... API 调用
}
</script>
<template>
    <Dialog :open="open" title="添加" :confirm-loading="saving" ok-text="保存" @ok="handleSave" @update:open="$emit('update:open', $event)">
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="请输入名称" />
            </vort-form-item>
            <vort-form-item label="URL" name="url" required>
                <vort-input v-model="form.url" placeholder="请输入 URL" />
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>
```

**要点：**
- `vort-form-item` 必须设 `name`（对应 rules key），否则校验不生效
- `required` 显示红色星号
- Dialog 用 `@ok` + `:confirm-loading`，不要自己在 body 里放按钮

### 规则 5：Dialog 按钮永远在 footer，不在 body

三种方式按优先级：
1. **首选：** 内置 props（`@ok` + `:confirm-loading` + `ok-text`）
2. **自定义：** `#footer` 插槽
3. **纯展示弹窗：** `:footer="false"`

```vue
<!-- 禁止！在 body 内部放按钮 -->
<VortDialog :open="open" :footer="false">
    <form>
        <vort-input v-model="name" />
        <vort-button @click="save">保存</vort-button>  <!-- 禁止！ -->
    </form>
</VortDialog>
```

### 规则 6：vort-switch 用 v-model:checked，不是 v-model

```vue
<!-- 正确 -->
<vort-switch v-model:checked="form.enabled" />

<!-- 错误 -- 点击不切换！ -->
<vort-switch v-model="form.enabled" />
```

同理 `vort-checkbox` 用 `v-model:checked`，`vort-tabs` 用 `v-model:activeKey`。

### 规则 7：侧边栏新增菜单图标必须注册 iconMap

`menus.ts` 设置 `icon` 后，必须在 `Sidebar.vue` 中 import + iconMap 注册：

```typescript
import { ..., HardDrive } from "lucide-vue-next";
const iconMap = { ..., "hard-drive": HardDrive };
```

### 规则 8：label-width 必须适配最长 label

| label 字数 | 推荐 label-width |
|-----------|-----------------|
| 2-3 字 | `80px` |
| 4 字 | `100px` |
| 5-6 字 | `120px` |
| 7+ 字 | `140px` |

---

## 技术栈

- Vue 3 + TypeScript (`<script setup lang="ts">`)
- Tailwind CSS + CSS Variables (`--vort-*`)
- 自研 `vort` 组件库（Ant Design Vue 风格 API，`vort-*` 前缀自动注册）
- Pinia 状态管理
- lucide-vue-next 图标（禁止使用 emoji 代替图标）
- @vueuse/core 工具函数

## 全局注册组件清单

无需 import，模板中直接用 `vort-*` kebab-case：

- 基础：VortButton, VortInput, VortSelect, VortSelectOption, VortTag, VortSpin, VortTooltip, VortDivider, VortAlert, VortCard
- 表格：VortTable, VortTableColumn, VortPagination
- 表单：VortForm, VortFormItem, VortInput, VortInputNumber, VortInputPassword, VortInputSearch, VortSelect, VortTextarea, VortSwitch, VortCheckbox, VortRadioGroup, VortRadioButton, VortDatePicker, VortRangePicker
- 弹层：VortDialog, VortDrawer, VortDropdown, VortDropdownMenuItem, VortDropdownMenuSeparator, VortPopconfirm
- 布局：VortTabs, VortTabPane, VortScrollbar
- 业务（自动注册）：SearchToolbar, SearchForm, SearchFormItem, SearchFormActions, TableActions, TableActionsItem, DeleteRecord, AiAssistButton

## 组件 API 速查

| 组件 | 关键 Props |
|------|-----------|
| `vort-button` | `variant="primary\|dashed\|text\|link"`, `:loading`, `size="small\|large"`, `danger` |
| `vort-table` | `:data-source`, `:loading`, `:pagination="false"`, `:row-selection`, `row-key` |
| `vort-table-column` | `label`, `prop`, `:width`, `fixed="right"`, `#default="{ row, index }"` |
| `vort-pagination` | `v-model:current`, `v-model:page-size`, `:total`, `show-total-info`, `show-size-changer`, `@change` |
| `vort-form` | `label-width`, `:model`, `:rules`(zod), `ref` |
| `vort-form-item` | `label`, `name`(对应 rules key), `required` |
| `vort-input` | `v-model`, `placeholder` |
| `vort-input-search` | `v-model`, `allow-clear`, `@search`, `@keyup.enter` |
| `vort-input-password` | `v-model`, `placeholder` |
| `vort-select` | `v-model`, `placeholder`, `allow-clear`, `show-search`, `:options`, `@change` |
| `vort-select-option` | `value` |
| `vort-drawer` | `v-model:open`, `:title`, `:width` |
| `vort-dialog` | `:open`, `:title`, `:width`, `:footer`(默认true), `:confirm-loading`, `ok-text`, `@update:open`, `@ok` |
| `vort-tag` | `:color="green\|red\|blue\|orange\|default"`, `size="small"` |
| `vort-popconfirm` | `:title`, `@confirm` |
| `vort-switch` | `v-model:checked`(注意！), `:disabled`, `:loading`, `size="small"` |
| `vort-checkbox` | `v-model:checked`(注意！) |
| `vort-tabs` | `v-model:activeKey`(注意！), `type="line\|card"`, `:hide-content` |
| `vort-tab-pane` | `tab-key`(注意！不是key), `tab` |
| `vort-date-picker` | `v-model`, `value-format="YYYY-MM-DD"`, `placeholder`, `:show-time` |
| `vort-range-picker` | `v-model`, `value-format`, `:placeholder="['开始', '结束']"` |
| `vort-spin` | `:spinning` |
| `vort-tooltip` | `title` |
| `vort-divider` | `type="vertical"` |
| `vort-textarea` | `v-model`, `:rows` |

## 图标规范

禁止 emoji，一律使用 lucide-vue-next。图标需手动 import。

```vue
<script setup>
import { Plus, Edit, Trash2, Search } from "lucide-vue-next";
</script>
<template>
    <Plus :size="14" class="mr-1" />
</template>
```

## 核心 Hooks

### useCrudPage -- CRUD 列表页

```typescript
import { useCrudPage } from "@/hooks";

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

### useDialogForm -- 弹窗表单

```typescript
import { useDialogForm, type DialogFormProps, type CommonFormParams } from "@/hooks";

const { loading, formState, isEdit, isAdd, onSubmit } =
    useDialogForm<FormType>({
        defaultFormState: { name: "", desc: "" },
        detailApi: (params) => request.get(`/xxx/${params.id}`),
        submitApi: (op, data) => op === "create" ? request.post("/xxx", data) : request.put(`/xxx/${data.id}`, data),
        props, formRef
    });
```

## 页面布局模式

### 列表页（双卡片布局）

```vue
<template>
    <div class="space-y-4">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">页面标题</h3>
                <vort-button variant="primary" @click="handleAdd"><Plus :size="14" class="mr-1" /> 新增</vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索..." allow-clear class="flex-1 sm:w-[220px]" @search="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>
        <!-- 表格卡片 -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false">
                <vort-table-column label="名称" prop="name" />
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
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
                <vort-pagination v-model:current="filterParams.page" v-model:page-size="filterParams.size" :total="total" show-total-info show-size-changer @change="loadData" />
            </div>
        </div>
    </div>
</template>
```

### 弹窗表单（标准模板）

```vue
<!-- XxxEditDialog.vue -->
<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@/components/vort";
import { z } from "zod";

const props = defineProps<{ open: boolean; editData: XxxItem | null }>();
const emit = defineEmits<{ (e: "update:open", val: boolean): void; (e: "saved"): void }>();

const formRef = ref();
const saving = ref(false);
const form = ref({ name: "", desc: "" });
const rules = z.object({ name: z.string().min(1, "请输入名称") });

watch(() => props.open, (val) => {
    if (val) {
        form.value = props.editData ? { ...props.editData } : { name: "", desc: "" };
        saving.value = false;
    }
});

async function handleSave() {
    try { await formRef.value?.validate(); } catch { return; }
    saving.value = true;
    try {
        // await createXxx(form.value) or updateXxx(...)
        emit("saved");
        emit("update:open", false);
    } finally { saving.value = false; }
}
</script>
<template>
    <Dialog :open="open" :title="editData ? '编辑' : '新增'" :confirm-loading="saving" ok-text="保存" @ok="handleSave" @update:open="$emit('update:open', $event)">
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="请输入名称" />
            </vort-form-item>
            <vort-form-item label="描述">
                <vort-textarea v-model="form.desc" placeholder="请输入描述" :rows="3" />
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>
```

### 抽屉（查看/编辑/新增三合一）

```vue
<vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="550">
    <div v-if="drawerMode === 'view'" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div><span class="text-sm text-gray-400">名称</span><div class="text-sm text-gray-800 mt-1">{{ row.name }}</div></div>
    </div>
    <template v-else>
        <vort-form label-width="80px">
            <vort-form-item label="名称" required><vort-input v-model="row.name" /></vort-form-item>
        </vort-form>
        <div class="flex justify-end gap-3 mt-6">
            <vort-button @click="drawerVisible = false">取消</vort-button>
            <vort-button variant="primary" @click="handleSave">确定</vort-button>
        </div>
    </template>
</vort-drawer>
```

### 详情展示

```vue
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div><span class="text-sm text-gray-400">字段名</span><div class="text-sm text-gray-800 mt-1">{{ value }}</div></div>
    <div><span class="text-sm text-gray-400">状态</span><div class="mt-1"><vort-tag :color="colorMap[state]">{{ label }}</vort-tag></div></div>
</div>
```

### 卡片列表

```vue
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    <div class="bg-white rounded-xl border-2 border-dashed border-gray-200 flex items-center justify-center cursor-pointer hover:border-blue-400 min-h-[160px]" @click="handleAdd">
        <div class="text-center text-gray-400"><Plus :size="24" class="mx-auto mb-1" /><span class="text-sm">新增</span></div>
    </div>
    <div v-for="item in list" :key="item.id" class="bg-white rounded-xl hover:shadow-lg transition-shadow p-4">
        <h4 class="font-medium text-gray-800 mb-1">{{ item.name }}</h4>
        <p class="text-xs text-gray-400 line-clamp-2 mb-3">{{ item.description || '暂无描述' }}</p>
    </div>
</div>
```

## CSS 约定

| 场景 | 类名 |
|------|------|
| 页面容器 | `div.space-y-4` |
| 卡片 | `div.bg-white.rounded-xl.p-6` |
| 区块标题 | `h3.text-base.font-medium.text-gray-800.mb-4` |
| 标题行 | `div.flex.items-center.justify-between.mb-4` |
| 操作链接 | `a.text-sm.text-blue-600.cursor-pointer` |
| 危险操作 | `a.text-sm.text-red-500.cursor-pointer` |
| 字段标签 | `span.text-sm.text-gray-400` |
| 字段值 | `div.text-sm.text-gray-800.mt-1` |
| 抽屉底部按钮 | `div.flex.justify-end.gap-3.mt-6` |

## 其他易错点

### 组件包裹容器导致间距失效

`vort-spin`/`vort-tabs` 会生成额外 DOM 层。`space-y-*`/`gap-*` 必须放在实际内容的直接父级上。

### 日期选择必须用 vort-date-picker

禁止 `<vort-input type="date">`，用 `<vort-date-picker value-format="YYYY-MM-DD">`。

### message 导入路径

```typescript
import { message } from "@/components/vort/message";
message.success("操作成功");
```

### AI 助手创建按钮

```vue
<AiAssistButton prompt="我想创建一个定时任务，请引导我完成设置。" />
```

## API 调用规范

1. API 函数统一定义在 `api/*.ts`，不在组件内直接调用 `request`
2. 使用 `@/utils/request`（自带 token 注入和错误处理）
3. 命名：`get/create/update/delete{Resource}`

## 命名约定

| 类型 | 规范 | 示例 |
|------|------|------|
| 视图文件 | `views/{module}/{Name}.vue` | `views/vortflow/Stories.vue` |
| 弹窗组件 | `components/{Name}EditDialog.vue` | `IterationEditDialog.vue` |
| 接口类型 | `{Name}Item` | `StoryItem` |
| 事件处理 | `handle{Action}` | `handleEdit` |
| API 函数 | `get/create/update/delete{Resource}` | `getVortflowStories` |
