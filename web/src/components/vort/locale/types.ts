/**
 * Vort 组件库国际化类型定义
 */

export interface PaginationLocale {
    /** 每页条数，如 "条/页" */
    items_per_page: string;
    /** 跳转前缀，如 "跳至" */
    jump_to: string;
    /** 页后缀，如 "页" */
    page: string;
    /** 上一页 */
    prev_page: string;
    /** 下一页 */
    next_page: string;
    /** 向前 N 页，支持 {count} 占位符 */
    prev_n: string;
    /** 向后 N 页，支持 {count} 占位符 */
    next_n: string;
    /** 总数显示，支持 {start} {end} {total} 占位符 */
    total: string;
}

export interface TableLocale {
    /** 空数据文本 */
    empty_text: string;
    /** 筛选确认按钮 */
    filter_confirm: string;
    /** 筛选重置按钮 */
    filter_reset: string;
    /** 全选当页 */
    select_all: string;
    /** 反选当页 */
    select_invert: string;
    /** 排序升序提示 */
    sort_asc: string;
    /** 排序降序提示 */
    sort_desc: string;
    /** 取消排序提示 */
    sort_cancel: string;
}

export interface ModalLocale {
    /** 确定按钮文本 */
    ok_text: string;
    /** 取消按钮文本 */
    cancel_text: string;
}

export interface DrawerLocale {
    /** 关闭按钮 aria-label */
    close: string;
}

export interface PopconfirmLocale {
    /** 确定按钮文本 */
    ok_text: string;
    /** 取消按钮文本 */
    cancel_text: string;
}

export interface UploadLocale {
    /** 上传文件按钮 */
    upload_text: string;
    /** 拖拽上传提示 */
    drag_text: string;
    /** 移除文件 */
    remove_file: string;
    /** 预览文件 */
    preview_file: string;
}

export interface SelectLocale {
    /** 无数据时显示 */
    no_data: string;
    /** 搜索框占位符 */
    search_placeholder: string;
}

export interface DatePickerLocale {
    /** 今天 */
    today: string;
    /** 此刻 */
    now: string;
    /** 确定 */
    ok: string;
    /** 清除 */
    clear: string;
    /** 开始日期 */
    start_date: string;
    /** 结束日期 */
    end_date: string;
    /** 开始时间 */
    start_time: string;
    /** 结束时间 */
    end_time: string;
    /** 月份名称 */
    months: string[];
    /** 星期名称（周日到周六） */
    weekdays: string[];
    /** 星期名称简写 */
    weekdays_short: string[];
}

export interface TimePickerLocale {
    /** 占位符 */
    placeholder: string;
    /** 范围选择分隔符 */
    range_separator: string;
}

export interface TransferLocale {
    /** 搜索框占位符 */
    search_placeholder: string;
    /** 无数据 */
    no_data: string;
    /** 已选 N 项 */
    selected_items: string;
}

export interface EmptyLocale {
    /** 暂无数据 */
    description: string;
}

/**
 * Vort 组件库完整 Locale 类型
 */
export interface Locale {
    /** 语言标识，如 "zh-CN"、"en-US" */
    locale: string;
    /** 分页组件 */
    Pagination: PaginationLocale;
    /** 表格组件 */
    Table: TableLocale;
    /** 对话框组件 */
    Modal: ModalLocale;
    /** 抽屉组件 */
    Drawer: DrawerLocale;
    /** 气泡确认框组件 */
    Popconfirm: PopconfirmLocale;
    /** 上传组件 */
    Upload: UploadLocale;
    /** 选择器组件 */
    Select: SelectLocale;
    /** 日期选择器组件 */
    DatePicker: DatePickerLocale;
    /** 时间选择器组件 */
    TimePicker: TimePickerLocale;
    /** 穿梭框组件 */
    Transfer: TransferLocale;
    /** 空状态组件 */
    Empty: EmptyLocale;
}

/** Locale 中的组件名称 */
export type LocaleComponentName = Exclude<keyof Locale, "locale">;
