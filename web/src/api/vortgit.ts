import request from "@/utils/request";

// ---- Providers ----

export function getVortgitProviders() {
    return request.get("/vortgit/providers", {
        params: { _t: Date.now() }
    });
}

export function getVortgitProvider(id: string) {
    return request.get(`/vortgit/providers/${id}`);
}

export function createVortgitProvider(data: { name: string; platform: string; api_base?: string; access_token?: string; is_default?: boolean }) {
    return request.post("/vortgit/providers", data);
}

export function updateVortgitProvider(id: string, data: { name?: string; platform?: string; api_base?: string; access_token?: string; is_default?: boolean }) {
    return request.put(`/vortgit/providers/${id}`, data);
}

export function deleteVortgitProvider(id: string) {
    return request.delete(`/vortgit/providers/${id}`);
}

export function getVortgitRemoteRepos(providerId: string, params: { page?: number; per_page?: number; search?: string }) {
    return request.get(`/vortgit/providers/${providerId}/remote-repos`, { params });
}

// ---- Repos ----

export function getVortgitRepos(params: { provider_id?: string; project_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortgit/repos", { params });
}

export function getVortgitRepo(id: string) {
    return request.get(`/vortgit/repos/${id}`);
}

export function createVortgitRepo(data: { provider_id: string; name: string; full_name: string; clone_url?: string; ssh_url?: string; default_branch?: string; description?: string; language?: string; repo_type?: string; is_private?: boolean; project_id?: string }) {
    return request.post("/vortgit/repos", data);
}

export function updateVortgitRepo(id: string, data: { name?: string; description?: string; repo_type?: string; project_id?: string; default_branch?: string }) {
    return request.put(`/vortgit/repos/${id}`, data);
}

export function deleteVortgitRepo(id: string) {
    return request.delete(`/vortgit/repos/${id}`);
}

export function importVortgitRepos(data: { provider_id: string; repos: { full_name: string; project_id?: string; repo_type?: string }[] }) {
    return request.post("/vortgit/repos/import", data);
}

export function syncVortgitRepo(id: string) {
    return request.post(`/vortgit/repos/${id}/sync`);
}

export function getVortgitRepoCommits(id: string, params: { branch?: string; since?: string; until?: string; author?: string; page?: number; per_page?: number }) {
    return request.get(`/vortgit/repos/${id}/commits`, { params });
}

export function getVortgitRepoBranches(id: string) {
    return request.get(`/vortgit/repos/${id}/branches`);
}

// ---- Repo Members ----

export function getVortgitRepoMembers(repoId: string) {
    return request.get(`/vortgit/repos/${repoId}/members`);
}

export function addVortgitRepoMember(repoId: string, data: { member_id: string; access_level?: string; platform_username?: string }) {
    return request.post(`/vortgit/repos/${repoId}/members`, data);
}

export function removeVortgitRepoMember(repoId: string, memberId: string) {
    return request.delete(`/vortgit/repos/${repoId}/members/${memberId}`);
}

// ---- Code Tasks ----

export function getVortgitCodeTasks(params: { status?: string; repo_id?: string; member_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortgit/code-tasks", { params });
}

export function getVortgitCodeTask(id: string) {
    return request.get(`/vortgit/code-tasks/${id}`);
}

export function getVortgitCodeTaskStats() {
    return request.get("/vortgit/code-tasks/stats");
}

export function deleteVortgitCodeTask(id: string) {
    return request.delete(`/vortgit/code-tasks/${id}`);
}

export function batchDeleteVortgitCodeTasks(ids: string[]) {
    return request.post("/vortgit/code-tasks/batch-delete", { ids });
}

export function getVortgitCodingEnvStatus() {
    return request.get("/vortgit/coding-env/status");
}
