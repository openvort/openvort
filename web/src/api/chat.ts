import request from "@/utils/request";

export function getChatHistory(sessionId = "default", limit = 20, offset = 0) {
    return request.get("/chat/history", { params: { limit, offset, session_id: sessionId } });
}

export function sendChatMessage(
    content: string,
    images: { data: string; media_type: string }[] = [],
    sessionId = "default",
    targetType = "ai",
    targetId = ""
) {
    return request.post("/chat/send", { content, images, session_id: sessionId, target_type: targetType, target_id: targetId });
}

export function getChatStreamUrl(messageId: string, token: string) {
    return `/api/chat/stream/${messageId}?token=${encodeURIComponent(token)}`;
}

export function abortChatMessage(messageId: string) {
    return request.post("/chat/abort", { message_id: messageId });
}

export function getChatSessionInfo(sessionId = "default") {
    return request.get("/chat/session-info", { params: { session_id: sessionId } });
}

export function setChatThinking(level: string, sessionId = "default") {
    return request.post("/chat/thinking", { level, session_id: sessionId });
}

export function compactChatSession(sessionId = "default") {
    return request.post("/chat/compact", { session_id: sessionId });
}

export function resetChatSession(sessionId = "default") {
    return request.post("/chat/reset", { session_id: sessionId });
}

export function clearChatHistory(sessionId = "default") {
    return request.post("/chat/clear-history", { session_id: sessionId });
}

export function restoreChatContext(sessionId = "default") {
    return request.post("/chat/restore-context", { session_id: sessionId });
}

export function getChatMembers(keyword = "", limit = 20) {
    return request.get("/chat/members", { params: { keyword, limit } });
}

export function getChatSessions(targetType = "", limit = 20, offset = 0) {
    return request.get("/chat/sessions", { params: { target_type: targetType, limit, offset } });
}

export function createChatSession(title = "新对话", targetType = "ai", targetId = "") {
    return request.post("/chat/sessions", { title, target_type: targetType, target_id: targetId });
}

export function renameChatSession(sessionId: string, title: string) {
    return request.put(`/chat/sessions/${sessionId}`, { title });
}

export function deleteChatSession(sessionId: string) {
    return request.delete(`/chat/sessions/${sessionId}`);
}

export function batchDeleteChatSessions(sessionIds: string[]) {
    return request.post("/chat/sessions/batch-delete", { session_ids: sessionIds });
}

export function getChatContacts() {
    return request.get("/chat/contacts");
}

export function startMemberChat(memberId: string) {
    return request.post("/chat/contacts/start", { member_id: memberId });
}

export function togglePinContact(sessionId: string, pinned: boolean) {
    return request.put(`/chat/contacts/${sessionId}/pin`, { pinned });
}

export function hideChatContact(sessionId: string) {
    return request.delete(`/chat/contacts/${sessionId}`);
}

export function markChatRead(sessionId: string) {
    return request.post("/chat/mark-read", { session_id: sessionId });
}

export function getChatUnreadCounts() {
    return request.get("/chat/unread-counts");
}

export function getChatActiveTasks() {
    return request.get("/chat/active-tasks");
}

export function cancelChatTask(taskId: string) {
    return request.post(`/chat/tasks/${taskId}/cancel`);
}

export function injectChatTaskMessage(taskId: string, content: string) {
    return request.post(`/chat/tasks/${taskId}/message`, { content });
}

export function searchChatMessages(q: string, sessionId?: string, limit?: number) {
    return request.get("/chat/messages/search", { params: { q, session_id: sessionId, limit } });
}

export function getChatMessages(sessionId: string, before?: string, limit?: number) {
    return request.get("/chat/messages", { params: { session_id: sessionId, before, limit } });
}
