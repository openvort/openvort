import request from "@/utils/request";

// ---- Admin Skills ----

export function getSkillTags() {
    return request.get("/admin/skills/tags");
}

export function getSkills(params?: { skill_type?: string; tag?: string }) {
    return request.get("/admin/skills", { params });
}

export function getSkill(id: string) {
    return request.get(`/admin/skills/${id}`);
}

export function createSkill(data: { name: string; description?: string; content?: string; skill_type?: string; tags?: string[] }) {
    return request.post("/admin/skills", data);
}

export function updateSkill(id: string, data: { name?: string; description?: string; content?: string; skill_type?: string; tags?: string[] }) {
    return request.put(`/admin/skills/${id}`, data);
}

export function deleteSkill(id: string) {
    return request.delete(`/admin/skills/${id}`);
}

export function toggleSkill(id: string) {
    return request.post(`/admin/skills/${id}/toggle`);
}

export function getSkillDirectories() {
    return request.get("/admin/skills/directories");
}

export function generateSkillContentPrompt(skillId: string) {
    return request.get(`/admin/skills/${skillId}/generate-content-prompt`);
}

// ---- Member Skills ----

export function getMemberSkills(memberId: string) {
    return request.get(`/skills/member/${memberId}`);
}

export function createPersonalSkill(memberId: string, data: { name: string; description?: string; content?: string }) {
    return request.post(`/skills/member/${memberId}/personal`, data);
}

export function updatePersonalSkill(skillId: string, data: { name?: string; description?: string; content?: string }) {
    return request.put(`/skills/personal/${skillId}`, data);
}

export function deletePersonalSkill(skillId: string) {
    return request.delete(`/skills/personal/${skillId}`);
}

export function getPublicSkills() {
    return request.get("/skills/public");
}

export function subscribeMemberSkill(memberId: string, skillId: string) {
    return request.post(`/skills/member/${memberId}/subscribe/${skillId}`);
}

export function unsubscribeMemberSkill(memberId: string, skillId: string) {
    return request.delete(`/skills/member/${memberId}/subscribe/${skillId}`);
}

export function updateMemberBio(memberId: string, bio: string) {
    return request.put(`/skills/member/${memberId}/bio`, { bio });
}

export function generateMemberBioPrompt(memberId: string) {
    return request.get(`/skills/member/${memberId}/generate-bio-prompt`);
}
