export interface JenkinsInstance {
    id: string;
    name: string;
    url: string;
    verify_ssl: boolean;
    is_default: boolean;
    created_at: string | null;
    updated_at: string | null;
}

export interface JenkinsBuild {
    number: number;
    result: string | null;
    timestamp: number;
    building: boolean;
    duration: number;
    estimatedDuration?: number;
    url: string;
}

export interface JenkinsJob {
    name: string;
    full_name: string;
    url: string;
    color: string;
    description: string;
    in_queue: boolean;
    is_folder: boolean;
    class?: string;
    last_build: JenkinsBuild | null;
}

export interface JenkinsParameterDef {
    name: string;
    type: string;
    description: string;
    default: string;
    choices?: string[];
}

export interface JenkinsJobDetail {
    name: string;
    full_name: string;
    display_name: string;
    description: string;
    url: string;
    buildable: boolean;
    in_queue: boolean;
    next_build_number: number | null;
    color: string;
    last_build: JenkinsBuild | null;
    last_completed_build: JenkinsBuild | null;
    parameters: JenkinsParameterDef[];
    builds: JenkinsBuild[];
}

export interface JenkinsView {
    name: string;
}

export interface JenkinsConfigItem {
    label: string;
    value: string;
    type: "text" | "code";
}

export interface JenkinsConfigSection {
    title: string;
    items: JenkinsConfigItem[];
}

export interface JenkinsConfigSummary {
    job_name: string;
    job_type: string;
    sections: JenkinsConfigSection[];
    raw_xml_length: number;
    config_xml?: string;
}

export type JenkinsColor =
    | "blue" | "red" | "yellow" | "grey" | "notbuilt" | "disabled" | "aborted"
    | "blue_anime" | "red_anime" | "yellow_anime" | "grey_anime" | "aborted_anime";

export function getColorStatus(color: string): { label: string; variant: "success" | "error" | "warning" | "default"; animating: boolean } {
    const animating = color?.endsWith("_anime") ?? false;
    const base = animating ? color.replace("_anime", "") : color;

    switch (base) {
        case "blue":
            return { label: animating ? "构建中" : "成功", variant: "success", animating };
        case "red":
            return { label: animating ? "构建中" : "失败", variant: "error", animating };
        case "yellow":
            return { label: animating ? "构建中" : "不稳定", variant: "warning", animating };
        case "aborted":
            return { label: "已中止", variant: "default", animating };
        case "disabled":
            return { label: "已禁用", variant: "default", animating: false };
        default:
            return { label: "未构建", variant: "default", animating };
    }
}

export function formatDuration(ms: number): string {
    if (!ms || ms <= 0) return "-";
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainSeconds = seconds % 60;
    if (minutes < 60) return remainSeconds > 0 ? `${minutes}m ${remainSeconds}s` : `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainMinutes = minutes % 60;
    return remainMinutes > 0 ? `${hours}h ${remainMinutes}m` : `${hours}h`;
}

export function formatRelativeTime(timestamp: number): string {
    if (!timestamp) return "-";
    const now = Date.now();
    const diff = now - timestamp;
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return "刚刚";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} 分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} 天前`;
    const months = Math.floor(days / 30);
    return `${months} 个月前`;
}
