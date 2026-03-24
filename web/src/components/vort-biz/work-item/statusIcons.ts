import type { Component } from 'vue'
import {
    Circle, CircleDot, CircleDashed, CircleCheck, CircleX,
    CircleMinus, CirclePlus, CircleSlash,
    Play, Pause, Clock, Hourglass,
    RotateCcw, Ban, Check, CheckCheck,
    X, AlertTriangle, Lock, Eye,
    Pencil, Target, Zap, Rocket,
    Flag, Star, Archive, Smile, Frown, HelpCircle,
} from 'lucide-vue-next'

export const STATUS_ICON_MAP: Record<string, Component> = {
    'circle': Circle,
    'circle-dot': CircleDot,
    'circle-dashed': CircleDashed,
    'circle-check': CircleCheck,
    'circle-x': CircleX,
    'circle-minus': CircleMinus,
    'circle-plus': CirclePlus,
    'circle-slash': CircleSlash,
    'play': Play,
    'pause': Pause,
    'clock': Clock,
    'hourglass': Hourglass,
    'rotate-ccw': RotateCcw,
    'ban': Ban,
    'check': Check,
    'check-check': CheckCheck,
    'x': X,
    'alert-triangle': AlertTriangle,
    'lock': Lock,
    'eye': Eye,
    'pencil': Pencil,
    'target': Target,
    'zap': Zap,
    'rocket': Rocket,
    'flag': Flag,
    'star': Star,
    'archive': Archive,
    'smile': Smile,
    'frown': Frown,
    'help-circle': HelpCircle,
}

export const STATUS_ICON_KEYS: string[] = [
    'circle', 'circle-dot', 'circle-dashed', 'circle-check', 'circle-x', 'circle-minus', 'circle-plus',
    'circle-slash', 'play', 'pause', 'clock', 'hourglass', 'rotate-ccw', 'ban',
    'check', 'check-check', 'x', 'alert-triangle', 'lock', 'eye', 'pencil',
    'target', 'zap', 'rocket', 'flag', 'star', 'archive', 'smile', 'frown', 'help-circle',
]

const LEGACY_ICON_MAP: Record<string, string> = {
    '\u25CB': 'circle',
    '\u25CF': 'circle-dot',
    '\u25D4': 'circle-dot',
    '\u25CE': 'target',
    '\u25B7': 'play',
    '\u263A': 'smile',
    '\u2639': 'frown',
    '\u2299': 'target',
    '\u2016': 'pause',
    '\u2296': 'circle-minus',
    '\u231B': 'hourglass',
    '\u2297': 'circle-x',
    '\u229C': 'circle-minus',
    '\u2298': 'circle-slash',
    '\u2295': 'circle-plus',
    '\u25B3': 'alert-triangle',
    '\u22A0': 'circle-x',
    '\u2630': 'pause',
    '\u2B20': 'circle-dashed',
    '\u270E': 'pencil',
    '\u2713': 'check',
    '\u2715': 'x',
    '\u26A1': 'zap',
    '!': 'alert-triangle',
    '?': 'help-circle',
}

export function resolveIconKey(icon: string): string | null {
    if (!icon) return null
    if (STATUS_ICON_MAP[icon]) return icon
    if (LEGACY_ICON_MAP[icon]) return LEGACY_ICON_MAP[icon]
    const firstChar = icon.charAt(0)
    if (LEGACY_ICON_MAP[firstChar]) return LEGACY_ICON_MAP[firstChar]
    return null
}

export function getIconComponent(icon: string): Component | null {
    const key = resolveIconKey(icon)
    return key ? STATUS_ICON_MAP[key] : null
}
