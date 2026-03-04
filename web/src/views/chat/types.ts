export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    images?: string[];
    toolCalls?: ToolCall[];
    toolsExpanded?: boolean;
    timestamp: number;
    streaming?: boolean;
}

export interface ChatSession {
    session_id: string;
    title: string;
    created_at: number;
    updated_at: number;
    target_type?: string;
    target_id?: string;
    pinned?: boolean;
}

export interface ToolCall {
    name: string;
    status: string;
    elapsed?: number;
    output?: string;
    collapsed?: boolean;
    count?: number;
    hasLiveOutput?: boolean;
}

export interface PendingImage {
    data: string;
    media_type: string;
    preview: string;
}

export interface Contact {
    type: "ai" | "member";
    id: string;
    name: string;
    avatar_url: string;
    last_message: string;
    last_message_time: number;
    unread: number;
    session_count?: number;
    session_id?: string;
    pinned?: boolean;
    position?: string;
    bio?: string;
}

export interface MentionMember {
    id: string;
    name: string;
    avatar_url: string;
    email: string;
    position?: string;
    department?: string;
}

export interface SlashCommand {
    name: string;
    label: string;
    description: string;
}

export interface Draft {
    text: string;
    images: PendingImage[];
}

export interface HashTagCategory {
    key: string;       // e.g. "bug", "task", "story", "milestone"
    label: string;     // e.g. "#bug"
    description: string;
    icon?: string;
    plugin: "vortflow" | "vortgit";
}

export interface HashTagItem {
    id: string;
    title: string;
    state?: string;
    priority?: number;
    category: string;  // back-ref to HashTagCategory.key
}
