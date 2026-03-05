# Vort UI — shadcn 式分发方案设计文档

> 本文档基于 `vort-ui-demo` 源码的静态分析，记录了 vort-ui 与 shadcn 的架构差异，以及实现"npm 包 + shadcn 式源码拷贝"双模式分发的完整方案。

---

## 一、vort-ui 与 shadcn-vue 架构差异

### 1.1 分发模型对比


| 维度    | shadcn-vue                  | vort-ui (当前)                                 |
| ----- | --------------------------- | -------------------------------------------- |
| 分发方式  | CLI 拷贝源码到用户项目               | npm 包 (`@openvort/vort-ui`)                  |
| 组件所有权 | 用户拥有源码，可随意修改                | 组件在 `node_modules`，不可改                       |
| 更新方式  | `npx shadcn-vue diff` 对比差异  | `pnpm update`                                |
| 样式方案  | Tailwind CSS class（写在组件内）   | CSS 变量 + scoped CSS                          |
| 底层原语  | reka-ui (headless)          | 部分用 reka-ui，部分自研                             |
| 组件间依赖 | 极少（几乎每个组件独立）                | 较多（深度交叉引用）                                   |
| 基础设施  | 极薄（cn 函数 + tailwind config） | 较厚（icons/composables/locale/config-provider） |


### 1.2 组件间依赖图（从源码提取）

vort-ui 的 50+ 组件存在以下交叉依赖，这是与 shadcn 最大的架构差异：

```
基础设施层（被广泛依赖）
├── icons/           ← 30+ 个组件引用
├── composables/     ← 15+ 个组件引用
│   ├── useFloating      → tooltip, popover, popconfirm, dropdown, color-picker
│   ├── useZIndex        → tooltip, popover, popconfirm, dropdown, select, date-picker, time-picker, auto-complete, color-picker
│   ├── useSSR           → message, notification, dialog, client-only
│   ├── useTeleportContainer → dialog, drawer, image, tooltip, popover, popconfirm, dropdown, select, date-picker, time-picker, auto-complete, cascader, color-picker
│   └── useVirtualScroll → table
├── locale/          ← pagination, date-picker, time-picker, select, table
└── config-provider/ ← 全局主题注入

组件间依赖
├── button/       ← dialog, dropdown-button, date-picker, time-picker, color-picker, input-search, confirm-dialog
├── tooltip/      ← slider, form-item
├── input/        ← pagination, auto-complete, color-picker
├── select/       ← pagination, color-picker
└── checkbox/     ← cascader
```

**关键结论**：如果做纯 shadcn 模式（全部拷贝），添加 `color-picker` 会连锁拉入 `button` + `input` + `select` + `icons`（30+ 文件） + `composables`（5 文件），这不现实。

### 1.3 外部依赖分布


| npm 依赖                    | 使用的组件                              |
| ------------------------- | ---------------------------------- |
| `reka-ui`                 | select (11 个文件), dropdown (10 个文件) |
| `lucide-vue-next`         | select, image, dropdown, dialog    |
| `dayjs`                   | date-picker, time-picker           |
| `clsx` + `tailwind-merge` | lib/utils.ts (cn 函数)               |
| `@vueuse/core`            | 部分 composable                      |
| `vee-validate` + `zod`    | form 验证                            |


### 1.4 样式方案差异

**shadcn-vue**：组件样式完全由 Tailwind CSS class 内联，修改样式就是改 class 字符串。

**vort-ui**：采用 CSS 变量 + scoped CSS 方案：

- `styles/variables.css` — 定义全局 CSS 变量（`--vort-primary`, `--vort-radius` 等）
- 组件内 `<style scoped>` — 通过 CSS 变量实现主题化
- `ConfigProvider` — 运行时动态注入 CSS 变量

这意味着 vort-ui 的样式系统比 shadcn 更"结构化"，不适合让用户随意拆散。

---

## 二、推荐方案：分层架构

### 2.1 核心思路

```
用户的可控区域                     npm 管理的稳定区域
┌──────────────────────┐     ┌──────────────────────────┐
│  src/                │     │  node_modules/           │
│  ├── lib/utils.ts    │     │  └── @openvort/          │
│  └── components/     │     │      ├── vort-ui-core/   │
│      └── vort/       │     │      │   ├── icons/      │
│          ├── button/  │────>│      │   ├── composables/│
│          ├── dialog/  │     │      │   ├── locale/     │
│          ├── table/   │     │      │   ├── styles/     │
│          └── ...     │     │      │   └── config-prov/ │
│                      │     │      │                    │
│   CLI 拷贝，用户可修改 │     │      └── vort-ui/       │
│                      │     │          (整包，兼容老用户) │
└──────────────────────┘     └──────────────────────────┘
```

### 2.2 分层原则


| 层                             | 包名                       | 分发方式   | 理由                           |
| ----------------------------- | ------------------------ | ------ | ---------------------------- |
| 图标 (`icons/`)                 | `@openvort/vort-ui-core` | npm    | 30+ SVG 组件，用户不会改 path 数据     |
| 组合式函数 (`composables/`)        | `@openvort/vort-ui-core` | npm    | 通用工具逻辑，不是 UI，无定制需求           |
| 国际化 (`locale/`)               | `@openvort/vort-ui-core` | npm    | 标准 i18n 文案，增删语言走 PR          |
| CSS 变量 (`styles/`)            | `@openvort/vort-ui-core` | npm    | 用户通过 ConfigProvider 覆盖，不改源文件 |
| 全局配置 (`config-provider/`)     | `@openvort/vort-ui-core` | npm    | 主题注入逻辑稳定不变                   |
| 工具函数 (`lib/utils.ts`)         | CLI init                 | 拷贝     | cn() 函数，shadcn 标配            |
| **UI 组件** (button, dialog...) | CLI add                  | **拷贝** | **用户想改的核心目标**                |


### 2.3 两种模式并存

```bash
# 模式 A：传统 npm 整包（零配置，适合不需要深度定制的用户）
pnpm add @openvort/vort-ui
# 使用：import { Button } from '@openvort/vort-ui'

# 模式 B：shadcn 式（源码拷贝，适合需要深度定制的用户）
pnpm add @openvort/vort-ui-core    # 基础设施
npx @openvort/vort-cli init         # 初始化配置
npx @openvort/vort-cli add button   # 拷贝组件源码
# 使用：import { Button } from '@/components/vort/button'
```

原有 `@openvort/vort-ui` 包不需要任何改动，继续发布维护。

---

## 三、npm 包结构设计

### 3.1 `@openvort/vort-ui-core`

```
@openvort/vort-ui-core/
├── package.json
├── dist/
│   ├── index.js              # 统一导出
│   ├── index.d.ts
│   ├── icons/
│   │   ├── index.js
│   │   ├── index.d.ts
│   │   ├── LoadingOutlined.vue.js
│   │   └── ...               # 30+ 图标组件
│   ├── composables/
│   │   ├── index.js
│   │   ├── index.d.ts
│   │   ├── useFloating.js
│   │   ├── useZIndex.js
│   │   ├── useSSR.js
│   │   ├── useTeleportContainer.js
│   │   └── useVirtualScroll.js
│   ├── locale/
│   │   ├── index.js
│   │   ├── zh-CN.js
│   │   ├── en-US.js
│   │   └── useLocale.js
│   ├── config-provider/
│   │   ├── ConfigProvider.vue.js
│   │   ├── index.js
│   │   └── types.d.ts
│   └── styles/
│       └── index.css          # 包含 variables + motion + themes
└── src/                       # 源码（供 CLI 读取）
    └── ...
```

**package.json exports**：

```json
{
  "name": "@openvort/vort-ui-core",
  "version": "1.0.0",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./icons": {
      "types": "./dist/icons/index.d.ts",
      "import": "./dist/icons/index.js"
    },
    "./composables": {
      "types": "./dist/composables/index.d.ts",
      "import": "./dist/composables/index.js"
    },
    "./locale": {
      "types": "./dist/locale/index.d.ts",
      "import": "./dist/locale/index.js"
    },
    "./config-provider": {
      "types": "./dist/config-provider/index.d.ts",
      "import": "./dist/config-provider/index.js"
    },
    "./styles": "./dist/styles/index.css"
  },
  "peerDependencies": {
    "vue": "^3.4.0"
  },
  "dependencies": {
    "@vueuse/core": "^14.2.0"
  }
}
```

### 3.2 `@openvort/vort-cli`

```
@openvort/vort-cli/
├── package.json
├── bin/
│   └── vort.mjs              # CLI 入口
├── src/
│   ├── commands/
│   │   ├── init.ts            # 初始化项目配置
│   │   ├── add.ts             # 添加组件
│   │   ├── diff.ts            # 对比本地与最新版差异
│   │   └── list.ts            # 列出可用组件
│   ├── registry/
│   │   ├── index.ts           # 注册表入口
│   │   └── components.ts      # 所有组件的注册信息
│   ├── templates/             # 组件源码模板（初始内嵌，后续可迁移为远程）
│   │   ├── button/
│   │   ├── dialog/
│   │   └── ...
│   └── utils/
│       ├── config.ts          # 读写 vort.json
│       ├── transform.ts       # 路径重写
│       ├── deps.ts            # 依赖解析
│       └── fs.ts              # 文件操作
└── tsconfig.json
```

---

## 四、组件注册表 (Registry)

### 4.1 数据结构

```typescript
interface RegistryEntry {
  /** 组件标识 */
  name: string;
  /** 分类标签 */
  category: "general" | "layout" | "data-entry" | "data-display" | "feedback" | "navigation";
  /** 需要拷贝的文件列表（相对于 src/components/vort/） */
  files: string[];
  /** 需要安装的 npm 依赖 */
  dependencies: string[];
  /** 依赖的其他 registry 组件（CLI 自动递归安装） */
  registryDependencies: string[];
  /** 使用的 core 包子路径（用于 import 重写） */
  coreImports: ("icons" | "composables" | "locale" | "config-provider" | "styles")[];
}
```

### 4.2 完整注册表

```typescript
export const registry: Record<string, RegistryEntry> = {

  // ===== 通用 =====

  button: {
    name: "button",
    category: "general",
    files: ["button/Button.vue", "button/index.ts", "button/types.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  divider: {
    name: "divider",
    category: "general",
    files: ["divider/Divider.vue", "divider/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  dropdown: {
    name: "dropdown",
    category: "general",
    files: [
      "dropdown/Dropdown.vue",
      "dropdown/DropdownButton.vue",
      "dropdown/DropdownMenuItem.vue",
      "dropdown/DropdownMenuSeparator.vue",
      "dropdown/DropdownMenuLabel.vue",
      "dropdown/DropdownMenuGroup.vue",
      "dropdown/DropdownMenuSub.vue",
      "dropdown/DropdownMenuCheckboxItem.vue",
      "dropdown/DropdownMenuRadioGroup.vue",
      "dropdown/DropdownMenuRadioItem.vue",
      "dropdown/dropdown.css",
      "dropdown/types.ts",
      "dropdown/index.ts",
    ],
    dependencies: ["reka-ui", "lucide-vue-next"],
    registryDependencies: ["button"],
    coreImports: ["composables", "icons"],
  },

  menu: {
    name: "menu",
    category: "navigation",
    files: [
      "menu/Menu.vue",
      "menu/MenuItem.vue",
      "menu/MenuItemGroup.vue",
      "menu/SubMenu.vue",
      "menu/MenuDivider.vue",
      "menu/menu.css",
      "menu/types.ts",
      "menu/index.ts",
    ],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  // ===== 布局 =====

  card: {
    name: "card",
    category: "layout",
    files: ["card/Card.vue", "card/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  grid: {
    name: "grid",
    category: "layout",
    files: ["grid/Row.vue", "grid/Col.vue", "grid/types.ts", "grid/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  scrollbar: {
    name: "scrollbar",
    category: "layout",
    files: ["scrollbar/Scrollbar.vue", "scrollbar/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  anchor: {
    name: "anchor",
    category: "layout",
    files: ["anchor/Anchor.vue", "anchor/AnchorLink.vue", "anchor/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  // ===== 数据录入 =====

  input: {
    name: "input",
    category: "data-entry",
    files: [
      "input/Input.vue",
      "input/InputNumber.vue",
      "input/InputPassword.vue",
      "input/InputSearch.vue",
      "input/types.ts",
      "input/index.ts",
    ],
    dependencies: [],
    registryDependencies: ["button"],
    coreImports: ["icons"],
  },

  textarea: {
    name: "textarea",
    category: "data-entry",
    files: ["textarea/Textarea.vue", "textarea/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  select: {
    name: "select",
    category: "data-entry",
    files: [
      "select/Select.vue",
      "select/SelectOption.vue",
      "select/SelectContent.vue",
      "select/SelectGroup.vue",
      "select/SelectItem.vue",
      "select/SelectItemText.vue",
      "select/SelectLabel.vue",
      "select/SelectScrollDownButton.vue",
      "select/SelectScrollUpButton.vue",
      "select/SelectSeparator.vue",
      "select/SelectTrigger.vue",
      "select/SelectValue.vue",
      "select/select.css",
      "select/types.ts",
      "select/index.ts",
    ],
    dependencies: ["reka-ui", "lucide-vue-next"],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  checkbox: {
    name: "checkbox",
    category: "data-entry",
    files: ["checkbox/Checkbox.vue", "checkbox/CheckboxGroup.vue", "checkbox/types.ts", "checkbox/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  radio: {
    name: "radio",
    category: "data-entry",
    files: ["radio/Radio.vue", "radio/RadioGroup.vue", "radio/RadioButton.vue", "radio/types.ts", "radio/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  switch: {
    name: "switch",
    category: "data-entry",
    files: ["switch/Switch.vue", "switch/types.ts", "switch/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  slider: {
    name: "slider",
    category: "data-entry",
    files: ["slider/Slider.vue", "slider/types.ts", "slider/index.ts"],
    dependencies: [],
    registryDependencies: ["tooltip"],
    coreImports: [],
  },

  "date-picker": {
    name: "date-picker",
    category: "data-entry",
    files: ["date-picker/DatePicker.vue", "date-picker/RangePicker.vue", "date-picker/types.ts", "date-picker/index.ts"],
    dependencies: ["dayjs"],
    registryDependencies: ["button"],
    coreImports: ["composables", "icons"],
  },

  "time-picker": {
    name: "time-picker",
    category: "data-entry",
    files: ["time-picker/TimePicker.vue", "time-picker/index.ts"],
    dependencies: [],
    registryDependencies: ["button"],
    coreImports: ["composables", "icons"],
  },

  "color-picker": {
    name: "color-picker",
    category: "data-entry",
    files: ["color-picker/ColorPicker.vue", "color-picker/index.ts"],
    dependencies: [],
    registryDependencies: ["button", "input", "select"],
    coreImports: ["composables"],
  },

  cascader: {
    name: "cascader",
    category: "data-entry",
    files: ["cascader/Cascader.vue", "cascader/index.ts"],
    dependencies: [],
    registryDependencies: ["checkbox"],
    coreImports: ["composables", "icons"],
  },

  "auto-complete": {
    name: "auto-complete",
    category: "data-entry",
    files: ["auto-complete/AutoComplete.vue", "auto-complete/index.ts"],
    dependencies: [],
    registryDependencies: ["input"],
    coreImports: ["composables"],
  },

  upload: {
    name: "upload",
    category: "data-entry",
    files: ["upload/Upload.vue", "upload/UploadDragger.vue", "upload/types.ts", "upload/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  form: {
    name: "form",
    category: "data-entry",
    files: ["form/Form.vue", "form/FormItem.vue", "form/types.ts", "form/index.ts"],
    dependencies: [],
    registryDependencies: ["tooltip"],
    coreImports: ["icons"],
  },

  // ===== 数据展示 =====

  table: {
    name: "table",
    category: "data-display",
    files: [
      "table/Table.vue",
      "table/TableColumn.vue",
      "table/renderers.ts",
      "table/types.ts",
      "table/composables/useTableSelection.ts",
      "table/composables/index.ts",
      "table/index.ts",
    ],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  pagination: {
    name: "pagination",
    category: "data-display",
    files: ["pagination/Pagination.vue", "pagination/icons.ts", "pagination/types.ts", "pagination/index.ts"],
    dependencies: [],
    registryDependencies: ["select", "input"],
    coreImports: ["locale"],
  },

  tabs: {
    name: "tabs",
    category: "data-display",
    files: ["tabs/Tabs.vue", "tabs/TabPane.vue", "tabs/types.ts", "tabs/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  tag: {
    name: "tag",
    category: "data-display",
    files: ["tag/Tag.vue", "tag/CheckableTag.vue", "tag/DraggableTags.vue", "tag/types.ts", "tag/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  badge: {
    name: "badge",
    category: "data-display",
    files: ["badge/Badge.vue", "badge/BadgeRibbon.vue", "badge/StatusDot.vue", "badge/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  image: {
    name: "image",
    category: "data-display",
    files: ["image/Image.vue", "image/ImagePreviewGroup.vue", "image/index.ts"],
    dependencies: ["lucide-vue-next"],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  statistic: {
    name: "statistic",
    category: "data-display",
    files: ["statistic/Statistic.vue", "statistic/StatisticCountdown.vue", "statistic/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  timeline: {
    name: "timeline",
    category: "data-display",
    files: ["timeline/Timeline.vue", "timeline/TimelineItem.vue", "timeline/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  segmented: {
    name: "segmented",
    category: "data-display",
    files: ["segmented/Segmented.vue", "segmented/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  skeleton: {
    name: "skeleton",
    category: "data-display",
    files: [
      "skeleton/Skeleton.vue",
      "skeleton/SkeletonAvatar.vue",
      "skeleton/SkeletonButton.vue",
      "skeleton/SkeletonInput.vue",
      "skeleton/SkeletonImage.vue",
      "skeleton/SkeletonNode.vue",
      "skeleton/index.ts",
    ],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },

  steps: {
    name: "steps",
    category: "data-display",
    files: ["steps/Steps.vue", "steps/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  // ===== 反馈 =====

  alert: {
    name: "alert",
    category: "feedback",
    files: ["alert/Alert.vue", "alert/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["icons"],
  },

  dialog: {
    name: "dialog",
    category: "feedback",
    files: ["dialog/Dialog.vue", "dialog/ConfirmDialog.vue", "dialog/types.ts", "dialog/index.ts"],
    dependencies: ["lucide-vue-next"],
    registryDependencies: ["button"],
    coreImports: ["composables", "icons"],
  },

  drawer: {
    name: "drawer",
    category: "feedback",
    files: ["drawer/Drawer.vue", "drawer/types.ts", "drawer/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  message: {
    name: "message",
    category: "feedback",
    files: ["message/MessageItem.vue", "message/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  notification: {
    name: "notification",
    category: "feedback",
    files: ["notification/NotificationItem.vue", "notification/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  tooltip: {
    name: "tooltip",
    category: "feedback",
    files: ["tooltip/Tooltip.vue", "tooltip/types.ts", "tooltip/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables"],
  },

  popover: {
    name: "popover",
    category: "feedback",
    files: ["popover/Popover.vue", "popover/types.ts", "popover/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables"],
  },

  popconfirm: {
    name: "popconfirm",
    category: "feedback",
    files: ["popconfirm/Popconfirm.vue", "popconfirm/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: ["composables", "icons"],
  },

  spin: {
    name: "spin",
    category: "feedback",
    files: ["spin/Spin.vue", "spin/index.ts"],
    dependencies: [],
    registryDependencies: [],
    coreImports: [],
  },
};
```

---

## 五、CLI 实现细节

### 5.1 命令一览


| 命令              | 说明                                               | 示例                                         |
| --------------- | ------------------------------------------------ | ------------------------------------------ |
| `init`          | 初始化项目：创建 `vort.json`，拷贝 `lib/utils.ts`，安装 core 包 | `npx @openvort/vort-cli init`              |
| `add <name...>` | 添加一个或多个组件                                        | `npx @openvort/vort-cli add button dialog` |
| `add --all`     | 添加所有组件                                           | `npx @openvort/vort-cli add --all`         |
| `list`          | 列出所有可用组件及安装状态                                    | `npx @openvort/vort-cli list`              |
| `diff <name>`   | 对比本地组件与最新版本的差异                                   | `npx @openvort/vort-cli diff button`       |


### 5.2 `init` 命令流程

```
1. 检测项目类型（Vite / Nuxt / 其他）
2. 交互式询问：
   - 组件安装路径？（默认 src/components/vort）
   - utils 路径？（默认 src/lib）
   - TypeScript？（自动检测 tsconfig.json）
   - 路径别名？（自动检测 vite.config.ts 中的 alias）
3. 生成 vort.json 配置文件
4. 拷贝 lib/utils.ts（cn 函数）
5. 安装 @openvort/vort-ui-core（如果尚未安装）
6. 在 CSS 入口文件中注入 @import "@openvort/vort-ui-core/styles"
```

### 5.3 `add` 命令流程

```
1. 读取 vort.json 配置
2. 解析依赖树：
   add color-picker
   → 解析 registryDependencies: [button, input, select]
   → 递归解析 input 的 registryDependencies: [button] (已包含，跳过)
   → 最终列表: [color-picker, button, input, select]
3. 过滤已安装的组件：
   → 检查 vort.json 的 installedComponents
   → 如果 button 已安装，提示跳过
4. 对每个待安装组件：
   a. 读取源码文件
   b. 执行路径重写（见 5.4）
   c. 写入到用户项目目录
   d. 确认覆盖（如果文件已存在）
5. 安装 npm 依赖：
   → 收集所有组件的 dependencies: [reka-ui, lucide-vue-next]
   → 执行 pnpm add reka-ui lucide-vue-next
6. 更新 vort.json 的 installedComponents
7. 输出安装摘要
```

### 5.4 路径重写规则

CLI 拷贝文件时执行以下替换：

```typescript
const REWRITE_RULES = [
  // 基础设施 → core 包
  { from: '@/components/vort/icons',             to: '@openvort/vort-ui-core/icons' },
  { from: '@/components/vort/composables',       to: '@openvort/vort-ui-core/composables' },
  { from: '@/components/vort/locale',            to: '@openvort/vort-ui-core/locale' },
  { from: '@/components/vort/config-provider',   to: '@openvort/vort-ui-core/config-provider' },
  { from: '@/components/vort/styles',            to: '@openvort/vort-ui-core/styles' },

  // 组件间依赖 → 保持本地路径（使用用户配置的 alias）
  // @/components/vort/<component> → {aliases.components}/<component>
  // 例如: @/components/vort/button → @/components/vort/button（通常不变）

  // 工具函数
  // @/lib/utils → {aliases.utils}/utils
];
```

**重写示例**：

源码中的 `Dialog.vue`：

```vue
<script setup>
import { X } from "lucide-vue-next";
import { getVortTeleportTo, useZIndexProviderValue } from "@/components/vort/composables";
import { Button } from "@/components/vort/button";
import { CloseOutlined } from "@/components/vort/icons";
</script>
```

重写后（用户项目中）：

```vue
<script setup>
import { X } from "lucide-vue-next";
import { getVortTeleportTo, useZIndexProviderValue } from "@openvort/vort-ui-core/composables";
import { Button } from "@/components/vort/button";
import { CloseOutlined } from "@openvort/vort-ui-core/icons";
</script>
```

### 5.5 `vort.json` 配置文件格式

```json
{
  "$schema": "https://vortui.com/schema.json",
  "typescript": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/assets/main.css"
  },
  "aliases": {
    "components": "@/components/vort",
    "utils": "@/lib"
  },
  "installedComponents": [
    "button",
    "dialog",
    "input"
  ]
}
```

---

## 六、Registry 分发策略

### 6.1 方案对比


| 方案                | 说明                   | 优点              | 缺点            |
| ----------------- | -------------------- | --------------- | ------------- |
| **A: 本地打包**       | 组件源码打包在 CLI 的 npm 包里 | 简单，无网络依赖        | 更新组件需要发新版 CLI |
| **B: 远程 API**     | 组件源码托管在 HTTP API     | 组件与 CLI 解耦，独立更新 | 需要服务器，有网络依赖   |
| **C: GitHub Raw** | 直接从 GitHub 仓库读取源码    | 无需独立服务，版本即 tag  | 依赖 GitHub 可用性 |


### 6.2 推荐路线

```
第一阶段 → 方案 A（本地打包）
  - 快速验证，最小工作量
  - 组件源码放在 @openvort/vort-cli 的 templates/ 目录
  - 每次 vort-ui 发版时同步更新 CLI

第二阶段 → 方案 C（GitHub Raw）
  - CLI 从 GitHub 仓库的指定 tag 拉取组件源码
  - URL 格式：https://raw.githubusercontent.com/openvort/vort-ui/{version}/src/components/vort/{component}/
  - 支持 --tag 参数指定版本

第三阶段 → 方案 B（远程 API）
  - 搭建 vortui.com/registry API
  - 支持版本管理、组件搜索、依赖预解析
  - 可做 CDN 缓存
```

---

## 七、技术选型

### 7.1 CLI 框架


| 框架          | Star    | 特点               | 推荐  |
| ----------- | ------- | ---------------- | --- |
| `citty`     | unjs 生态 | 轻量、TypeScript 优先 | 首选  |
| `commander` | 经典      | 功能全面、社区大         | 备选  |
| `cac`       | vue 生态用 | 轻量、API 简洁        | 备选  |


推荐 `citty`，理由：

- unjs 生态与 Vue/Nuxt 一脉相承
- 零依赖，包体积极小
- TypeScript 类型完善

### 7.2 辅助依赖

```json
{
  "dependencies": {
    "citty": "latest",
    "consola": "latest",
    "pathe": "latest",
    "defu": "latest",
    "fast-glob": "latest",
    "diff": "latest"
  }
}
```


| 包           | 用途             |
| ----------- | -------------- |
| `citty`     | CLI 命令定义       |
| `consola`   | 美观的控制台输出       |
| `pathe`     | 跨平台路径处理        |
| `defu`      | 深度合并配置         |
| `fast-glob` | 检测已安装组件        |
| `diff`      | diff 命令的文本差异对比 |


---

## 八、实施路线图

### Phase 1：基础建设（预计 2-3 天）

- 创建 `@openvort/vort-ui-core` 包结构
- 从 vort-ui-demo 抽离基础设施代码（icons, composables, locale, styles, config-provider）
- 配置 vite.config.lib.ts 打包 core 包
- 发布 `@openvort/vort-ui-core@1.0.0`

### Phase 2：CLI 开发（预计 3-5 天）

- 搭建 CLI 项目骨架（citty + TypeScript）
- 实现 `init` 命令
- 实现 `add` 命令（含依赖解析 + 路径重写）
- 实现 `list` 命令
- 编写完整的 registry 数据（50 个组件）
- 本地打包组件模板

### Phase 3：测试验证（预计 1-2 天）

- 创建测试项目，验证 `init` + `add` 全流程
- 验证组件间依赖正确解析
- 验证路径重写无遗漏
- 验证与 Vort-Admin 和 vortmall-pc 的兼容性

### Phase 4：文档与发布（预计 1 天）

- 编写 CLI 使用文档
- 更新 vort-ui README（添加 shadcn 模式说明）
- 发布 `@openvort/vort-cli@1.0.0`
- 发布更新后的 `@openvort/vort-ui`（保持兼容）

### Phase 5：迭代优化（持续）

- 实现 `diff` 命令
- 迁移到 GitHub Raw 分发
- 搭建在线 Registry API
- 添加组件预览图到 CLI 输出

---

## 九、注意事项

### 9.1 避免的坑

1. **不要把每个组件都发独立 npm 包** — Element Plus 走过这条路（`@element-plus/components` 下几十个子包），版本管理和发布流程极其痛苦。
2. **不要在 CLI 中做 AST 级别的代码转换** — 简单的字符串替换足够覆盖当前的路径重写需求，AST 转换（如 babel/SWC）增加大量复杂度但收益极小。
3. **不要强制用户切换到 shadcn 模式** — 很多用户只想 `pnpm add` 然后用，传统 npm 包模式必须继续支持。

### 9.2 需要决策的问题

1. **core 包和 CLI 是否放在同一个 monorepo？** — 建议是，方便版本同步。
2. **CLI 是否支持 monorepo 项目（如 Vort-Admin + vortmall-pc 共享组件）？** — 暂不考虑，后续迭代。
3. **组件的 scoped CSS 是否需要支持提取为 Tailwind class？** — 暂不需要，当前 CSS 变量方案已经够灵活。

---

## 十、风险评估与替代思路

### 10.1 核心质疑：用户是否真的需要改源码？

shadcn/ui 的诞生有其特定背景：React + Tailwind 成为主流，headless 组件库（Radix）成熟使样式层极薄，用户对 node_modules 黑盒极度不满。但 vort-ui 的用户未必有同样的痛点。

如果大多数定制需求可被以下方式覆盖，那 shadcn 模式的投入产出比可能不划算：

| 定制需求 | 现有方案是否可解决 |
|---------|-----------------|
| 改颜色/圆角/间距 | ✅ CSS 变量 + ConfigProvider |
| 改组件局部行为 | ✅ slot + expose + 事件 |
| 改组件的 DOM 结构 | ❌ 需要源码级别控制 |

**建议**：在投入开发前，先通过用户调研确认"想改源码"是否是真实的高频需求。

### 10.2 风险清单

#### 风险 1：定制体验名不副实

shadcn 的用户体验是打开源码直接改 Tailwind class 字符串，所见即所得：

```vue
<!-- shadcn: 直接改 class -->
<div class="rounded-lg p-4 bg-primary">  →  <div class="rounded-xl p-6 bg-blue-500">
```

但 vort-ui 拷贝给用户的组件仍然是 **scoped CSS + CSS 变量**：

```vue
<style scoped>
.vort-button {
  border-radius: var(--vort-radius);
  padding: var(--vort-button-padding);
  background: var(--vort-primary);
}
</style>
```

用户拿到源码后改的还是 CSS 变量名和 scoped 样式 — 这与 shadcn 的"改 class 字符串"体验完全不同。**给了 shadcn 的分发形式，但没给 shadcn 的修改体验**，可能导致用户困惑。

**缓解措施**：若要做 shadcn 模式，应先将组件样式从 scoped CSS 迁移到 Tailwind class + CVA 变体管理，再做 CLI 分发。

#### 风险 2：core 包边界随时间模糊

当前分层看起来清晰，但随着 vort-ui 演进，边界会被持续挑战：

- 新增 composable `useFormValidation` — 放 core 还是跟 form 组件一起拷贝？
- icons 新增一个只被某个组件使用的图标 — 放 core 还是跟组件走？
- 用户想改 `useFloating` 的默认定位逻辑 — 但它在 npm 包里改不了

core 包本质上还是"黑盒"，只是比原来的整包稍小一些，用户的自由度没有质的提升。

**缓解措施**：制定严格的 core 包准入标准 — 只有"被 5 个以上组件依赖 + 用户几乎不会修改"的模块才放入 core。

#### 风险 3：版本耦合

拷贝的组件源码与 npm 的 core 包之间没有版本锁定机制：

1. 用户在 core@1.0 时拷贝了 Button 组件
2. core 升级到 1.1，`useZIndex` 的 API 发生变化
3. 用户升级 core 包 → 拷贝的 Button 源码可能编译失败

shadcn 没有此问题，因为它几乎没有 core 包依赖。vort-ui 因为有较厚的 core 层，这个风险是真实存在的。

**缓解措施**：
- core 包遵循严格的 semver，公开 API 变更必须走 major 版本
- `diff` 命令中集成 core 版本兼容性检查
- core 包导出时附带版本元信息，CLI 可校验

#### 风险 4：维护成本乘数效应

| 包 | 需要维护的事项 |
|---|-------------|
| `@openvort/vort-ui` | 传统模式正常发布 |
| `@openvort/vort-ui-core` | 基础设施独立发版，需保证 API 稳定 |
| `@openvort/vort-cli` | CLI 逻辑 + 内嵌模板 + 注册表与源码同步 |

每次改一个组件，可能需要同时更新 3 个包。对于小团队而言，这个负担不可忽视。

**缓解措施**：放在同一个 monorepo，使用 changesets 或 bumpp 统一发版流程。

#### 风险 5：路径重写的脆弱性

基于字符串替换的路径重写可能在以下场景出错：

- 动态 import（`import()` 表达式）
- 模板字符串中的路径
- re-export 链路较深的情况
- 用户自定义的 alias 与预设冲突

**缓解措施**：为路径重写编写完整的单元测试，覆盖各种 import 模式。

### 10.3 替代思路

#### 思路 A：加强 npm 模式的定制能力（推荐优先考虑）

不做 shadcn 模式，将精力投入让 npm 包更可定制：

1. **更细粒度的 CSS 变量** — 每个组件暴露更多可覆盖的变量
2. **丰富 slot 体系** — 让用户能替换组件内部的任何区域
3. **render 函数 / 自定义渲染器** — 用于 Table 等复杂组件
4. **主题预设系统** — 提供多套预设主题（shadcn 风格、ant 风格、material 风格），一键切换
5. **可选 Tailwind 集成** — 提供 Tailwind plugin，用 utility class 覆盖组件样式

```typescript
import { createVortTheme } from '@openvort/vort-ui'

const theme = createVortTheme({
  preset: 'shadcn',
  overrides: {
    button: { borderRadius: '0.75rem' },
  },
})
```

**优势**：投入小、见效快、不增加维护包数量。

#### 思路 B：先迁移样式再做 CLI

如果确定要做 shadcn 模式，应先完成样式层迁移：

1. 将组件样式从 scoped CSS 迁移到 Tailwind class + CVA
2. 用语义化 CSS 变量定义 Tailwind theme
3. 确保拷贝后的源码用户可以直接改 class 来定制
4. 然后再开发 CLI

这样用户拿到的源码才是真正的 "shadcn 式" 体验。

#### 思路 C：渐进式 — 仅高频定制组件提供拷贝

不需要一开始让 50 个组件都支持拷贝。根据用户反馈找出最常被定制的 5–10 个组件（通常是 Button、Dialog、Table、Form），只对这些提供 shadcn 模式，其余继续走 npm 包。

**优势**：大幅降低 core 包边界设计复杂度和维护成本。

### 10.4 建议的实施策略

| 阶段 | 行动 | 目的 |
|------|------|------|
| 短期（现在） | 思路 A — 加强 npm 包的定制能力 | 投入小、见效快、满足大部分用户 |
| 中期（需求验证后） | 思路 C — 对 5–10 个高频组件试点 shadcn 模式 | 用最小代价验证"用户是否真的想改源码" |
| 长期（试点成功后） | 全量组件 shadcn 模式 + 思路 B 样式迁移 | 此时有经验判断 core 包边界 |

---

## 十一、参考资料

- [shadcn-vue 源码](https://github.com/unovue/shadcn-vue) — CLI 实现参考
- [shadcn/ui 源码](https://github.com/shadcn-ui/ui) — Registry 设计参考
- [citty 文档](https://github.com/unjs/citty) — CLI 框架
- [reka-ui 文档](https://reka-ui.com/) — headless 原语

---

*文档创建时间：2026-03-05*
*基于 `@openvort/vort-ui@1.0.4` 源码分析*