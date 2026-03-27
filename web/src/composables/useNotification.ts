import { ref, watch, onUnmounted } from "vue";
import { notification } from "@openvort/vort-ui";
import { useNotificationStore } from "@/stores/modules/notification";
import { useRouter } from "vue-router";

let audioCtx: AudioContext | null = null;
let audioBuffer: AudioBuffer | null = null;
let audioReady = false;
const originalTitle = document.title;
const soundEnabled = ref(true);
const desktopEnabled = ref(false);
let titleTimer: ReturnType<typeof setInterval> | null = null;

async function initAudio() {
    if (audioReady) return;
    try {
        audioCtx = new AudioContext();
        const resp = await fetch("/audio/notification.mp3");
        if (resp.ok) {
            const buf = await resp.arrayBuffer();
            audioBuffer = await audioCtx.decodeAudioData(buf);
            audioReady = true;
        }
    } catch {
        // Audio not available, degrade silently
    }
}

function playSound() {
    if (!soundEnabled.value || !audioCtx || !audioBuffer) return;
    try {
        if (audioCtx.state === "suspended") audioCtx.resume();
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);
        source.start(0);
    } catch {
        // ignore playback errors
    }
}

function showToast(
    senderName: string,
    summary: string,
    severity: "info" | "error" = "info",
    onClick?: () => void,
) {
    const type = severity === "error" ? "error" : "info";
    notification[type]({
        message: senderName,
        description: summary.slice(0, 120),
        duration: 5000,
        onClose: onClick,
    });
}

function showDesktopNotification(senderName: string, summary: string) {
    if (!desktopEnabled.value) return;
    if (typeof Notification === "undefined") return;
    if (Notification.permission !== "granted") return;
    if (document.visibilityState === "visible") return;

    try {
        new Notification(senderName, {
            body: summary.slice(0, 200),
            icon: "/favicon.ico",
        });
    } catch {
        // ignore
    }
}

function updateTabTitle(unreadCount: number) {
    if (titleTimer) {
        clearInterval(titleTimer);
        titleTimer = null;
    }
    if (unreadCount > 0) {
        document.title = `(${unreadCount}) ${originalTitle}`;
    } else {
        document.title = originalTitle;
    }
}

export async function requestDesktopPermission() {
    if (typeof Notification === "undefined") return false;
    if (Notification.permission === "granted") {
        desktopEnabled.value = true;
        return true;
    }
    if (Notification.permission === "denied") return false;
    const result = await Notification.requestPermission();
    desktopEnabled.value = result === "granted";
    return desktopEnabled.value;
}

export function useNotification() {
    const notificationStore = useNotificationStore();
    const router = useRouter();

    // Preload audio on first user interaction
    const initOnce = () => {
        initAudio();
        document.removeEventListener("click", initOnce);
        document.removeEventListener("keydown", initOnce);
    };
    document.addEventListener("click", initOnce, { once: true });
    document.addEventListener("keydown", initOnce, { once: true });

    // Watch total unread and update tab title
    const stopWatch = watch(
        () => notificationStore.totalUnreadCount,
        (count) => updateTabTitle(count),
        { immediate: true },
    );

    onUnmounted(() => {
        stopWatch();
        document.title = originalTitle;
    });

    function loadPrefs() {
        try {
            const raw = localStorage.getItem("notification-prefs");
            if (raw) {
                const p = JSON.parse(raw);
                soundEnabled.value = p.sound_enabled !== false;
                desktopEnabled.value = p.desktop_enabled === true;
            }
        } catch { /* silent */ }
    }

    function savePrefs() {
        localStorage.setItem("notification-prefs", JSON.stringify({
            sound_enabled: soundEnabled.value,
            desktop_enabled: desktopEnabled.value,
        }));
    }

    loadPrefs();

    function notifyNewMessage(opts: {
        senderName: string;
        summary: string;
        sessionId: string;
        severity?: "info" | "error";
        isCurrentSession?: boolean;
    }) {
        if (opts.isCurrentSession) return;

        playSound();
        showToast(opts.senderName, opts.summary, opts.severity ?? "info", () => {
            router.push({ path: "/chat", query: { session: opts.sessionId } });
        });
        showDesktopNotification(opts.senderName, opts.summary);
    }

    return {
        soundEnabled,
        desktopEnabled,
        notifyNewMessage,
        requestDesktopPermission,
        savePrefs,
    };
}
