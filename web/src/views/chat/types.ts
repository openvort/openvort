export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    images?: string[];
    toolCalls?: { name: string; status: string; elapsed?: number; output?: string }[];
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
