/**
 * Table 渲染器组件
 * 用于渲染 TableColumn 的 slot 内容
 */
import { defineComponent, type PropType } from "vue";
import type { TableColumn, TableCellScope, TableHeaderScope } from "./types";

/**
 * 单元格渲染器
 * 用于渲染 TableColumn 的 default slot
 */
export const CellRenderer = defineComponent({
    name: "TableCellRenderer",
    props: {
        render: {
            type: Function as PropType<(scope: TableCellScope) => any>,
            required: true
        },
        value: {
            type: null,
            default: undefined
        },
        row: {
            type: Object,
            default: undefined
        },
        index: {
            type: Number,
            default: 0
        },
        column: {
            type: Object as PropType<TableColumn>,
            required: true
        }
    },
    setup(props) {
        return () =>
            props.render({
                value: props.value,
                row: props.row,
                index: props.index,
                column: props.column
            });
    }
});

/**
 * 表头渲染器
 * 用于渲染 TableColumn 的 header slot
 */
export const HeaderRenderer = defineComponent({
    name: "TableHeaderRenderer",
    props: {
        render: {
            type: Function as PropType<(scope: TableHeaderScope) => any>,
            required: true
        },
        column: {
            type: Object as PropType<TableColumn>,
            required: true
        }
    },
    setup(props) {
        return () => props.render({ column: props.column });
    }
});
