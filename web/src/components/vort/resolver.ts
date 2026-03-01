/**
 * Vort UI 组件解析器
 *
 * 用于 unplugin-vue-components 自动导入
 * 支持 <vort-button> 或 <VortButton> 两种写法
 */

import type { ComponentResolver } from "unplugin-vue-components/types";

// 组件映射表：组件名 -> 导出路径
const componentMap: Record<string, { from: string; name: string }> = {
    // =====================
    // UI 基础库 (vort/)
    // =====================

    // ConfigProvider
    VortConfigProvider: { from: "@/components/vort/config-provider", name: "VortConfigProvider" },

    // Anchor
    VortAnchor: { from: "@/components/vort/anchor", name: "Anchor" },
    VortAnchorLink: { from: "@/components/vort/anchor", name: "AnchorLink" },

    // AutoComplete
    VortAutoComplete: { from: "@/components/vort/auto-complete", name: "AutoComplete" },

    // Button
    VortButton: { from: "@/components/vort/button", name: "Button" },

    // Card
    VortCard: { from: "@/components/vort/card", name: "Card" },

    // Input
    VortInput: { from: "@/components/vort/input", name: "Input" },
    VortInputNumber: { from: "@/components/vort/input", name: "InputNumber" },
    VortInputPassword: { from: "@/components/vort/input", name: "InputPassword" },
    VortInputSearch: { from: "@/components/vort/input", name: "InputSearch" },

    // Textarea
    VortTextarea: { from: "@/components/vort/textarea", name: "Textarea" },

    // Checkbox
    VortCheckbox: { from: "@/components/vort/checkbox", name: "Checkbox" },
    VortCheckboxGroup: { from: "@/components/vort/checkbox", name: "CheckboxGroup" },

    // Radio
    VortRadio: { from: "@/components/vort/radio", name: "Radio" },
    VortRadioGroup: { from: "@/components/vort/radio", name: "RadioGroup" },
    VortRadioButton: { from: "@/components/vort/radio", name: "RadioButton" },

    // Select
    VortSelect: { from: "@/components/vort/select", name: "Select" },
    VortSelectOption: { from: "@/components/vort/select", name: "SelectOption" },

    // Cascader
    VortCascader: { from: "@/components/vort/cascader", name: "Cascader" },

    // Switch
    VortSwitch: { from: "@/components/vort/switch", name: "Switch" },

    // Dialog
    VortDialog: { from: "@/components/vort/dialog", name: "Dialog" },

    // Divider
    VortDivider: { from: "@/components/vort/divider", name: "Divider" },

    // Drawer
    VortDrawer: { from: "@/components/vort/drawer", name: "Drawer" },

    // Dropdown
    VortDropdown: { from: "@/components/vort/dropdown", name: "Dropdown" },
    VortDropdownButton: { from: "@/components/vort/dropdown", name: "DropdownButton" },
    VortDropdownMenuItem: { from: "@/components/vort/dropdown", name: "DropdownMenuItem" },
    VortDropdownMenuSeparator: { from: "@/components/vort/dropdown", name: "DropdownMenuSeparator" },
    VortDropdownMenuLabel: { from: "@/components/vort/dropdown", name: "DropdownMenuLabel" },
    VortDropdownMenuGroup: { from: "@/components/vort/dropdown", name: "DropdownMenuGroup" },
    VortDropdownMenuSub: { from: "@/components/vort/dropdown", name: "DropdownMenuSub" },
    VortDropdownMenuCheckboxItem: { from: "@/components/vort/dropdown", name: "DropdownMenuCheckboxItem" },
    VortDropdownMenuRadioGroup: { from: "@/components/vort/dropdown", name: "DropdownMenuRadioGroup" },
    VortDropdownMenuRadioItem: { from: "@/components/vort/dropdown", name: "DropdownMenuRadioItem" },

    // Alert
    VortAlert: { from: "@/components/vort/alert", name: "Alert" },

    // Badge
    VortBadge: { from: "@/components/vort/badge", name: "Badge" },
    VortBadgeRibbon: { from: "@/components/vort/badge", name: "BadgeRibbon" },
    VortStatusDot: { from: "@/components/vort/badge", name: "StatusDot" },

    // Form
    VortForm: { from: "@/components/vort/form", name: "Form" },
    VortFormItem: { from: "@/components/vort/form", name: "FormItem" },

    // Grid
    VortRow: { from: "@/components/vort/grid", name: "Row" },
    VortCol: { from: "@/components/vort/grid", name: "Col" },

    // Table
    VortTable: { from: "@/components/vort/table", name: "Table" },
    VortTableColumn: { from: "@/components/vort/table", name: "TableColumn" },

    // Pagination
    VortPagination: { from: "@/components/vort/pagination", name: "Pagination" },

    // Image
    VortImage: { from: "@/components/vort/image", name: "Image" },
    VortImagePreviewGroup: { from: "@/components/vort/image", name: "ImagePreviewGroup" },

    // Popover
    VortPopover: { from: "@/components/vort/popover", name: "Popover" },

    // Popconfirm
    VortPopconfirm: { from: "@/components/vort/popconfirm", name: "Popconfirm" },

    // Tooltip
    VortTooltip: { from: "@/components/vort/tooltip", name: "Tooltip" },

    // Tag
    VortTag: { from: "@/components/vort/tag", name: "Tag" },
    VortCheckableTag: { from: "@/components/vort/tag", name: "CheckableTag" },
    VortDraggableTags: { from: "@/components/vort/tag", name: "DraggableTags" },

    // DatePicker
    VortDatePicker: { from: "@/components/vort/date-picker", name: "DatePicker" },
    VortRangePicker: { from: "@/components/vort/date-picker", name: "RangePicker" },

    // TimePicker
    VortTimePicker: { from: "@/components/vort/time-picker", name: "TimePicker" },

    // Upload
    VortUpload: { from: "@/components/vort/upload", name: "Upload" },
    VortUploadDragger: { from: "@/components/vort/upload", name: "UploadDragger" },

    // Tabs
    VortTabs: { from: "@/components/vort/tabs", name: "Tabs" },
    VortTabPane: { from: "@/components/vort/tabs", name: "TabPane" },

    // Scrollbar
    VortScrollbar: { from: "@/components/vort/scrollbar", name: "Scrollbar" },

    // Slider
    VortSlider: { from: "@/components/vort/slider", name: "Slider" },

    // ColorPicker
    VortColorPicker: { from: "@/components/vort/color-picker", name: "ColorPicker" },

    // Steps
    VortSteps: { from: "@/components/vort/steps", name: "Steps" },

    // Spin
    VortSpin: { from: "@/components/vort/spin", name: "Spin" },

    // Skeleton
    VortSkeleton: { from: "@/components/vort/skeleton", name: "Skeleton" },
    VortSkeletonAvatar: { from: "@/components/vort/skeleton", name: "SkeletonAvatar" },
    VortSkeletonButton: { from: "@/components/vort/skeleton", name: "SkeletonButton" },
    VortSkeletonInput: { from: "@/components/vort/skeleton", name: "SkeletonInput" },
    VortSkeletonImage: { from: "@/components/vort/skeleton", name: "SkeletonImage" },
    VortSkeletonNode: { from: "@/components/vort/skeleton", name: "SkeletonNode" },

    // Statistic
    VortStatistic: { from: "@/components/vort/statistic", name: "Statistic" },
    VortStatisticCountdown: { from: "@/components/vort/statistic", name: "StatisticCountdown" },

    // Timeline
    VortTimeline: { from: "@/components/vort/timeline", name: "Timeline" },
    VortTimelineItem: { from: "@/components/vort/timeline", name: "TimelineItem" },

    // Segmented
    VortSegmented: { from: "@/components/vort/segmented", name: "Segmented" },

    // Menu
    VortMenu: { from: "@/components/vort/menu", name: "Menu" },
    VortMenuItem: { from: "@/components/vort/menu", name: "MenuItem" },
    VortSubMenu: { from: "@/components/vort/menu", name: "SubMenu" },
    VortMenuItemGroup: { from: "@/components/vort/menu", name: "MenuItemGroup" },
    VortMenuDivider: { from: "@/components/vort/menu", name: "MenuDivider" },

    // =====================
    // 业务 UI 库 (vort-biz/)
    // =====================

    // Icon
    VortIcon: { from: "@/components/vort-biz/icon", name: "VortIcon" },

    // SearchToolbar
    SearchToolbar: { from: "@/components/vort-biz/search-toolbar", name: "SearchToolbar" },
    SearchForm: { from: "@/components/vort-biz/search-toolbar", name: "SearchForm" },
    SearchFormItem: { from: "@/components/vort-biz/search-toolbar", name: "SearchFormItem" },
    SearchFormActions: { from: "@/components/vort-biz/search-toolbar", name: "SearchFormActions" },

    // DialogForm
    DialogForm: { from: "@/components/vort-biz/dialog-form", name: "DialogForm" },

    // PopForm
    PopForm: { from: "@/components/vort-biz/pop-form", name: "PopForm" },

    // TableActions
    TableActions: { from: "@/components/vort-biz/table-actions", name: "TableActions" },
    TableActionsItem: { from: "@/components/vort-biz/table-actions", name: "TableActionsItem" },
    TableActionsMoreItem: { from: "@/components/vort-biz/table-actions", name: "TableActionsMoreItem" },

    // DeleteRecord
    DeleteRecord: { from: "@/components/vort-biz/delete-record", name: "DeleteRecord" },

    // BatchActions
    BatchActions: { from: "@/components/vort-biz/batch-actions", name: "BatchActions" },

    // AiAssistButton
    AiAssistButton: { from: "@/components/vort-biz/ai-assist-button", name: "AiAssistButton" }
};

/**
 * Vort UI 组件解析器
 *
 * @example
 * // vite.config.ts
 * import Components from 'unplugin-vue-components/vite';
 * import { VortResolver } from '@/components/vort/resolver';
 *
 * export default defineConfig({
 *   plugins: [
 *     Components({
 *       resolvers: [VortResolver()]
 *     })
 *   ]
 * });
 *
 * @example
 * // 使用组件（无需手动导入）
 * <vort-button variant="primary">按钮</vort-button>
 * <VortButton variant="primary">按钮</VortButton>
 */
export function VortResolver(): ComponentResolver {
    return {
        type: "component",
        resolve: (name: string) => {
            const component = componentMap[name];
            if (component) {
                return {
                    name: component.name,
                    from: component.from
                };
            }
            return undefined;
        }
    };
}

// 导出组件名列表（用于类型声明）
export const vortComponentNames = Object.keys(componentMap);
