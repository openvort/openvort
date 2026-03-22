import type { ChatMessage } from "./types";

const TIME_GAP_THRESHOLD = 5 * 60 * 1000; // 5 min

/**
 * Whether to show a time divider above the message at `index`.
 * Rules (similar to WeChat / 企业微信):
 *  - Always show for the first message (if it has a valid ts).
 *  - Show when the gap from the previous message >= 5 minutes.
 *  - Skip if either message has no timestamp (legacy data).
 */
export function shouldShowTimestamp(messages: ChatMessage[], index: number): boolean {
    const curr = messages[index];
    if (!curr?.timestamp) return false;
    if (index === 0) return true;
    const prev = messages[index - 1];
    if (!prev?.timestamp) return true;
    return curr.timestamp - prev.timestamp >= TIME_GAP_THRESHOLD;
}

/**
 * Format a millisecond-epoch timestamp into a human-friendly divider label.
 *  - Today:       "16:09"
 *  - Yesterday:   "昨天 16:09"
 *  - This week:   "星期一 16:09"
 *  - This year:   "3月15日 16:09"
 *  - Older:       "2024年3月15日 16:09"
 */
export function formatTimeDivider(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;

    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86_400_000;
    const ts = date.getTime();

    if (ts >= todayStart) return time;
    if (ts >= yesterdayStart) return `昨天 ${time}`;

    const weekDays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
    const daysDiff = Math.floor((todayStart - ts) / 86_400_000);
    if (daysDiff < 7) return `${weekDays[date.getDay()]} ${time}`;

    if (date.getFullYear() === now.getFullYear()) {
        return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`;
    }
    return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 ${time}`;
}
