export interface MemberItem {
    id: string;
    name: string;
    email: string;
    phone: string;
    position: string;
    status: string;
    is_account: boolean;
    has_password: boolean;
    roles: string[];
    platform_accounts: Record<string, string>;
    departments: string[];
    created_at: string;
}

export interface MemberDetail extends Omit<MemberItem, 'departments'> {
    avatar_url: string;
    permissions: string[];
    remote_node_id: string;
    departments: { id: number; name: string }[];
    identities: {
        id: number;
        platform: string;
        platform_user_id: string;
        platform_username: string;
        platform_display_name: string;
        platform_email: string;
        platform_position: string;
        platform_department: string;
    }[];
}

export interface RoleItem {
    id: number;
    name: string;
    display_name: string;
    source: string;
    is_builtin: boolean;
    is_admin: boolean;
    permissions: { code: string; display_name: string }[];
    member_count: number;
}

export interface Suggestion {
    id: number;
    source_member_id: string;
    source_name: string;
    source_platform: string;
    target_member_id: string;
    target_name: string;
    match_type: string;
    confidence: number;
}

export interface ChannelItem {
    name: string;
    display_name: string;
    type: string;
    status: string;
    enabled: boolean;
}

export interface PermissionItem {
    id: number;
    code: string;
    display_name: string;
    source: string;
}

export interface PermGroup {
    key: string;
    label: string;
    permissions: PermissionItem[];
}

export interface CalendarEntry {
    id: number;
    date: string;
    day_type: string;
    name: string;
    year: number;
}

export interface WorkSettingsData {
    timezone: string;
    work_start: string;
    work_end: string;
    work_days: string;
    lunch_start: string;
    lunch_end: string;
}
