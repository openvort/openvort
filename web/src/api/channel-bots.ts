import request from "@/utils/request";

export interface ChannelBotItem {
    id: string;
    channel_type: string;
    member_id: string;
    credentials: Record<string, string>;
    status: string;
    last_test_at: string | null;
    last_test_ok: boolean;
    created_at: string | null;
}

export interface CredentialField {
    key: string;
    label: string;
    secret: boolean;
    required: boolean;
    placeholder: string;
    description: string;
}

export function getChannelBots(params?: { member_id?: string; channel_type?: string }) {
    return request.get("/admin/channel-bots", { params });
}

export function getChannelBotCredentialFields() {
    return request.get("/admin/channel-bots/credential-fields");
}

export function getChannelBotSummary() {
    return request.get("/admin/channel-bots/summary");
}

export function createChannelBot(data: { channel_type: string; member_id: string; credentials: Record<string, string> }) {
    return request.post("/admin/channel-bots", data);
}

export function updateChannelBot(botId: string, data: { credentials?: Record<string, string>; status?: string }) {
    return request.put(`/admin/channel-bots/${botId}`, data);
}

export function deleteChannelBot(botId: string) {
    return request.delete(`/admin/channel-bots/${botId}`);
}

export function testChannelBot(botId: string) {
    return request.post(`/admin/channel-bots/${botId}/test`);
}
