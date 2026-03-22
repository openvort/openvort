// 类型导出
export type {
    Locale,
    LocaleComponentName,
    PaginationLocale,
    TableLocale,
    ModalLocale,
    DrawerLocale,
    PopconfirmLocale,
    UploadLocale,
    SelectLocale,
    DatePickerLocale,
    TimePickerLocale,
    TransferLocale,
    EmptyLocale
} from "./types";

// 语言包导出
export { default as zhCN } from "./zh-CN";
export { default as enUS } from "./en-US";

// Composable 导出
export { useLocale, useGlobalLocale, localeContextKey } from "./useLocale";
