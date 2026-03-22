import request from "@/utils/request";

export function getNotifications(params?: { status?: string; source?: string; page?: number; limit?: number }) {
    return request.get("/notifications", { params });
}

export function batchReadNotifications(notificationIds?: number[], all?: boolean) {
    return request.post("/notifications/batch-read", { notification_ids: notificationIds || [], all: all || false });
}

export function getNotificationUnreadCount(source?: string) {
    return request.get("/notifications/unread-count", { params: source ? { source } : {} });
}
