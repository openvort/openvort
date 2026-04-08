import { computed } from "vue";
import { useVortFlowStore } from "@/stores";
import { useUserStore } from "@/stores";
import type { WorkItemType, ViewFilters } from "@/components/vort-biz/work-item/WorkItemTable.types";

export type { ViewFilters };

export interface VortFlowView {
    id: string;
    name: string;
    scope: "system" | "shared" | "personal";
    getFilters: (currentUserId: string) => ViewFilters;
}

export const SYSTEM_VIEWS: VortFlowView[] = [
    {
        id: "incomplete",
        name: "未完成工作项",
        scope: "shared",
        getFilters: () => ({ status: "incomplete" }),
    },
    {
        id: "all",
        name: "全部工作项",
        scope: "system",
        getFilters: () => ({}),
    },
    {
        id: "my_assigned",
        name: "我负责的",
        scope: "system",
        getFilters: (userId) => ({ owner: userId }),
    },
    {
        id: "my_created",
        name: "我创建的",
        scope: "system",
        getFilters: (userId) => ({ creator: userId }),
    },
    {
        id: "my_participated",
        name: "我参与的",
        scope: "system",
        getFilters: (userId) => ({ participant: userId }),
    },
    {
        id: "parent_only",
        name: "父级工作项",
        scope: "system",
        getFilters: () => ({ parentOnly: true }),
    },
];

export function useVortFlowViews(type: WorkItemType) {
    const store = useVortFlowStore();
    const userStore = useUserStore();

    const currentViewId = computed(() => store.getViewId(type));

    const allViews = computed<VortFlowView[]>(() => {
        const custom: VortFlowView[] = store.customViews
            .filter(v => v.visible)
            .sort((a, b) => a.order - b.order)
            .map(v => ({
                id: v.id,
                name: v.name,
                scope: v.scope,
                // Custom views restore their saved toolbar/column state in WorkItemTable.
                // They should not inject the same snapshot into request-time view filters again.
                getFilters: () => ({}),
            }));
        return [...SYSTEM_VIEWS, ...custom];
    });

    const currentView = computed(() =>
        allViews.value.find(v => v.id === currentViewId.value) ?? SYSTEM_VIEWS[1]!
    );

    const activeViewFilters = computed<ViewFilters>(() => {
        const userId = userStore.userInfo.member_id;
        return currentView.value.getFilters(userId);
    });

    const setView = (viewId: string) => {
        store.setViewId(type, viewId);
    };

    return {
        views: allViews,
        currentViewId,
        currentView,
        activeViewFilters,
        setView,
    };
}
