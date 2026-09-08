import request from "@/utils/request";

export interface AutodevProjectConfig {
    id: string;
    project_id: string;
    repo_path: string;
    jira_project_key: string;
    sync_jql: string;
    sync_max_results: number;
    last_synced_at: string | null;
    deliver: boolean;
    enabled: boolean;
    paused: boolean;
    last_dispatched_at: string | null;
    hcm_base_url: string;
    hcm_username: string;
    hcm_password: string;
    env: Record<string, string>;
    updated_at: string | null;
}

export interface AutodevRun {
    id: string;
    issue_key: string;
    story_id: string;
    status: string;
    trigger: string;
    exit_code: number | null;
    exit_meaning: string;
    outcome: string;
    verdict: string;
    branch: string;
    mr_url: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    calls: number;
    duration_ms: number;
    cost: number;
    error: string;
    started_at: string | null;
    finished_at: string | null;
}

export interface AutodevQueueItem {
    story_id: string;
    key: string;
    title: string;
    priority: number;
    running: boolean;
}

export function getAutodevProject(projectId: string) {
    return request.get(`/autodev/projects/${projectId}`, { params: { _t: Date.now() } });
}

export function saveAutodevProject(projectId: string, data: Partial<AutodevProjectConfig>) {
    return request.put(`/autodev/projects/${projectId}`, data);
}

export function pauseAutodevProject(projectId: string) {
    return request.post(`/autodev/projects/${projectId}/pause`);
}

export function resumeAutodevProject(projectId: string) {
    return request.post(`/autodev/projects/${projectId}/resume`);
}

export function getAutodevQueue(projectId: string) {
    return request.get(`/autodev/projects/${projectId}/queue`, { params: { _t: Date.now() } });
}

export function syncAutodevProject(projectId: string) {
    return request.post(`/autodev/projects/${projectId}/sync`, {}, { timeout: 180000 });
}

export function dispatchAutodev(projectId: string, issueKey = "", maxStarts = 1) {
    return request.post(`/autodev/projects/${projectId}/dispatch`, { issue_key: issueKey, max_starts: maxStarts },
        { timeout: 60000 });
}

export function getAutodevRuns(projectId: string, limit = 50) {
    return request.get(`/autodev/projects/${projectId}/runs`, { params: { limit, _t: Date.now() } });
}

export function getAutodevStats(projectId: string, days = 7) {
    return request.get(`/autodev/projects/${projectId}/stats`, { params: { days, _t: Date.now() } });
}

export function getAutodevGlobal() {
    return request.get("/autodev/global", { params: { _t: Date.now() } });
}

export function setAutodevGlobalJob(action: "autodev_dispatch" | "autodev_sync", enabled: boolean, intervalSeconds?: number) {
    return request.put(`/autodev/global/${action}`, { enabled, interval_seconds: intervalSeconds });
}

export function getAutodevExitCodes() {
    return request.get("/autodev/exit-codes");
}
