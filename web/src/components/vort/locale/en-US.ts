import type { Locale } from "./types";

/**
 * English (US) language pack
 */
const enUS: Locale = {
    locale: "en-US",

    Pagination: {
        items_per_page: "/ page",
        jump_to: "Go to",
        page: "",
        prev_page: "Previous page",
        next_page: "Next page",
        prev_n: "Previous {count} pages",
        next_n: "Next {count} pages",
        total: "{start}-{end} of {total} items"
    },

    Table: {
        empty_text: "No data",
        filter_confirm: "OK",
        filter_reset: "Reset",
        select_all: "Select current page",
        select_invert: "Invert current page",
        sort_asc: "Click to sort ascending",
        sort_desc: "Click to sort descending",
        sort_cancel: "Click to cancel sorting"
    },

    Modal: {
        ok_text: "OK",
        cancel_text: "Cancel"
    },

    Drawer: {
        close: "Close"
    },

    Popconfirm: {
        ok_text: "OK",
        cancel_text: "Cancel"
    },

    Upload: {
        upload_text: "Click to upload",
        drag_text: "Click or drag file to this area to upload",
        remove_file: "Remove file",
        preview_file: "Preview file"
    },

    Select: {
        no_data: "No data",
        search_placeholder: "Search"
    },

    DatePicker: {
        today: "Today",
        now: "Now",
        ok: "OK",
        clear: "Clear",
        start_date: "Start date",
        end_date: "End date",
        start_time: "Start time",
        end_time: "End time",
        months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        weekdays: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        weekdays_short: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
    },

    TimePicker: {
        placeholder: "Select time",
        range_separator: "to"
    },

    Transfer: {
        search_placeholder: "Search",
        no_data: "No data",
        selected_items: "{count} items selected"
    },

    Empty: {
        description: "No data"
    }
};

export default enUS;
