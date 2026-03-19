import { z, type ZodErrorMap, ZodIssueCode, ZodParsedType } from "zod";

const zhCNErrorMap: ZodErrorMap = (issue, ctx) => {
    let message: string;

    switch (issue.code) {
        case ZodIssueCode.invalid_type:
            if (issue.received === ZodParsedType.undefined || issue.received === ZodParsedType.null) {
                message = "必填项";
            } else {
                message = `类型错误：期望 ${issue.expected}，收到 ${issue.received}`;
            }
            break;
        case ZodIssueCode.invalid_literal:
            message = `值必须为 ${JSON.stringify(issue.expected)}`;
            break;
        case ZodIssueCode.unrecognized_keys:
            message = `包含未识别的字段：${issue.keys.map((k) => `"${k}"`).join(", ")}`;
            break;
        case ZodIssueCode.invalid_union:
            message = "输入不符合任何预期格式";
            break;
        case ZodIssueCode.invalid_union_discriminator:
            message = `无效的类型标识，期望 ${issue.options.map((v) => `"${v}"`).join(" | ")}`;
            break;
        case ZodIssueCode.invalid_enum_value:
            message = `无效的选项，期望 ${issue.options.map((v) => `"${v}"`).join(" | ")}`;
            break;
        case ZodIssueCode.invalid_arguments:
            message = "无效的函数参数";
            break;
        case ZodIssueCode.invalid_return_type:
            message = "无效的返回类型";
            break;
        case ZodIssueCode.invalid_date:
            message = "无效的日期";
            break;
        case ZodIssueCode.invalid_string:
            if (typeof issue.validation === "object") {
                if ("includes" in issue.validation) {
                    message = `必须包含 "${issue.validation.includes}"`;
                } else if ("startsWith" in issue.validation) {
                    message = `必须以 "${issue.validation.startsWith}" 开头`;
                } else if ("endsWith" in issue.validation) {
                    message = `必须以 "${issue.validation.endsWith}" 结尾`;
                } else {
                    message = "格式不正确";
                }
            } else if (issue.validation === "email") {
                message = "邮箱格式不正确";
            } else if (issue.validation === "url") {
                message = "URL 格式不正确";
            } else if (issue.validation === "uuid") {
                message = "UUID 格式不正确";
            } else if (issue.validation === "regex") {
                message = "格式不正确";
            } else {
                message = "格式不正确";
            }
            break;
        case ZodIssueCode.too_small:
            if (issue.type === "string") {
                message = issue.minimum === 1 ? "必填项" : `至少 ${issue.minimum} 个字符`;
            } else if (issue.type === "number") {
                message = issue.inclusive ? `不能小于 ${issue.minimum}` : `必须大于 ${issue.minimum}`;
            } else if (issue.type === "array") {
                message = issue.minimum === 1 ? "至少选择一项" : `至少 ${issue.minimum} 项`;
            } else {
                message = "值过小";
            }
            break;
        case ZodIssueCode.too_big:
            if (issue.type === "string") {
                message = `最多 ${issue.maximum} 个字符`;
            } else if (issue.type === "number") {
                message = issue.inclusive ? `不能大于 ${issue.maximum}` : `必须小于 ${issue.maximum}`;
            } else if (issue.type === "array") {
                message = `最多 ${issue.maximum} 项`;
            } else {
                message = "值过大";
            }
            break;
        case ZodIssueCode.invalid_intersection_types:
            message = "交叉类型合并失败";
            break;
        case ZodIssueCode.not_multiple_of:
            message = `必须是 ${issue.multipleOf} 的倍数`;
            break;
        case ZodIssueCode.not_finite:
            message = "必须为有限数字";
            break;
        case ZodIssueCode.custom:
            message = "输入不正确";
            break;
        default:
            message = ctx.defaultError;
    }

    return { message };
};

z.setErrorMap(zhCNErrorMap);
 