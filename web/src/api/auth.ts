import request from "@/utils/request";

export function login(user_id: string, password: string, remember_me: boolean = false) {
    return request.post("/auth/login", { user_id, password, remember_me });
}

export interface SiteInfo {
    is_demo: boolean;
}

export function getSiteInfo(): Promise<SiteInfo> {
    return request.get("/auth/site-info", { skipErrorMessage: true });
}

export function getHealthStatus(force?: boolean) {
    return request.get("/health", { params: force ? { force: true } : undefined, skipErrorMessage: true });
}

export function getDashboard() {
    return request.get("/dashboard");
}
