import request from "@/utils/request";

export function login(user_id: string, password: string) {
    return request.post("/auth/login", { user_id, password });
}

export function getHealthStatus(force?: boolean) {
    return request.get("/health", { params: force ? { force: true } : undefined, skipErrorMessage: true });
}

export function getDashboard() {
    return request.get("/dashboard");
}
