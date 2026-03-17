import { type Ref } from "vue";
import type { ChatMessage, ChatSession, Contact, Draft, PendingImage } from "../types";
import type { ActiveStream } from "./useChatStream";
import { startMemberChat, markChatRead } from "@/api";
import { useNotificationStore } from "@/stores/modules/notification";
import { message } from "@/components/vort";

interface UseChatSessionOptions {
    messages: Ref<ChatMessage[]>;
    inputText: Ref<string>;
    loading: Ref<boolean>;
    currentSessionId: Ref<string>;
    activeContact: Ref<Contact | null>;
    sessions: Ref<ChatSession[]>;
    sessionTokens: Ref<{ input: number; output: number; messages: number; cacheCreation: number; cacheRead: number }>;
    thinkingLevel: Ref<string>;
    pendingImages: Ref<PendingImage[]>;
    messageCounter: Ref<number>;
    hasMoreHistory: Ref<boolean>;
    historyOffset: Ref<number>;
    contextResetAt: Ref<number>;
    activeStreams: Map<string, ActiveStream>;
    drafts: Map<string, Draft>;
    sessionSwitcherRef: Ref<any>;
    loadHistory: () => Promise<boolean>;
    loadSessionInfo: () => Promise<void>;
    scrollToBottom: (force?: boolean) => void;
}

export function useChatSession(options: UseChatSessionOptions) {
    const {
        messages, inputText, loading, currentSessionId, activeContact, sessions,
        sessionTokens, thinkingLevel, pendingImages, messageCounter,
        hasMoreHistory, historyOffset, contextResetAt,
        activeStreams, drafts, sessionSwitcherRef,
        loadHistory, loadSessionInfo, scrollToBottom,
    } = options;

    function saveDraft() {
        const key = currentSessionId.value;
        if (inputText.value || pendingImages.value.length) {
            drafts.set(key, { text: inputText.value, images: [...pendingImages.value] });
        } else {
            drafts.delete(key);
        }
    }

    function restoreDraft(sessionId: string) {
        const draft = drafts.get(sessionId);
        inputText.value = draft?.text ?? "";
        pendingImages.value = draft?.images ? [...draft.images] : [];
    }

    function handleNewSession() {
        if (!currentSessionId.value && messages.value.length === 0) {
            message.info("已经是最新对话");
            return;
        }
        saveDraft();
        currentSessionId.value = "";
        messages.value = [];
        messageCounter.value = 0;
        sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };
        loading.value = false;
        thinkingLevel.value = "off";
        contextResetAt.value = 0;
        hasMoreHistory.value = false;
        historyOffset.value = 0;
        restoreDraft("");
    }

    async function switchSession(sessionId: string) {
        if (currentSessionId.value === sessionId && messages.value.length > 0) return;

        saveDraft();

        const prevId = currentSessionId.value;
        if (prevId && loading.value) {
            const stream = activeStreams.get(prevId);
            if (stream) {
                stream.messagesRef = [...messages.value];
            }
        }

        currentSessionId.value = sessionId;
        messageCounter.value = 0;
        sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };

        const notifStore = useNotificationStore();
        if (notifStore.getUnread(sessionId) > 0) {
            notifStore.clearUnread(sessionId);
            markChatRead(sessionId).catch(() => {});
        }

        const existingStream = activeStreams.get(sessionId);
        if (existingStream && !existingStream.done) {
            messages.value = existingStream.messagesRef;
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && lastMsg.role === "assistant" && lastMsg.streaming) {
                existingStream.assistantMsg = lastMsg;
                lastMsg.content = existingStream.targetText;
                loading.value = true;
                scrollToBottom(true);
            }
            restoreDraft(sessionId);
            await loadSessionInfo();
            return;
        }

        messages.value = [];
        loading.value = false;
        await loadHistory();
        restoreDraft(sessionId);
        await loadSessionInfo();
    }

    async function handleContactSelect(contact: Contact) {
        activeContact.value = contact;
        if (contact.type === "ai") {
            await sessionSwitcherRef.value?.loadSessions();
            const lastSessionId = localStorage.getItem('chat-last-session-id');
            if (lastSessionId && sessions.value.some(s => s.session_id === lastSessionId)) {
                await switchSession(lastSessionId);
            } else if (sessions.value.length > 0) {
                await switchSession(sessions.value[0].session_id);
            } else {
                handleNewSession();
            }
        } else {
            if (contact.session_id) {
                await switchSession(contact.session_id);
            } else {
                try {
                    const res: any = await startMemberChat(contact.id);
                    if (res?.session_id) {
                        contact.session_id = res.session_id;
                        await switchSession(res.session_id);
                    }
                } catch {
                    message.error("进入对话失败");
                }
            }
        }
    }

    function handleSessionsLoaded(loadedSessions: ChatSession[]) {
        sessions.value = loadedSessions.map(session => ({ ...session }));
    }

    return {
        switchSession,
        handleNewSession,
        handleContactSelect,
        handleSessionsLoaded,
        saveDraft,
        restoreDraft,
    };
}
