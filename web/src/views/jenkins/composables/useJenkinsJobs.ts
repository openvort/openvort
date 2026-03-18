import { ref, computed } from "vue";
import { getJenkinsJobs, getJenkinsSystemInfo, getJenkinsJobInfo } from "@/api/jenkins";
import type { JenkinsJob, JenkinsView, JenkinsJobDetail } from "../types";

export type LoadResult = "ok" | "auth_error" | "error";

function isJenkinsAuthError(err: any): boolean {
    const status = err?.response?.status;
    const detail: string = err?.response?.data?.detail || "";
    if (status === 401) return true;
    if (status === 422 && (detail.includes("认证失败") || detail.includes("凭证未配置"))) return true;
    return false;
}

export function useJenkinsJobs() {
    const jobs = ref<JenkinsJob[]>([]);
    const views = ref<JenkinsView[]>([]);
    const activeView = ref("All");
    const folderPath = ref<string[]>([]);
    const loading = ref(false);
    const keyword = ref("");

    const currentFolder = computed(() => folderPath.value.join("/"));

    const breadcrumbs = computed(() => {
        const items: { label: string; path: string[] }[] = [{ label: "Jenkins", path: [] }];
        folderPath.value.forEach((segment, idx) => {
            items.push({ label: segment, path: folderPath.value.slice(0, idx + 1) });
        });
        return items;
    });

    async function loadViews(instanceId: string, silent = false): Promise<LoadResult> {
        try {
            const config = silent ? { skipErrorMessage: true } : undefined;
            const res: any = await getJenkinsSystemInfo(instanceId, config);
            views.value = res.views || [];
            if (views.value.length > 0 && !views.value.find((v) => v.name === activeView.value)) {
                activeView.value = views.value[0]?.name || "All";
            }
            return "ok";
        } catch (err) {
            views.value = [];
            return isJenkinsAuthError(err) ? "auth_error" : "error";
        }
    }

    async function loadJobs(instanceId: string, silent = false): Promise<LoadResult> {
        loading.value = true;
        try {
            const params: Record<string, any> = {
                include_folders: true,
                recursive: false,
                limit: 200,
            };
            if (currentFolder.value) {
                params.folder = currentFolder.value;
            } else if (activeView.value && activeView.value !== "All") {
                params.view = activeView.value;
            }
            if (keyword.value.trim()) {
                params.keyword = keyword.value.trim();
            }
            const config = silent ? { skipErrorMessage: true } : undefined;
            const res: any = await getJenkinsJobs(instanceId, params, config);
            jobs.value = res.jobs || [];
            return "ok";
        } catch (err) {
            jobs.value = [];
            return isJenkinsAuthError(err) ? "auth_error" : "error";
        } finally {
            loading.value = false;
        }
    }

    function enterFolder(folderName: string) {
        if (currentFolder.value) {
            folderPath.value = [...folderPath.value, folderName];
        } else {
            folderPath.value = [folderName];
        }
    }

    function navigateBreadcrumb(path: string[]) {
        folderPath.value = [...path];
    }

    function switchView(viewName: string) {
        activeView.value = viewName;
        folderPath.value = [];
    }

    function resetNavigation() {
        jobs.value = [];
        views.value = [];
        folderPath.value = [];
        activeView.value = "All";
        keyword.value = "";
    }

    // Job detail
    const jobDetail = ref<JenkinsJobDetail | null>(null);
    const jobDetailLoading = ref(false);

    async function loadJobDetail(instanceId: string, jobName: string) {
        jobDetailLoading.value = true;
        try {
            const res: any = await getJenkinsJobInfo(instanceId, jobName);
            jobDetail.value = res.job || null;
        } catch {
            jobDetail.value = null;
        } finally {
            jobDetailLoading.value = false;
        }
    }

    return {
        jobs,
        views,
        activeView,
        folderPath,
        currentFolder,
        breadcrumbs,
        loading,
        keyword,
        loadViews,
        loadJobs,
        enterFolder,
        navigateBreadcrumb,
        switchView,
        resetNavigation,
        jobDetail,
        jobDetailLoading,
        loadJobDetail,
    };
}
