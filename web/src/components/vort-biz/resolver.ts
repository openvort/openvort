/**
 * Vort Biz 业务组件解析器
 *
 * 用于 unplugin-vue-components 自动导入 openvort 业务组件
 * UI 基础组件由 @openvort/vort-ui/resolver 的 VortResolver 处理
 */

import type { ComponentResolver } from "unplugin-vue-components/types";

const bizComponentMap: Record<string, { from: string; name: string }> = {
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

    // OpenVort extended biz components
    AiAssistButton: { from: "@/components/vort-biz/ai-assist-button", name: "AiAssistButton" },
    VortEditor: { from: "@/components/vort-biz/editor", name: "VortEditor" },
    MarkdownView: { from: "@/components/vort-biz/editor", name: "MarkdownView" },
    DeptTree: { from: "@/components/vort-biz/dept-tree", name: "DeptTree" },
    ProTable: { from: "@/components/vort-biz/pro-table", name: "ProTable" }
};

export function VortBizResolver(): ComponentResolver {
    return {
        type: "component",
        resolve: (name: string) => {
            const component = bizComponentMap[name];
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
