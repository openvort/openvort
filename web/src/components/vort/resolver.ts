/**
 * Vort UI 组件解析器
 *
 * 用于 unplugin-vue-components 自动导入
 * 支持 <vort-button> 或 <VortButton> 两种写法
 */

import type { ComponentResolver } from "unplugin-vue-components/types";

const vortBizComponentMap: Record<string, { from: string; name: string }> = {
    VortIcon: { from: "@/components/vort-biz/icon", name: "VortIcon" },

    SearchToolbar: { from: "@/components/vort-biz/search-toolbar", name: "SearchToolbar" },
    SearchForm: { from: "@/components/vort-biz/search-toolbar", name: "SearchForm" },
    SearchFormItem: { from: "@/components/vort-biz/search-toolbar", name: "SearchFormItem" },
    SearchFormActions: { from: "@/components/vort-biz/search-toolbar", name: "SearchFormActions" },

    DialogForm: { from: "@/components/vort-biz/dialog-form", name: "DialogForm" },
    PopForm: { from: "@/components/vort-biz/pop-form", name: "PopForm" },
    TableActions: { from: "@/components/vort-biz/table-actions", name: "TableActions" },
    TableActionsItem: { from: "@/components/vort-biz/table-actions", name: "TableActionsItem" },
    TableActionsMoreItem: { from: "@/components/vort-biz/table-actions", name: "TableActionsMoreItem" },
    DeleteRecord: { from: "@/components/vort-biz/delete-record", name: "DeleteRecord" },
    BatchActions: { from: "@/components/vort-biz/batch-actions", name: "BatchActions" },
    AiAssistButton: { from: "@/components/vort-biz/ai-assist-button", name: "AiAssistButton" },
    VortEditor: { from: "@/components/vort-biz/editor", name: "VortEditor" },
    MarkdownView: { from: "@/components/vort-biz/editor", name: "MarkdownView" },
    DeptTree: { from: "@/components/vort-biz/dept-tree", name: "DeptTree" },
    ProTable: { from: "@/components/vort-biz/pro-table", name: "ProTable" }
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
            const bizComponent = vortBizComponentMap[name];
            if (bizComponent) {
                return {
                    name: bizComponent.name,
                    from: bizComponent.from
                };
            }

            if (name.startsWith("Vort")) {
                return {
                    name: name === "VortConfigProvider" ? "VortConfigProvider" : name.slice(4),
                    from: "@openvort/vort-ui"
                };
            }

            return undefined;
        }
    };
}

// 导出组件名列表（用于类型声明）
export const vortComponentNames = Object.keys(vortBizComponentMap);
