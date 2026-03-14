---
name: openvort-page-extraction
description: 约束 OpenVort 项目中新增/编辑/详情等表单弹窗的代码组织方式。任何模块的新建、编辑、详情弹窗必须提取为独立组件，不允许内联在页面中。新增或修改 VortFlow 迭代、项目、版本、需求、任务、缺陷等模块的弹窗/抽屉表单时使用。
---

# 表单弹窗提取规范

## 核心原则

**所有新建/编辑/详情弹窗必须是独立组件**，由页面 import 后使用。禁止把弹窗的表单模板、校验 schema、保存逻辑内联在页面组件中。

## 适用范围

项目中任何模块的以下交互：

- 新建表单弹窗（Dialog / Drawer）
- 编辑表单弹窗
- 详情展示弹窗/面板

包括但不限于：迭代、项目、版本、需求、任务、缺陷、标签、成员等。

## 规则

### 规则 1：弹窗必须独立成文件

每个弹窗对应一个独立 `.vue` 文件，放在对应模块的 `components/` 目录下。

```text
web/src/views/vortflow/
├── Iterations.vue              # 页面壳，只做列表展示和装配
├── IterationDetail.vue         # 详情页壳
├── components/
│   ├── IterationEditDialog.vue # 新建/编辑迭代弹窗
│   └── ...
```

### 规则 2：弹窗组件的标准接口

弹窗组件必须通过 props/emits 与父组件通信，不依赖路由或全局状态来控制开关：

```typescript
interface Props {
    open: boolean;                // 控制弹窗显隐
    mode?: "add" | "edit";       // 新建或编辑模式
    data?: SomeFormData;         // 初始数据（编辑时传入）
}

const emit = defineEmits<{
    "update:open": [val: boolean];  // v-model:open
    saved: [];                      // 保存成功后通知父组件刷新
}>();
```

父组件使用方式：

```vue
<SomeEditDialog
    v-model:open="dialogOpen"
    :mode="dialogMode"
    :data="dialogData"
    @saved="handleRefresh"
/>
```

### 规则 3：弹窗内部自包含

弹窗组件内部应包含：

- 表单状态（`ref` / `reactive`）
- 校验 schema（zod / rules）
- 保存逻辑（API 调用）
- 表单模板

弹窗组件不应包含：

- 页面路由逻辑
- 列表加载逻辑
- 与弹窗无关的页面级状态

### 规则 4：支持多模式复用

当新建和编辑表单结构相似时，用同一个组件 + `mode` prop 区分：

- `mode="add"` 时显示所属项目选择、文档模板等新建专属字段
- `mode="edit"` 时显示状态选择等编辑专属字段
- 共用字段（标题、负责人、日期等）在两种模式下共享

当结构差异过大（>50% 字段不同）时，拆为两个独立组件。

### 规则 5：已有实现必须遵循

已经提取好的弹窗组件：

| 组件 | 位置 | 用途 |
|------|------|------|
| `IterationEditDialog` | `views/vortflow/components/` | 迭代新建/编辑 |

新增模块时参照此模式。

## 命名约定

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| 新建/编辑弹窗 | `XxxEditDialog.vue` | `IterationEditDialog.vue` |
| 详情弹窗/面板 | `XxxDetailPanel.vue` | `IterationDetailPanel.vue` |
| 新建专用弹窗 | `XxxCreateDialog.vue` | `ProjectCreateDialog.vue` |

## 反例

### 反例：弹窗内联在页面中

```vue
<!-- 坏：页面组件内有 100+ 行弹窗模板和 50+ 行保存逻辑 -->
<script setup>
const formRef = ref();
const formLoading = ref(false);
const schema = z.object({ ... });
const handleSave = async () => { ... };
</script>
<template>
    <!-- 列表内容 -->
    ...
    <!-- 弹窗 -->
    <vort-dialog :open="dialogOpen" ...>
        <vort-form ref="formRef" ...>
            <!-- 大量表单字段 -->
        </vort-form>
    </vort-dialog>
</template>
```

应提取为 `XxxEditDialog.vue`，页面只保留：

```vue
<XxxEditDialog v-model:open="dialogOpen" :mode="mode" :data="data" @saved="refresh" />
```

## 执行检查

每次新增弹窗交互时按此顺序检查：

1. 是否已存在对应弹窗组件？有则复用。
2. 弹窗模板 + 逻辑是否超过 30 行？超过则必须提取。
3. 是否有多个页面需要同一弹窗？必须提取为共享组件。
4. 提取后页面组件是否仍然只负责装配和事件转发？
