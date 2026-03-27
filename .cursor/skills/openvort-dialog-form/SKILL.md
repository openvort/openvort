---
name: openvort-dialog-form
description: 约束 OpenVort 前端弹窗(Dialog)/抽屉(Drawer)表单的编写方式。新增或修改任何包含表单的弹窗、抽屉组件时必须遵循此规范。涉及 Dialog、Drawer、vort-form、zod 校验、footer 按钮等场景时使用。
---

# 弹窗/抽屉表单规范

## 触发条件

以下任一场景必须阅读并遵循本 Skill：

- 新建弹窗(Dialog)或抽屉(Drawer)组件
- 修改已有弹窗/抽屉中的表单
- 页面中需要新增/编辑/配置等表单交互

## 强制规则（违反即为 BUG）

### 规则 1：弹窗必须是独立 `.vue` 文件

禁止把弹窗模板、表单状态、校验逻辑内联在页面组件中。每个弹窗对应一个独立文件，放在模块的 `components/` 目录下。

```text
web/src/views/{module}/
├── Index.vue                    # 页面壳
├── components/
│   ├── XxxEditDialog.vue        # 新建/编辑弹窗
│   ├── XxxCreateDialog.vue      # 新建专用弹窗
│   └── XxxConfigDrawer.vue      # 配置抽屉
```

页面中只保留引用和事件转发：

```vue
<XxxEditDialog v-model:open="dialogOpen" :data="editData" @saved="refresh" />
```

### 规则 2：表单必须用 `vort-form` + `vort-form-item` + zod 校验

**禁止**使用原生 `<form>`、`<label>`、手动 `if (!xxx) return` 校验。

```vue
<!-- 正确 -->
<vort-form ref="formRef" :model="form" :rules="rules" label-width="120px">
    <vort-form-item label="名称" name="name" required>
        <vort-input v-model="form.name" placeholder="请输入名称" />
    </vort-form-item>
</vort-form>

<script setup lang="ts">
import { z } from "zod";
const rules = z.object({
    name: z.string().min(1, "请输入名称"),
});
</script>
```

```vue
<!-- 禁止 -->
<form @submit.prevent="handleSubmit">
    <label>名称</label>
    <vort-input v-model="form.name" />
</form>
```

**要点：**

- `vort-form-item` 必须设 `name` 属性（对应 zod schema 的 key），否则校验不生效
- 必填字段加 `required` 显示红色星号
- 可选字段的 zod 规则用 `.optional()`
- 提交前必须调用 `formRef.value?.validate()`

### 规则 3：Dialog 按钮用内置 props，不在 body 内放按钮

Dialog 组件内置了 footer 按钮，通过 `@ok` + `:confirm-loading` + `ok-text` 控制。**禁止**在 body 区域自行放置取消/确认按钮。

```vue
<!-- 正确：使用 Dialog 内置 footer -->
<Dialog
    :open="open"
    title="新建视图"
    :confirm-loading="submitting"
    ok-text="创建"
    @ok="handleSubmit"
    @update:open="$emit('update:open', $event)"
>
    <vort-form ...>
        <!-- 表单内容 -->
    </vort-form>
</Dialog>
```

```vue
<!-- 禁止：body 内自己放按钮 -->
<Dialog :open="open" :footer="false">
    <form>
        <vort-input v-model="name" />
        <vort-button @click="save">保存</vort-button>
    </form>
</Dialog>
```

```vue
<!-- 禁止：用底层组件拼装 -->
<VortDialog :open="open">
    <VortDialogContent>
        <VortDialogHeader>
            <VortDialogTitle>标题</VortDialogTitle>
        </VortDialogHeader>
        <!-- 内容 -->
        <VortDialogFooter>
            <VortButton @click="cancel">取消</VortButton>
            <VortButton @click="save">保存</VortButton>
        </VortDialogFooter>
    </VortDialogContent>
</VortDialog>
```

Dialog footer 三种方式（按优先级）：

1. **首选：** 内置 props — `@ok` + `:confirm-loading` + `ok-text`
2. **自定义：** `#footer` 插槽（当按钮逻辑复杂时，如构建确认弹窗）
3. **纯展示：** `:footer="false"`（无需操作按钮的只读弹窗）

### 规则 4：Drawer 表单按钮放在 `#footer` 插槽

Drawer 没有内置 `@ok` 机制，按钮通过 `#footer` 插槽放置：

```vue
<vort-drawer :open="open" :title="title" :width="600" @update:open="handleClose">
    <vort-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <!-- 表单内容 -->
    </vort-form>

    <template #footer>
        <div class="flex justify-end gap-3">
            <vort-button @click="handleClose">取消</vort-button>
            <vort-button variant="primary" :loading="submitting" @click="handleSubmit">保存</vort-button>
        </div>
    </template>
</vort-drawer>
```

### 规则 5：确认按钮必须 `variant="primary"`

主操作按钮（保存/提交/确认/创建）必须 `variant="primary"`，取消按钮用默认样式。Dialog 内置 footer 已自动处理，Drawer 的 `#footer` 需手动设置。

### 规则 6：`label-width` 适配最长 label

| label 字数 | 推荐 label-width |
|-----------|-----------------|
| 2-3 字 | `80px` |
| 4 字 | `100px` |
| 5-6 字 | `120px` |
| 7+ 字 | `140px` |

## Dialog 表单完整模板

```vue
<!-- XxxEditDialog.vue -->
<template>
    <Dialog
        :open="open"
        :title="editData ? '编辑 Xxx' : '新建 Xxx'"
        :confirm-loading="submitting"
        :ok-text="editData ? '保存' : '创建'"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="请输入名称" />
            </vort-form-item>
            <vort-form-item label="描述" name="description">
                <vort-textarea v-model="form.description" placeholder="请输入描述" :rows="3" />
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@/components/vort";
import { z } from "zod";

const props = defineProps<{
    open: boolean;
    editData?: { name: string; description: string } | null;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "saved"): void;
}>();

const formRef = ref();
const submitting = ref(false);
const form = ref({ name: "", description: "" });

const rules = z.object({
    name: z.string().min(1, "请输入名称"),
    description: z.string().optional(),
});

watch(() => props.open, (val) => {
    if (val) {
        form.value = props.editData
            ? { ...props.editData }
            : { name: "", description: "" };
        submitting.value = false;
    }
});

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        // await createXxx(form.value) 或 updateXxx(form.value)
        emit("saved");
        emit("update:open", false);
    } finally {
        submitting.value = false;
    }
}
</script>
```

## Drawer 表单完整模板

```vue
<!-- XxxConfigDrawer.vue -->
<template>
    <vort-drawer :open="open" :title="title" :width="600" @update:open="handleClose">
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="请输入名称" />
            </vort-form-item>
        </vort-form>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="handleClose">取消</vort-button>
                <vort-button variant="primary" :loading="submitting" @click="handleSubmit">保存</vort-button>
            </div>
        </template>
    </vort-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { z } from "zod";

const props = defineProps<{
    open: boolean;
    editData?: { name: string } | null;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const title = computed(() => props.editData ? "编辑" : "新建");

const formRef = ref();
const submitting = ref(false);
const form = ref({ name: "" });

const rules = z.object({
    name: z.string().min(1, "请输入名称"),
});

watch(() => props.open, (val) => {
    if (val) {
        form.value = props.editData ? { ...props.editData } : { name: "" };
        submitting.value = false;
    }
});

function handleClose() {
    emit("update:open", false);
}

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        // await createXxx(form.value) 或 updateXxx(form.value)
        emit("saved");
        emit("update:open", false);
    } finally {
        submitting.value = false;
    }
}
</script>
```

## 检查清单

每次生成弹窗/抽屉表单代码前，逐项检查：

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | 独立文件 | 弹窗是独立 `.vue` 文件，不内联在页面中 |
| 2 | 容器组件 | Dialog 用 `Dialog` from `@/components/vort`，不用底层 `VortDialog/VortDialogContent` |
| 3 | 表单组件 | 用 `vort-form` + `vort-form-item`，不用原生 `<form>` + `<label>` |
| 4 | 校验方式 | 用 zod schema + `formRef.validate()`，不用手动 if 校验 |
| 5 | 按钮位置 | Dialog 用 `@ok`/`:confirm-loading` 或 `#footer`；Drawer 用 `#footer`；不在 body 内放按钮 |
| 6 | 按钮样式 | 确认按钮 `variant="primary"`，取消按钮默认样式 |
| 7 | form-item name | 每个需校验的 `vort-form-item` 都有 `name` 属性（对应 zod key） |
| 8 | label-width | 根据最长 label 字数选择合适宽度 |
| 9 | 表单状态 | 用 `ref({})` 而非 `reactive({})`，与项目约定一致 |
| 10 | open 监听 | `watch(() => props.open)` 中重置表单和 submitting 状态 |
