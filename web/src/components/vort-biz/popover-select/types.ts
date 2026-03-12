import type { PropType, VNodeChild } from "vue";
import type { PopoverPlacement } from "@/components/vort/popover";

export type PopoverSelectSize = "large" | "middle" | "small";

export interface PopoverSelectTriggerSlotProps {
    open: boolean;
    keyword: string;
}

export interface PopoverSelectDefaultSlotProps {
    open: boolean;
    keyword: string;
}

export interface PopoverSelectSearchSlotProps {
    keyword: string;
}

export interface PopoverSelectFooterSlotProps {
    open: boolean;
    keyword: string;
}

export const popoverSelectSizeProp = {
    type: String as PropType<PopoverSelectSize>,
    default: "middle"
};

export interface PopoverSelectOptionLike {
    label: string;
    value: string | number;
    render?: () => VNodeChild;
}

export interface PopoverSelectProps {
    disabled?: boolean;
    size?: PopoverSelectSize;
    placeholder?: string;
    showSearch?: boolean;
    searchPlaceholder?: string;
    dropdownWidth?: number | string;
    dropdownMaxHeight?: number;
    placement?: PopoverPlacement;
    triggerClass?: string;
    dropdownClass?: string;
    bordered?: boolean;
    clearSearchOnClose?: boolean;
}
