import { h, defineComponent } from "vue";

// 左箭头图标
export const LeftOutlined = defineComponent({
    name: "LeftOutlined",
    render() {
        return h(
            "svg",
            {
                viewBox: "64 64 896 896",
                focusable: "false",
                width: "1em",
                height: "1em",
                fill: "currentColor",
                "aria-hidden": "true"
            },
            [
                h("path", {
                    d: "M724 218.3V141c0-6.7-7.7-10.4-12.9-6.3L260.3 486.8a31.86 31.86 0 000 50.3l450.8 352.1c5.3 4.1 12.9.4 12.9-6.3v-77.3c0-4.9-2.3-9.6-6.1-12.6l-360-281 360-281.1c3.8-3 6.1-7.7 6.1-12.6z"
                })
            ]
        );
    }
});

// 右箭头图标
export const RightOutlined = defineComponent({
    name: "RightOutlined",
    render() {
        return h(
            "svg",
            {
                viewBox: "64 64 896 896",
                focusable: "false",
                width: "1em",
                height: "1em",
                fill: "currentColor",
                "aria-hidden": "true"
            },
            [
                h("path", {
                    d: "M765.7 486.8L314.9 134.7A7.97 7.97 0 00302 141v77.3c0 4.9 2.3 9.6 6.1 12.6l360 281.1-360 281.1c-3.9 3-6.1 7.7-6.1 12.6V869c0 6.7 7.7 10.4 12.9 6.3l450.8-352.1a31.96 31.96 0 000-50.4z"
                })
            ]
        );
    }
});

// 双左箭头图标（快速后退）
export const DoubleLeftOutlined = defineComponent({
    name: "DoubleLeftOutlined",
    render() {
        return h(
            "svg",
            {
                viewBox: "64 64 896 896",
                focusable: "false",
                width: "1em",
                height: "1em",
                fill: "currentColor",
                "aria-hidden": "true"
            },
            [
                h("path", {
                    d: "M272.9 512l265.4-339.1c4.1-5.2.4-12.9-6.3-12.9h-77.3c-4.9 0-9.6 2.3-12.6 6.1L186.8 492.3a31.99 31.99 0 000 39.5l255.3 326.1c3 3.9 7.7 6.1 12.6 6.1H532c6.7 0 10.4-7.7 6.3-12.9L272.9 512zm304 0l265.4-339.1c4.1-5.2.4-12.9-6.3-12.9h-77.3c-4.9 0-9.6 2.3-12.6 6.1L490.8 492.3a31.99 31.99 0 000 39.5l255.3 326.1c3 3.9 7.7 6.1 12.6 6.1H836c6.7 0 10.4-7.7 6.3-12.9L576.9 512z"
                })
            ]
        );
    }
});

// 双右箭头图标（快速前进）
export const DoubleRightOutlined = defineComponent({
    name: "DoubleRightOutlined",
    render() {
        return h(
            "svg",
            {
                viewBox: "64 64 896 896",
                focusable: "false",
                width: "1em",
                height: "1em",
                fill: "currentColor",
                "aria-hidden": "true"
            },
            [
                h("path", {
                    d: "M533.2 492.3L277.9 166.1c-3-3.9-7.7-6.1-12.6-6.1H188c-6.7 0-10.4 7.7-6.3 12.9L447.1 512 181.7 851.1A7.98 7.98 0 00188 864h77.3c4.9 0 9.6-2.3 12.6-6.1l255.3-326.1c9.1-11.7 9.1-27.9 0-39.5zm304 0L581.9 166.1c-3-3.9-7.7-6.1-12.6-6.1H492c-6.7 0-10.4 7.7-6.3 12.9L751.1 512 485.7 851.1A7.98 7.98 0 00492 864h77.3c4.9 0 9.6-2.3 12.6-6.1l255.3-326.1c9.1-11.7 9.1-27.9 0-39.5z"
                })
            ]
        );
    }
});

// 更多图标（省略号）
export const MoreOutlined = defineComponent({
    name: "MoreOutlined",
    render() {
        return h(
            "svg",
            {
                viewBox: "0 0 1024 1024",
                focusable: "false",
                width: "1em",
                height: "1em",
                fill: "currentColor",
                "aria-hidden": "true"
            },
            [
                h("path", {
                    d: "M176 416a112 112 0 1 1 0 224 112 112 0 0 1 0-224m336 0a112 112 0 1 1 0 224 112 112 0 0 1 0-224m336 0a112 112 0 1 1 0 224 112 112 0 0 1 0-224"
                })
            ]
        );
    }
});
