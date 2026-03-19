import request from "@/utils/request";

// Per-instance credential
export function getJenkinsInstanceCredential(instanceId: string) {
    return request.get(`/jenkins/instances/${instanceId}/credential`);
}

export function saveJenkinsInstanceCredential(instanceId: string, data: { username: string; api_token: string }) {
    return request.put(`/jenkins/instances/${instanceId}/credential`, data);
}

export function deleteJenkinsInstanceCredential(instanceId: string) {
    return request.delete(`/jenkins/instances/${instanceId}/credential`);
}

// View management
export function createJenkinsView(instanceId: string, data: { name: string; include_regex?: string }) {
    return request.post(`/jenkins/instances/${instanceId}/views`, data);
}

export function deleteJenkinsView(instanceId: string, viewName: string) {
    return request.delete(`/jenkins/instances/${instanceId}/views/${encodeURIComponent(viewName)}`);
}

// Instance CRUD
export function getJenkinsInstances() {
    return request.get("/jenkins/instances");
}

export function createJenkinsInstance(data: { name: string; url: string; verify_ssl?: boolean; is_default?: boolean }) {
    return request.post("/jenkins/instances", data);
}

export function updateJenkinsInstance(id: string, data: { name?: string; url?: string; verify_ssl?: boolean; is_default?: boolean }) {
    return request.put(`/jenkins/instances/${id}`, data);
}

export function deleteJenkinsInstance(id: string) {
    return request.delete(`/jenkins/instances/${id}`);
}

// Build status (queue & executors)
export function getJenkinsQueue(id: string) {
    return request.get(`/jenkins/instances/${id}/queue`);
}

export function getJenkinsExecutors(id: string) {
    return request.get(`/jenkins/instances/${id}/executors`);
}

// Jenkins operations
export function verifyJenkinsInstance(id: string) {
    return request.post(`/jenkins/instances/${id}/verify`);
}

export function getJenkinsSystemInfo(id: string, config?: Record<string, any>) {
    return request.get(`/jenkins/instances/${id}/system`, config);
}

export function getJenkinsJobs(id: string, params: { view?: string; folder?: string; keyword?: string; recursive?: boolean; include_folders?: boolean; limit?: number } = {}, config?: Record<string, any>) {
    return request.get(`/jenkins/instances/${id}/jobs`, { params, ...config });
}

export function getJenkinsJobInfo(id: string, jobName: string) {
    return request.get(`/jenkins/instances/${id}/jobs/info`, { params: { job_name: jobName } });
}

export function getJenkinsJobConfigSummary(id: string, jobName: string) {
    return request.get(`/jenkins/instances/${id}/jobs/config-summary`, { params: { job_name: jobName } });
}

export function triggerJenkinsBuild(id: string, data: { job_name: string; parameters?: Record<string, any> }) {
    return request.post(`/jenkins/instances/${id}/jobs/build`, data);
}

export function abortJenkinsBuild(id: string, jobName: string, buildNumber: number) {
    return request.post(`/jenkins/instances/${id}/builds/abort`, null, { params: { job_name: jobName, build_number: buildNumber } });
}

export function getJenkinsBuildStatus(id: string, jobName: string, buildNumber: number) {
    return request.get(`/jenkins/instances/${id}/builds/status`, { params: { job_name: jobName, build_number: buildNumber } });
}

export function getJenkinsBuildLog(id: string, jobName: string, buildNumber: number, tailLines: number = 200) {
    return request.get(`/jenkins/instances/${id}/builds/log`, { params: { job_name: jobName, build_number: buildNumber, tail_lines: tailLines } });
}
