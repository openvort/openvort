const VORT_TELEPORT_CONTAINER_ID = "vort-teleport-container";

/**
 * Get the default teleport mount point.
 * Prefers #vort-teleport-container if present, falls back to "body".
 */
export function getVortTeleportTo(): HTMLElement | string {
    if (typeof window === "undefined") return "body";
    return document.getElementById(VORT_TELEPORT_CONTAINER_ID) ?? "body";
}
