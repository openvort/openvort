import { reactive, ref } from "vue";
import type { Ref, ComputedRef } from "vue";
import type { ProTableRequestParams, ProTableResponse } from "@/components/vort-biz";
import type { ColumnFilterValue } from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import type {
    WorkItemType,
    RowItem,
    Status,
} from "@/components/vort-biz/work-item/WorkItemTable.types";
import {
    getVortflowStory, getVortflowStories,
    getVortflowTask, getVortflowTasks,
    getVortflowBug, getVortflowBugs,
} from "@/api";

export const SORT_FIELD_MAP: Record<string, string> = {
    createdAt: "created_at",
    updatedAt: "updated_at",
    priority: "priority",
    title: "title",
    status: "state",
    planTime: "deadline",
    owner: "assignee_id",
    creator: "creator_id",
};

export const SORT_FIELD_OVERRIDES: Record<string, Record<string, string>> = {
    "需求": { owner: "assignee_id", creator: "submitter_id" },
    "缺陷": { creator: "reporter_id" },
};

export interface UseWorkItemDataSourceOptions {
    useApi: ComputedRef<boolean> | Ref<boolean>;
    propType: string;
    propProjectId: ComputedRef<string> | Ref<string>;
    propIterationId: ComputedRef<string> | Ref<string>;
    propViewFilters: ComputedRef<Record<string, any>> | Ref<Record<string, any>>;
    type: Ref<string>;
    owner: Ref<string>;
    status: Ref<string[]>;
    columnFilters: Record<string, ColumnFilterValue | null>;
    columnSortField: Ref<string>;
    columnSortOrder: Ref<"ascend" | "descend" | null>;
    totalCount: Ref<number>;
    apiProjects: Ref<Array<{ id: string; name: string }>>;
    pinnedRowsByType: Record<WorkItemType, RowItem[]>;
    expandedItemIds: Record<string, boolean>;
    expandingItemIds: Record<string, boolean>;
    itemRowsById: Record<string, RowItem>;
    itemChildrenMap: Record<string, RowItem[]>;
    getMemberIdByName: (name: string) => string;
    getMemberNameById: (id: string) => string;
    loadMemberOptions?: () => Promise<void>;
    mapBackendStateToStatus: (type: WorkItemType, state: string) => Status;
    mapBackendPriority: (item: any, type: WorkItemType) => any;
    getBackendStatesByDisplayStatus: (type: WorkItemType, status: Status | string) => string[] | undefined;
    formatCnTime: (date: Date) => string;
    formatDate: (date: Date) => string;
    collectTagOptions: (rows: RowItem[]) => void;
    collectEnumOptions: (rows: RowItem[]) => void;
}

export function useWorkItemDataSource(options: UseWorkItemDataSourceOptions) {
    const {
        useApi,
        propType,
        propProjectId,
        propIterationId,
        propViewFilters,
        type,
        owner,
        status,
        columnFilters,
        columnSortField,
        columnSortOrder,
        totalCount,
        apiProjects,
        pinnedRowsByType,
        expandedItemIds,
        itemRowsById,
        itemChildrenMap,
        getMemberIdByName,
        getMemberNameById,
        loadMemberOptions,
        mapBackendStateToStatus,
        mapBackendPriority,
        getBackendStatesByDisplayStatus,
        formatCnTime,
        formatDate,
        collectTagOptions,
        collectEnumOptions,
    } = options;

    const mapBackendItemToRow = (item: any, typeValue: WorkItemType, index: number): RowItem => {
        const created = item?.created_at ? new Date(item.created_at) : new Date();
        const createdAt = formatCnTime(created);
        const deadline = item?.deadline ? String(item.deadline).split("T")[0] : "";
        const backendId = String(item?.id || index + 1);
        const workNo = `#${backendId.replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`;
        const ownerSourceId = String(item?.assignee_id || item?.pm_id || item?.developer_id || "").trim();
        const ownerSourceName = getMemberNameById(ownerSourceId);
        const ownerName = ownerSourceName || (ownerSourceId ? ownerSourceId : "未指派");

        const creatorSourceId = String(item?.submitter_id || item?.creator_id || item?.reporter_id || "").trim();
        const creatorName = getMemberNameById(creatorSourceId) || (creatorSourceId || "");

        const collaboratorsFromBackend = Array.isArray(item?.collaborators)
            ? (item.collaborators as any[]).map((x) => {
                const id = String(x || "").trim();
                return getMemberNameById(id) || id;
            }).filter(Boolean)
            : [];

        const tags: string[] = Array.isArray(item?.tags)
            ? (item.tags as any[]).map((x) => String(x || "").trim()).filter(Boolean)
            : [];

        const planDate = deadline || formatDate(created);
        const updated = item?.updated_at ? new Date(item.updated_at) : null;
        const updatedAt = updated ? formatCnTime(updated) : "";
        const estimateHours = item?.estimate_hours != null ? item.estimate_hours : undefined;
        const loggedHours = item?.actual_hours != null ? item.actual_hours : undefined;
        const remainHours = (estimateHours != null && loggedHours != null)
            ? Math.max(0, Number(estimateHours) - Number(loggedHours))
            : undefined;
        const iterationId = item?.iteration_id ? String(item.iteration_id) : "";
        const versionId = item?.version_id ? String(item.version_id) : "";
        const startAt = item?.start_at ? String(item.start_at).split("T")[0] : "";
        const endAt = item?.end_at ? String(item.end_at).split("T")[0] : "";
        return {
            backendId,
            workNo,
            title: String(item?.title || ""),
            parentId: item?.parent_id ? String(item.parent_id) : "",
            parentTitle: "",
            childrenCount: Number(item?.children_count || 0),
            isChild: Boolean(item?.parent_id),
            priority: mapBackendPriority(item, typeValue),
            tags,
            status: mapBackendStateToStatus(typeValue, String(item?.state || "")),
            createdAt,
            updatedAt,
            collaborators: collaboratorsFromBackend,
            type: typeValue,
            planTime: [planDate, planDate],
            description: item?.description || "",
            ownerId: ownerSourceId,
            owner: ownerName,
            creator: creatorName,
            projectId: item?.project_id ? String(item.project_id) : "",
            projectName: item?.project_id ? (apiProjects.value.find(p => p.id === String(item.project_id))?.name || "") : "",
            iterationId,
            iteration: item?.iteration_name ? String(item.iteration_name) : "",
            versionId,
            version: item?.version_name ? String(item.version_name) : "",
            estimateHours,
            loggedHours,
            remainHours,
            repoId: item?.repo_id ? String(item.repo_id) : "",
            repo: "",
            branch: item?.branch ? String(item.branch) : "",
            startAt,
            endAt,
            _prevIteration: iterationId,
            _prevVersion: versionId,
        };
    };

    const createOwnerMatcher = (ownerValue: string) => {
        const normalizedOwner = String(ownerValue || "").trim();
        const ownerMemberId = normalizedOwner && normalizedOwner !== "未指派" ? getMemberIdByName(normalizedOwner) : "";
        const matchOwner = (row: RowItem) => {
            if (!normalizedOwner) return true;
            if (normalizedOwner === "未指派") return !String(row.ownerId || "").trim();
            if (ownerMemberId) return String(row.ownerId || "").trim() === ownerMemberId;
            return row.owner === normalizedOwner;
        };
        return { ownerMemberId, matchOwner };
    };

    const cacheItemRows = (rows: RowItem[]) => {
        for (const row of rows) {
            if (!row.backendId) continue;
            itemRowsById[row.backendId] = row;
        }
    };

    const findItemRowById = (itemId?: string): RowItem | null => {
        if (!itemId) return null;
        return itemRowsById[itemId] || null;
    };

    const findItemRowByIdentifier = (itemId?: string): RowItem | null => {
        if (!itemId) return null;
        const byBackendId = findItemRowById(itemId);
        if (byBackendId) return byBackendId;
        return Object.values(itemRowsById).find((row) => row.workNo === itemId) || null;
    };

    const loadItemById = async (itemId: string | undefined, itemType: WorkItemType): Promise<RowItem | null> => {
        if (!itemId) return null;
        const cached = findItemRowByIdentifier(itemId);
        if (cached) return cached;
        try {
            const res: any = itemType === "任务"
                ? await getVortflowTask(itemId)
                : itemType === "缺陷"
                    ? await getVortflowBug(itemId)
                    : await getVortflowStory(itemId);
            if (!res?.id) return null;
            const row = mapBackendItemToRow(res, itemType, 0);
            itemRowsById[String(res.id)] = row;
            return row;
        } catch {
            return null;
        }
    };

    const loadChildItems = async (parentId: string, itemType: WorkItemType, projectId?: string): Promise<RowItem[]> => {
        if (!parentId || itemType === "缺陷") return [];
        const res: any = itemType === "任务"
            ? await getVortflowTasks({
                parent_id: parentId,
                page: 1,
                page_size: 100,
            })
            : await getVortflowStories({
                parent_id: parentId,
                project_id: projectId,
                page: 1,
                page_size: 100,
            });
        const rows = ((res?.items || []) as any[]).map((item, index) => {
            const row = mapBackendItemToRow(item, itemType, index);
            row.isChild = true;
            return row;
        });
        cacheItemRows(rows);
        itemChildrenMap[parentId] = rows;
        return rows;
    };

    const getVisibleChildRows = (rows: RowItem[], ownerValue = owner.value, statusValues: string[] = status.value) => {
        const currentType = String(propType ?? type.value ?? "").trim();
        if (!useApi.value || (currentType !== "需求" && currentType !== "任务")) return rows;
        const { matchOwner } = createOwnerMatcher(ownerValue);
        const flattenedRows: RowItem[] = [];
        for (const row of rows) {
            flattenedRows.push(row);
            const itemId = String(row.backendId || "").trim();
            if (!itemId || !expandedItemIds[itemId]) continue;
            const children = (itemChildrenMap[itemId] || [])
                .filter((child) => !statusValues.length || statusValues.includes(child.status))
                .filter(matchOwner)
                .map((child) => ({ ...child, isChild: true }));
            flattenedRows.push(...children);
        }
        return flattenedRows;
    };

    const applyColumnFilters = (rows: RowItem[]): RowItem[] => {
        const filters = columnFilters;
        if (!Object.keys(filters).length) return rows;

        return rows.filter(row => {
            for (const [field, fv] of Object.entries(filters)) {
                if (!fv) continue;
                if (field === "status") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(row.status)) return false;
                } else if (field === "owner") {
                    const vals = fv.value as string[];
                    if (vals?.length) {
                        const rowOwner = String(row.owner || "").trim();
                        const matched = vals.some((value) => {
                            if (value === "__unassigned__") {
                                return !String(row.ownerId || "").trim() || rowOwner === "未指派" || !rowOwner;
                            }
                            return rowOwner === value;
                        });
                        if (!matched) return false;
                    }
                } else if (field === "collaborators") {
                    const vals = fv.value as string[];
                    if (vals?.length) {
                        const rowCollaborators = (row.collaborators || []).map((name) => String(name || "").trim()).filter(Boolean);
                        if (!vals.some((value) => rowCollaborators.includes(value))) return false;
                    }
                } else if (field === "tags") {
                    const vals = fv.value as string[];
                    if (vals?.length) {
                        const rowTags: string[] = row.tags || [];
                        if (!vals.some(v => rowTags.includes(v))) return false;
                    }
                } else if (field === "priority") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(row.priority || "")) return false;
                } else if (field === "iteration") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(row.iteration || "")) return false;
                } else if (field === "version") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(row.version || "")) return false;
                } else if (field === "creator") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(String(row.creator || "").trim())) return false;
                } else if (field === "type") {
                    const vals = fv.value as string[];
                    if (vals?.length && !vals.includes(row.type || "")) return false;
                } else if (field === "createdAt" || field === "planTime" || field === "updatedAt" || field === "startAt" || field === "endAt") {
                    const dateFieldMap: Record<string, string> = {
                        createdAt: row.createdAt,
                        planTime: row.planStartDate || row.planEndDate || "",
                        updatedAt: row.updatedAt || "",
                        startAt: row.startAt || "",
                        endAt: row.endAt || "",
                    };
                    const rowVal = dateFieldMap[field] || "";
                    if (!rowVal) return false;
                    const rowDate = new Date(rowVal).getTime();
                    if (isNaN(rowDate)) return false;
                    const { operator, value } = fv;
                    if (operator === "between") {
                        const [start, end] = value as [string, string];
                        if (start && rowDate < new Date(start).getTime()) return false;
                        if (end && rowDate > new Date(end + "T23:59:59").getTime()) return false;
                    } else {
                        const target = new Date(value).getTime();
                        if (isNaN(target)) continue;
                        if (operator === "gt" && rowDate <= target) return false;
                        if (operator === "lt" && rowDate >= target) return false;
                        if (operator === "gte" && rowDate < target) return false;
                        if (operator === "lte" && rowDate > target) return false;
                        if (operator === "eq" && new Date(rowVal).toDateString() !== new Date(value).toDateString()) return false;
                    }
                }
            }
            return true;
        });
    };

    const applyColumnSort = (rows: RowItem[]): RowItem[] => {
        const field = columnSortField.value;
        const order = columnSortOrder.value;
        if (!field || !order) return rows;

        const sorted = [...rows];
        const dir = order === "ascend" ? 1 : -1;

        sorted.sort((a, b) => {
            let va: any;
            let vb: any;
            if (field === "status") {
                va = a.status || "";
                vb = b.status || "";
            } else if (field === "priority") {
                const priorityOrder: Record<string, number> = { urgent: 1, high: 2, medium: 3, low: 4, none: 5 };
                va = priorityOrder[a.priority] ?? 99;
                vb = priorityOrder[b.priority] ?? 99;
            } else if (field === "tags") {
                va = (a.tags || []).join(",");
                vb = (b.tags || []).join(",");
            } else if (field === "createdAt") {
                va = a.createdAt || "";
                vb = b.createdAt || "";
            } else if (field === "planTime") {
                va = a.planStartDate || a.planEndDate || "";
                vb = b.planStartDate || b.planEndDate || "";
            } else if (field === "updatedAt") {
                va = a.updatedAt || "";
                vb = b.updatedAt || "";
            } else if (field === "iteration") {
                va = a.iteration || "";
                vb = b.iteration || "";
            } else if (field === "version") {
                va = a.version || "";
                vb = b.version || "";
            } else if (field === "creator") {
                va = a.creator || "";
                vb = b.creator || "";
            } else if (field === "type") {
                va = a.type || "";
                vb = b.type || "";
            } else if (field === "startAt") {
                va = a.startAt || "";
                vb = b.startAt || "";
            } else if (field === "endAt") {
                va = a.endAt || "";
                vb = b.endAt || "";
            } else {
                return 0;
            }
            if (va < vb) return -1 * dir;
            if (va > vb) return 1 * dir;
            return 0;
        });
        return sorted;
    };

    const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
        await loadMemberOptions?.();
        const kw = String(params.keyword ?? "").trim().toLowerCase();
        const ownerValue = String(params.owner ?? "").trim();
        const { ownerMemberId, matchOwner } = createOwnerMatcher(ownerValue);
        const typeValue = String(propType ?? params.type ?? "").trim();
        const statusValues: string[] = Array.isArray(params.status) ? params.status.filter(Boolean) : [];
        const current = Number(params.current || 1);
        const pageSize = Number(params.pageSize || 20);

        const effectiveSortField = columnSortField.value || params.sortField || "";
        const effectiveSortOrder = columnSortOrder.value || params.sortOrder || null;
        const typeOverrides = SORT_FIELD_OVERRIDES[typeValue];
        let backendSortBy = (typeOverrides && typeOverrides[effectiveSortField]) || SORT_FIELD_MAP[effectiveSortField] || "";
        if (backendSortBy === "priority" && typeValue === "缺陷") backendSortBy = "severity";
        const backendSortOrder = effectiveSortOrder === "ascend" ? "asc" : effectiveSortOrder === "descend" ? "desc" : "";

        if (useApi.value && (typeValue === "需求" || typeValue === "任务" || typeValue === "缺陷")) {
            const workType = typeValue as WorkItemType;
            const backendStates = statusValues.length
                ? [...new Set(statusValues.flatMap(s => getBackendStatesByDisplayStatus(workType, s as any) || []))]
                : undefined;
            if (statusValues.length && (!backendStates || backendStates.length === 0)) {
                totalCount.value = 0;
                return { data: [], total: 0, current, pageSize };
            }
            const projectIdParam = propProjectId.value || undefined;
            const iterationIdParam = propIterationId.value || undefined;
            const vf = propViewFilters.value || {};
            const viewOwner = vf.owner || undefined;
            const viewCreator = vf.creator || undefined;
            const viewParticipant = vf.participant || undefined;
            const effectiveAssignee = ownerMemberId || viewOwner || undefined;
            const sortParams = backendSortBy ? { sort_by: backendSortBy, sort_order: backendSortOrder } : {};
            const requestByState = async (state?: string, page = current, size = pageSize) => {
                if (workType === "需求") {
                    return getVortflowStories({
                        keyword: kw, state, parent_id: "root",
                        project_id: projectIdParam,
                        iteration_id: iterationIdParam,
                        assignee_id: ownerMemberId || viewOwner || undefined,
                        submitter_id: viewCreator,
                        participant_id: viewParticipant,
                        ...sortParams,
                        page, page_size: size
                    });
                }
                if (workType === "任务") {
                    return getVortflowTasks({
                        keyword: kw,
                        parent_id: "root",
                        state,
                        assignee_id: effectiveAssignee,
                        project_id: projectIdParam,
                        iteration_id: iterationIdParam,
                        creator_id: viewCreator,
                        participant_id: viewParticipant,
                        ...sortParams,
                        page,
                        page_size: size
                    });
                }
                return getVortflowBugs({
                    keyword: kw,
                    state,
                    assignee_id: effectiveAssignee,
                    project_id: projectIdParam,
                    iteration_id: iterationIdParam,
                    reporter_id: viewCreator,
                    participant_id: viewParticipant,
                    ...sortParams,
                    page,
                    page_size: size
                });
            };
            const fetchAllItemsByState = async (state?: string): Promise<any[]> => {
                const batchSize = 100;
                const firstRes: any = await requestByState(state, 1, batchSize);
                const allItems: any[] = [...((firstRes as any)?.items || [])];
                const total = Number((firstRes as any)?.total || allItems.length);
                const totalPages = Math.max(1, Math.ceil(total / batchSize));
                for (let page = 2; page <= totalPages; page++) {
                    const pageRes: any = await requestByState(state, page, batchSize);
                    const pageItems = ((pageRes as any)?.items || []);
                    if (!pageItems.length) break;
                    allItems.push(...pageItems);
                }
                return allItems;
            };
            const buildRowsFromItems = (items: any[]): RowItem[] => {
                const rows = items.map((item: any, idx: number) => mapBackendItemToRow(item, workType, idx));
                if (workType === "需求" || workType === "任务") {
                    cacheItemRows(rows);
                }
                return rows;
            };

            let rows: RowItem[] = [];
            let totalFromApi = 0;

            const hasColumnFilters = Object.keys(columnFilters).some(k => columnFilters[k] != null);
            const needFetchAll = hasColumnFilters
                || (backendStates && backendStates.length > 1)
                || (ownerValue && (workType === "需求" || ownerValue === "未指派" || !ownerMemberId));

            if (needFetchAll) {
                let allItems: any[];
                if (backendStates && backendStates.length > 1) {
                    const merged = new Map<string, any>();
                    const itemGroups = await Promise.all(backendStates.map((state) => fetchAllItemsByState(state)));
                    for (const items of itemGroups) {
                        for (const item of items) {
                            const id = String(item?.id || "");
                            if (!id || merged.has(id)) continue;
                            merged.set(id, item);
                        }
                    }
                    allItems = [...merged.values()];
                } else {
                    allItems = await fetchAllItemsByState(backendStates?.[0]);
                }
                let allRows = buildRowsFromItems(allItems)
                    .filter((x) => !statusValues.length || statusValues.includes(x.status))
                    .filter(matchOwner);

                const isIncompleteView = vf.status === "incomplete";
                if (isIncompleteView) {
                    const completedStatuses: Set<string> = new Set(["已完成", "已关闭", "已取消", "发布完成"]);
                    allRows = allRows.filter((x) => !completedStatuses.has(x.status));
                }

                const optionRows = workType === "需求" || workType === "任务" ? getVisibleChildRows(allRows, ownerValue, statusValues) : allRows;
                collectTagOptions(optionRows);
                collectEnumOptions(optionRows);

                allRows = applyColumnFilters(allRows);
                allRows = applyColumnSort(allRows);
                totalFromApi = allRows.length;

                if (current === 1) {
                    let pinnedRows = pinnedRowsByType[workType] || [];
                    if (statusValues.length) pinnedRows = pinnedRows.filter((x) => statusValues.includes(x.status));
                    if (ownerValue) pinnedRows = pinnedRows.filter(matchOwner);
                    const pinnedIds = new Set(pinnedRows.map((x) => x.backendId || x.workNo));
                    allRows = [...pinnedRows, ...allRows.filter((x) => !pinnedIds.has(x.backendId || x.workNo))];
                    totalFromApi = allRows.length;
                }

                const start = (current - 1) * pageSize;
                rows = allRows.slice(start, start + pageSize);
            } else {
                const backendState = backendStates?.[0];
                const res: any = await requestByState(backendState, current, pageSize);
                rows = buildRowsFromItems((res as any)?.items || []);
                if (statusValues.length) rows = rows.filter((x) => statusValues.includes(x.status));
                if (ownerValue) rows = rows.filter(matchOwner);
                totalFromApi = Number((res as any)?.total || rows.length);

                if (current === 1) {
                    let pinnedRows = pinnedRowsByType[workType] || [];
                    if (statusValues.length) pinnedRows = pinnedRows.filter((x) => statusValues.includes(x.status));
                    if (ownerValue) pinnedRows = pinnedRows.filter(matchOwner);
                    const pinnedIds = new Set(pinnedRows.map((x) => x.backendId || x.workNo));
                    rows = [...pinnedRows, ...rows.filter((x) => !pinnedIds.has(x.backendId || x.workNo))];
                    rows = rows.slice(0, pageSize);
                }
                const isIncompleteView = vf.status === "incomplete";
                if (isIncompleteView) {
                    const completedStatuses: Set<string> = new Set(["已完成", "已关闭", "已取消", "发布完成"]);
                    rows = rows.filter((x) => !completedStatuses.has(x.status));
                    totalFromApi = rows.length;
                }
                rows = applyColumnSort(rows);

                const optionRows = workType === "需求" || workType === "任务" ? getVisibleChildRows(rows, ownerValue, statusValues) : rows;
                collectTagOptions(optionRows);
                collectEnumOptions(optionRows);
            }

            totalCount.value = totalFromApi;
            return { data: rows, total: totalFromApi, current, pageSize };
        }

        totalCount.value = 0;
        return { data: [], total: 0, current, pageSize };
    };

    const postProcessTableRows = (rows: RowItem[]) => getVisibleChildRows(rows);

    const prependPinnedRow = (typeValue: WorkItemType, row: RowItem) => {
        const list = pinnedRowsByType[typeValue] || [];
        const rowId = row.backendId || row.workNo;
        pinnedRowsByType[typeValue] = [row, ...list.filter((x) => (x.backendId || x.workNo) !== rowId)];
    };

    return {
        SORT_FIELD_MAP,
        SORT_FIELD_OVERRIDES,
        mapBackendItemToRow,
        createOwnerMatcher,
        cacheItemRows,
        findItemRowById,
        findItemRowByIdentifier,
        loadItemById,
        loadChildItems,
        getVisibleChildRows,
        applyColumnFilters,
        applyColumnSort,
        request,
        postProcessTableRows,
        prependPinnedRow,
    };
}
