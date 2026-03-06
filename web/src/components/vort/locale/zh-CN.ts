import type { Locale } from "./types";

/**
 * 简体中文语言包
 */
const zhCN: Locale = {
    locale: "zh-CN",

    Pagination: {
        items_per_page: "条/页",
        jump_to: "跳至",
        page: "页",
        prev_page: "上一页",
        next_page: "下一页",
        prev_n: "向前 {count} 页",
        next_n: "向后 {count} 页",
        total: "第 {start}-{end} 条 / 总共 {total} 条"
    },

    Table: {
        empty_text: "暂无数据",
        filter_confirm: "确定",
        filter_reset: "重置",
        select_all: "全选当页",
        select_invert: "反选当页",
        sort_asc: "点击升序",
        sort_desc: "点击降序",
        sort_cancel: "取消排序"
    },

    Modal: {
        ok_text: "确定",
        cancel_text: "取消"
    },

    Drawer: {
        close: "关闭"
    },

    Popconfirm: {
        ok_text: "确定",
        cancel_text: "取消"
    },

    Upload: {
        upload_text: "点击上传",
        drag_text: "点击或拖拽文件到此区域上传",
        remove_file: "删除文件",
        preview_file: "预览文件"
    },

    Select: {
        no_data: "暂无数据",
        search_placeholder: "请输入搜索内容"
    },

    DatePicker: {
        today: "今天",
        now: "此刻",
        ok: "确定",
        clear: "清除",
        start_date: "开始日期",
        end_date: "结束日期",
        start_time: "开始时间",
        end_time: "结束时间",
        months: ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"],
        weekdays: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"],
        weekdays_short: ["日", "一", "二", "三", "四", "五", "六"]
    },

    TimePicker: {
        placeholder: "请选择时间",
        range_separator: "至"
    },

    Transfer: {
        search_placeholder: "请输入搜索内容",
        no_data: "暂无数据",
        selected_items: "已选 {count} 项"
    },

    Empty: {
        description: "暂无数据"
    }
};

export default zhCN;
