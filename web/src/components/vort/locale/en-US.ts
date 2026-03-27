import type { Locale } from "./types";

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
        total: "{start}-{end} of {total} items",
        pagination: "Pagination"
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
        cancel_text: "Cancel",
        got_it: "Got it",
        close: "Close"
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
        search_placeholder: "Search",
        placeholder: "Select",
        no_match: "No matching results"
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
        weekdays_short: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"],
        year_suffix: "",
        date_placeholder: "Select date",
        datetime_placeholder: "Select date and time",
        start_datetime: "Start date and time",
        end_datetime: "End date and time"
    },

    TimePicker: {
        placeholder: "Select time",
        range_separator: "to",
        now: "Now",
        ok: "OK"
    },

    Transfer: {
        search_placeholder: "Search",
        no_data: "No data",
        selected_items: "{count} items selected"
    },

    Empty: {
        description: "No data"
    },

    Form: {
        validation_failed: "Validation failed",
        required: "This field is required",
        number: "Please enter a number",
        min_value: "Cannot be less than {min}",
        max_value: "Cannot be greater than {max}",
        min_length: "Length cannot be less than {min}",
        max_length: "Length cannot be greater than {max}",
        pattern: "Invalid format",
        optional: "(Optional)"
    },

    Cascader: {
        placeholder: "Please select",
        no_data: "No data"
    },

    AutoComplete: {
        placeholder: "Please enter",
        no_match: "No matching results"
    },

    InputPassword: {
        show_password: "Show password",
        hide_password: "Hide password"
    },

    Alert: {
        close: "Close"
    }
};

export default enUS;
