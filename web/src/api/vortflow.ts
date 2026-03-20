import request from "@/utils/request";

// ---- Dashboard ----

export function getVortflowStats(project_id?: string) {
    return request.get("/vortflow/dashboard/stats", { params: project_id ? { project_id } : {} });
}

// ---- Projects ----

export function getVortflowProjects() {
    return request.get("/vortflow/projects");
}

export function getVortflowProject(id: string) {
    return request.get(`/vortflow/projects/${id}`);
}

export function createVortflowProject(data: { name: string; description?: string; product?: string; iteration?: string; version?: string; start_date?: string; end_date?: string }) {
    return request.post("/vortflow/projects", data);
}

export function updateVortflowProject(id: string, data: { name?: string; description?: string; product?: string; iteration?: string; version?: string; start_date?: string; end_date?: string }) {
    return request.put(`/vortflow/projects/${id}`, data);
}

export function deleteVortflowProject(id: string) {
    return request.delete(`/vortflow/projects/${id}`);
}

export function getVortflowProjectMembers(projectId: string) {
    return request.get(`/vortflow/projects/${projectId}/members`);
}

export function addVortflowProjectMember(projectId: string, data: { member_id: string; role?: string }) {
    return request.post(`/vortflow/projects/${projectId}/members`, data);
}

export function removeVortflowProjectMember(projectId: string, memberId: string) {
    return request.delete(`/vortflow/projects/${projectId}/members/${memberId}`);
}

// ---- Stories ----

export function getVortflowStories(params: { project_id?: string; state?: string; keyword?: string; priority?: number; parent_id?: string; submitter_id?: string; pm_id?: string; participant_id?: string; iteration_id?: string; sort_by?: string; sort_order?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/stories", { params });
}

export function getVortflowStory(id: string) {
    return request.get(`/vortflow/stories/${id}`);
}

export function createVortflowStory(data: { project_id: string; title: string; description?: string; priority?: number; parent_id?: string; tags?: string[]; collaborators?: string[]; deadline?: string }) {
    return request.post("/vortflow/stories", data);
}

export function updateVortflowStory(id: string, data: {
    title?: string;
    description?: string;
    state?: string;
    priority?: number;
    parent_id?: string | null;
    tags?: string[];
    collaborators?: string[];
    deadline?: string;
    pm_id?: string | null;
    project_id?: string | null;
    start_at?: string;
    end_at?: string;
    repo_id?: string | null;
    branch?: string;
}) {
    return request.put(`/vortflow/stories/${id}`, data);
}

export function deleteVortflowStory(id: string) {
    return request.delete(`/vortflow/stories/${id}`);
}

export function transitionVortflowStory(id: string, target_state: string) {
    return request.post(`/vortflow/stories/${id}/transition`, { target_state });
}

export function getVortflowStoryTransitions(id: string) {
    return request.get(`/vortflow/stories/${id}/transitions`);
}

// ---- Tasks ----

export function getVortflowTasks(params: { story_id?: string; parent_id?: string; state?: string; task_type?: string; assignee_id?: string; keyword?: string; project_id?: string; creator_id?: string; participant_id?: string; iteration_id?: string; sort_by?: string; sort_order?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/tasks", { params });
}

export function getVortflowTask(id: string) {
    return request.get(`/vortflow/tasks/${id}`);
}

export function createVortflowTask(data: { project_id?: string; story_id?: string; parent_id?: string; title: string; description?: string; task_type?: string; assignee_id?: string; tags?: string[]; collaborators?: string[]; estimate_hours?: number; deadline?: string }) {
    return request.post("/vortflow/tasks", data);
}

export function updateVortflowTask(id: string, data: {
    project_id?: string | null;
    title?: string;
    description?: string;
    task_type?: string;
    state?: string;
    assignee_id?: string;
    tags?: string[];
    collaborators?: string[];
    estimate_hours?: number;
    actual_hours?: number;
    deadline?: string;
    start_at?: string;
    end_at?: string;
    repo_id?: string | null;
    branch?: string;
}) {
    return request.put(`/vortflow/tasks/${id}`, data);
}

export function deleteVortflowTask(id: string) {
    return request.delete(`/vortflow/tasks/${id}`);
}

export function transitionVortflowTask(id: string, target_state: string) {
    return request.post(`/vortflow/tasks/${id}/transition`, { target_state });
}

export function getVortflowTaskTransitions(id: string) {
    return request.get(`/vortflow/tasks/${id}/transitions`);
}

// ---- Bugs ----

export function getVortflowBugs(params: { story_id?: string; state?: string; severity?: number; assignee_id?: string; keyword?: string; project_id?: string; reporter_id?: string; participant_id?: string; iteration_id?: string; sort_by?: string; sort_order?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/bugs", { params });
}

export function getVortflowBug(id: string) {
    return request.get(`/vortflow/bugs/${id}`);
}

export function createVortflowBug(data: { project_id?: string; story_id?: string; task_id?: string; title: string; description?: string; severity?: number; assignee_id?: string; tags?: string[]; collaborators?: string[] }) {
    return request.post("/vortflow/bugs", data);
}

export function updateVortflowBug(id: string, data: {
    project_id?: string | null;
    title?: string;
    description?: string;
    severity?: number;
    state?: string;
    assignee_id?: string;
    tags?: string[];
    collaborators?: string[];
    estimate_hours?: number;
    actual_hours?: number;
    deadline?: string;
    start_at?: string;
    end_at?: string;
    repo_id?: string | null;
    branch?: string;
}) {
    return request.put(`/vortflow/bugs/${id}`, data);
}

export function deleteVortflowBug(id: string) {
    return request.delete(`/vortflow/bugs/${id}`);
}

export function transitionVortflowBug(id: string, target_state: string) {
    return request.post(`/vortflow/bugs/${id}/transition`, { target_state });
}

export function getVortflowBugTransitions(id: string) {
    return request.get(`/vortflow/bugs/${id}/transitions`);
}

// ---- Work Item Links ----

export function getVortflowWorkItemLinks(params: { entity_type: string; entity_id: string }) {
    return request.get("/vortflow/work-item-links", { params });
}

export function createVortflowWorkItemLink(data: { source_type: string; source_id: string; target_type: string; target_id: string }) {
    return request.post("/vortflow/work-item-links", data);
}

export function deleteVortflowWorkItemLink(linkId: string) {
    return request.delete(`/vortflow/work-item-links/${linkId}`);
}

// ---- Milestones ----

export function getVortflowMilestones(params: { project_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/milestones", { params });
}

export function getVortflowMilestone(id: string) {
    return request.get(`/vortflow/milestones/${id}`);
}

export function createVortflowMilestone(data: { project_id: string; name: string; description?: string; due_date?: string; story_id?: string }) {
    return request.post("/vortflow/milestones", data);
}

export function updateVortflowMilestone(id: string, data: { name?: string; description?: string; due_date?: string; completed_at?: string }) {
    return request.put(`/vortflow/milestones/${id}`, data);
}

export function deleteVortflowMilestone(id: string) {
    return request.delete(`/vortflow/milestones/${id}`);
}

export function completeVortflowMilestone(id: string) {
    return request.post(`/vortflow/milestones/${id}/complete`);
}

// ---- Events ----

export function getVortflowEvents(params: { entity_type?: string; entity_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/events", { params });
}

export function generateVortflowDescriptionPrompt(entityType: string, projectName: string, title: string) {
    return request.get("/vortflow/generate-description-prompt", {
        params: { entity_type: entityType, project_name: projectName, title },
    });
}

// ---- Iterations ----

export function getVortflowIterations(params: { project_id?: string; status?: string; keyword?: string; owner_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/iterations", { params });
}

export function getVortflowIteration(id: string) {
    return request.get(`/vortflow/iterations/${id}`);
}

export function createVortflowIteration(data: {
    project_id: string;
    name: string;
    goal?: string;
    owner_id?: string;
    start_date?: string;
    end_date?: string;
    status?: string;
    estimate_hours?: number;
}) {
    return request.post("/vortflow/iterations", data);
}

export function updateVortflowIteration(id: string, data: {
    name?: string;
    goal?: string;
    owner_id?: string;
    start_date?: string;
    end_date?: string;
    status?: string;
    estimate_hours?: number;
}) {
    return request.put(`/vortflow/iterations/${id}`, data);
}

export function deleteVortflowIteration(id: string) {
    return request.delete(`/vortflow/iterations/${id}`);
}

export function getVortflowIterationStories(iterationId: string) {
    return request.get(`/vortflow/iterations/${iterationId}/stories`);
}

export function addVortflowIterationStory(iterationId: string, data: { story_id: string; story_order?: number }) {
    return request.post(`/vortflow/iterations/${iterationId}/stories`, data);
}

export function removeVortflowIterationStory(iterationId: string, storyId: string) {
    return request.delete(`/vortflow/iterations/${iterationId}/stories/${storyId}`);
}

export function getVortflowIterationTasks(iterationId: string) {
    return request.get(`/vortflow/iterations/${iterationId}/tasks`);
}

export function addVortflowIterationTask(iterationId: string, data: { task_id: string; task_order?: number }) {
    return request.post(`/vortflow/iterations/${iterationId}/tasks`, data);
}

export function removeVortflowIterationTask(iterationId: string, taskId: string) {
    return request.delete(`/vortflow/iterations/${iterationId}/tasks/${taskId}`);
}

export function addVortflowIterationBug(iterationId: string, data: { bug_id: string; bug_order?: number }) {
    return request.post(`/vortflow/iterations/${iterationId}/bugs`, data);
}

export function removeVortflowIterationBug(iterationId: string, bugId: string) {
    return request.delete(`/vortflow/iterations/${iterationId}/bugs/${bugId}`);
}

// ---- Versions ----

export function getVortflowVersions(params: { project_id?: string; status?: string; keyword?: string; owner_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/versions", { params });
}

export function getVortflowVersion(id: string) {
    return request.get(`/vortflow/versions/${id}`);
}

export function createVortflowVersion(data: {
    project_id: string;
    name: string;
    description?: string;
    owner_id?: string;
    planned_release_at?: string;
    actual_release_at?: string;
    progress?: number;
    release_date?: string;
    status?: string;
    release_log?: string;
}) {
    return request.post("/vortflow/versions", data);
}

export function updateVortflowVersion(id: string, data: {
    name?: string;
    description?: string;
    owner_id?: string;
    planned_release_at?: string;
    actual_release_at?: string;
    progress?: number;
    release_date?: string;
    status?: string;
    release_log?: string;
}) {
    return request.put(`/vortflow/versions/${id}`, data);
}

export function deleteVortflowVersion(id: string) {
    return request.delete(`/vortflow/versions/${id}`);
}

export function releaseVortflowVersion(id: string) {
    return request.post(`/vortflow/versions/${id}/release`);
}

export function getVortflowVersionStories(versionId: string) {
    return request.get(`/vortflow/versions/${versionId}/stories`);
}

export function addVortflowVersionStory(versionId: string, data: { story_id: string; added_reason?: string; story_order?: number }) {
    return request.post(`/vortflow/versions/${versionId}/stories`, data);
}

export function removeVortflowVersionStory(versionId: string, storyId: string) {
    return request.delete(`/vortflow/versions/${versionId}/stories/${storyId}`);
}

export function addVortflowVersionBug(versionId: string, data: { bug_id: string; bug_order?: number }) {
    return request.post(`/vortflow/versions/${versionId}/bugs`, data);
}

export function removeVortflowVersionBug(versionId: string, bugId: string) {
    return request.delete(`/vortflow/versions/${versionId}/bugs/${bugId}`);
}

// ---- Comments & Activity ----

export function getVortflowComments(entityType: string, entityId: string) {
    return request.get(`/vortflow/comments/${entityType}/${entityId}`);
}

export function createVortflowComment(entityType: string, entityId: string, data: { content: string; mentions?: string[] }) {
    return request.post(`/vortflow/comments/${entityType}/${entityId}`, data);
}

export function getVortflowActivity(entityType: string, entityId: string, params?: { page?: number; page_size?: number }) {
    return request.get(`/vortflow/activity/${entityType}/${entityId}`, { params });
}

// ---- Views & Column Settings ----

export function getVortflowViews(work_item_type?: string) {
    return request.get("/vortflow/views", { params: { work_item_type: work_item_type || "" } });
}

export function createVortflowView(data: { name: string; work_item_type: string; scope?: string; filters?: Record<string, any>; columns?: Array<{ key: string; visible: boolean }> }) {
    return request.post("/vortflow/views", data);
}

export function updateVortflowView(id: string, data: { name?: string; filters?: Record<string, any>; columns?: Array<{ key: string; visible: boolean }>; view_order?: number }) {
    return request.put(`/vortflow/views/${id}`, data);
}

export function deleteVortflowView(id: string) {
    return request.delete(`/vortflow/views/${id}`);
}

export function getVortflowColumnSettings(work_item_type?: string) {
    return request.get("/vortflow/column-settings", { params: { work_item_type: work_item_type || "" } });
}

export function saveVortflowColumnSettings(data: { work_item_type: string; columns: Array<{ key: string; visible: boolean }> }) {
    return request.put("/vortflow/column-settings", data);
}

// ---- Tags ----

export function getVortflowTags() {
    return request.get("/vortflow/tags");
}

export function createVortflowTag(data: { name: string; color?: string }) {
    return request.post("/vortflow/tags", data);
}

export function updateVortflowTag(id: string, data: { name?: string; color?: string }) {
    return request.put(`/vortflow/tags/${id}`, data);
}

export function deleteVortflowTag(id: string) {
    return request.delete(`/vortflow/tags/${id}`);
}

export function reorderVortflowTags(ids: string[]) {
    return request.post("/vortflow/tags/reorder", { ids });
}

export function migrateVortflowTag(id: string, data: { target_tag_id?: string | null }) {
    return request.post(`/vortflow/tags/${id}/migrate`, data);
}

// ---- Statuses ----

export function getVortflowStatuses(params?: { keyword?: string }) {
    return request.get("/vortflow/statuses", { params });
}

export function createVortflowStatus(data: { name: string; icon?: string; icon_color?: string; command?: string; work_item_types?: string[] }) {
    return request.post("/vortflow/statuses", data);
}

export function updateVortflowStatus(id: string, data: { name?: string; icon?: string; icon_color?: string; command?: string; work_item_types?: string[] }) {
    return request.put(`/vortflow/statuses/${id}`, data);
}

export function deleteVortflowStatus(id: string) {
    return request.delete(`/vortflow/statuses/${id}`);
}

// ---- Test Modules ----

export function getVortflowTestModules(params?: { project_id?: string }) {
    return request.get("/vortflow/test-modules", { params });
}

export function createVortflowTestModule(data: { project_id: string; parent_id?: string | null; name: string }) {
    return request.post("/vortflow/test-modules", data);
}

export function updateVortflowTestModule(id: string, data: { name?: string; parent_id?: string | null; sort_order?: number }) {
    return request.put(`/vortflow/test-modules/${id}`, data);
}

export function deleteVortflowTestModule(id: string) {
    return request.delete(`/vortflow/test-modules/${id}`);
}

// ---- Test Cases ----

export function getVortflowTestCases(params?: {
    project_id?: string;
    module_id?: string;
    keyword?: string;
    case_type?: string;
    priority?: number;
    review_result?: string;
    maintainer_id?: string;
    page?: number;
    page_size?: number;
}) {
    return request.get("/vortflow/test-cases", { params });
}

export function getVortflowTestCase(id: string) {
    return request.get(`/vortflow/test-cases/${id}`);
}

export function createVortflowTestCase(data: {
    project_id: string;
    module_id?: string | null;
    title: string;
    precondition?: string;
    notes?: string;
    case_type?: string;
    priority?: number;
    maintainer_id?: string | null;
    steps?: { order: number; description: string; expected_result: string }[];
}) {
    return request.post("/vortflow/test-cases", data);
}

export function updateVortflowTestCase(id: string, data: {
    module_id?: string | null;
    title?: string;
    precondition?: string;
    notes?: string;
    case_type?: string;
    priority?: number;
    maintainer_id?: string | null;
    review_result?: string;
    steps?: { order: number; description: string; expected_result: string }[];
}) {
    return request.put(`/vortflow/test-cases/${id}`, data);
}

export function deleteVortflowTestCase(id: string) {
    return request.delete(`/vortflow/test-cases/${id}`);
}

// ---- Test Case Links ----

export function getVortflowTestCaseLinks(params: {
    test_case_id?: string;
    entity_type?: string;
    entity_id?: string;
}) {
    return request.get("/vortflow/test-case-links", { params });
}

export function createVortflowTestCaseLink(data: {
    test_case_id: string;
    entity_type: string;
    entity_id: string;
}) {
    return request.post("/vortflow/test-case-links", data);
}

export function deleteVortflowTestCaseLink(linkId: string) {
    return request.delete(`/vortflow/test-case-links/${linkId}`);
}
