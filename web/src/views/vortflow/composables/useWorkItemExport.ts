import { message } from "@openvort/vort-ui";
import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";
import type { Ref } from "vue";

export interface UseWorkItemExportOptions {
    selectedRows: Ref<RowItem[]>;
    itemRowsById: Record<string, RowItem>;
}

export function useWorkItemExport(options: UseWorkItemExportOptions) {
    const { selectedRows, itemRowsById } = options;

    const getExportData = (): RowItem[] => {
        if (selectedRows.value.length > 0) return selectedRows.value;
        return Object.values(itemRowsById);
    };

    const downloadFile = (content: string, filename: string, type: string) => {
        const bom = type.includes("csv") ? "\uFEFF" : "";
        const blob = new Blob([bom + content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportCsv = () => {
        const rows = getExportData();
        if (!rows.length) { message.warning("暂无数据可导出"); return; }
        const headers = ["工作编号", "标题", "类型", "状态", "优先级", "负责人", "创建人", "标签", "协作者", "创建时间", "计划开始", "计划结束"];
        const csvRows = rows.map(r => [
            r.workNo || "", (r.title || "").replace(/"/g, '""'), r.type || "",
            r.status || "", r.priority || "", r.owner || "", r.creator || "",
            (r.tags || []).join(";"), (r.collaborators || []).join(";"),
            r.createdAt || "", r.planTime?.[0] || "", r.planTime?.[1] || "",
        ].map(v => `"${v}"`).join(","));
        downloadFile([headers.join(","), ...csvRows].join("\n"), `工作项导出_${new Date().toISOString().slice(0, 10)}.csv`, "text/csv;charset=utf-8");
        message.success(`已导出 ${rows.length} 条数据`);
    };

    const handleExportExcel = () => {
        handleExportCsv();
        message.info("已导出为 CSV 格式，可使用 Excel 打开");
    };

    const handleExportJson = () => {
        const rows = getExportData();
        if (!rows.length) { message.warning("暂无数据可导出"); return; }
        const data = rows.map(r => ({
            workNo: r.workNo, title: r.title, type: r.type, status: r.status,
            priority: r.priority, owner: r.owner, creator: r.creator,
            tags: r.tags, collaborators: r.collaborators, createdAt: r.createdAt,
            planTimeStart: r.planTime?.[0] || "", planTimeEnd: r.planTime?.[1] || "",
            description: r.description || "",
        }));
        downloadFile(JSON.stringify(data, null, 2), `工作项导出_${new Date().toISOString().slice(0, 10)}.json`, "application/json;charset=utf-8");
        message.success(`已导出 ${rows.length} 条数据`);
    };

    return {
        getExportData,
        handleExportCsv,
        handleExportExcel,
        handleExportJson,
    };
}
