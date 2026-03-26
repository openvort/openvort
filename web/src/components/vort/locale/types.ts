/**
 * Vort 组件库国际化类型定义
 */

export interface PaginationLocale {
    items_per_page: string;
    jump_to: string;
    page: string;
    prev_page: string;
    next_page: string;
    prev_n: string;
    next_n: string;
    total: string;
    pagination: string;
}

export interface TableLocale {
    empty_text: string;
    filter_confirm: string;
    filter_reset: string;
    select_all: string;
    select_invert: string;
    sort_asc: string;
    sort_desc: string;
    sort_cancel: string;
}

export interface ModalLocale {
    ok_text: string;
    cancel_text: string;
    got_it: string;
    close: string;
}

export interface DrawerLocale {
    close: string;
}

export interface PopconfirmLocale {
    ok_text: string;
    cancel_text: string;
}

export interface UploadLocale {
    upload_text: string;
    drag_text: string;
    remove_file: string;
    preview_file: string;
}

export interface SelectLocale {
    no_data: string;
    search_placeholder: string;
    placeholder: string;
    no_match: string;
}

export interface DatePickerLocale {
    today: string;
    now: string;
    ok: string;
    clear: string;
    start_date: string;
    end_date: string;
    start_time: string;
    end_time: string;
    months: string[];
    weekdays: string[];
    weekdays_short: string[];
    year_suffix: string;
    date_placeholder: string;
    datetime_placeholder: string;
    start_datetime: string;
    end_datetime: string;
}

export interface TimePickerLocale {
    placeholder: string;
    range_separator: string;
    now: string;
    ok: string;
}

export interface TransferLocale {
    search_placeholder: string;
    no_data: string;
    selected_items: string;
}

export interface EmptyLocale {
    description: string;
}

export interface FormLocale {
    validation_failed: string;
    required: string;
    number: string;
    min_value: string;
    max_value: string;
    min_length: string;
    max_length: string;
    pattern: string;
    optional: string;
}

export interface CascaderLocale {
    placeholder: string;
    no_data: string;
}

export interface AutoCompleteLocale {
    placeholder: string;
    no_match: string;
}

export interface InputPasswordLocale {
    show_password: string;
    hide_password: string;
}

export interface AlertLocale {
    close: string;
}

export interface Locale {
    locale: string;
    Pagination: PaginationLocale;
    Table: TableLocale;
    Modal: ModalLocale;
    Drawer: DrawerLocale;
    Popconfirm: PopconfirmLocale;
    Upload: UploadLocale;
    Select: SelectLocale;
    DatePicker: DatePickerLocale;
    TimePicker: TimePickerLocale;
    Transfer: TransferLocale;
    Empty: EmptyLocale;
    Form: FormLocale;
    Cascader: CascaderLocale;
    AutoComplete: AutoCompleteLocale;
    InputPassword: InputPasswordLocale;
    Alert: AlertLocale;
}

export type LocaleComponentName = Exclude<keyof Locale, "locale">;
