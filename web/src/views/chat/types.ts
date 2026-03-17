export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    images?: string[];
    toolCalls?: ToolCall[];
    toolsExpanded?: boolean;
    timestamp: number;
    streaming?: boolean;
    avatar_url?: string;
    interrupted?: boolean;
    actionButtons?: ActionButton[];
}

export interface ActionButton {
    action: string;
    label: string;
    params?: Record<string, any>;
    clicked?: boolean;
    loading?: boolean;
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
    screenshots?: string[];
    id?: string;
    input?: Record<string, any>;
    outputExpanded?: boolean;
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
    /** Whether this contact represents an AI employee (virtual member) */
    is_virtual?: boolean;
    /** Optional virtual role key/name for AI employees */
    virtual_role_key?: string;
    virtual_role_name?: string;
    /** Bound remote node ID (AI employees only) */
    remote_node_id?: string;
    /** Remote node status: online / offline / unknown */
    remote_node_status?: string;
}

export interface MentionMember {
    id: string;
    name: string;
    avatar_url: string;
    email: string;
    position?: string;
    department?: string;
    is_virtual?: boolean;
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
