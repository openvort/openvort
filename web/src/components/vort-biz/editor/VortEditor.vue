<script setup lang="ts">
import { watch, onBeforeUnmount } from "vue";
import { useEditor, EditorContent } from "@tiptap/vue-3";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import BaseImage from "@tiptap/extension-image";
import { Markdown } from "tiptap-markdown";
import MarkdownIt from "markdown-it";

const mdIt = MarkdownIt();
const MD_PATTERN = /^#{1,6}\s|^\s*[-*+]\s|^\s*\d+\.\s|^\s*>/m;

const Image = BaseImage.extend({
    addStorage() {
        return {
            ...this.parent?.(),
            markdown: {
                serialize(state: any, node: any) {
                    const src = node.attrs?.src ?? "";
                    const alt = node.attrs?.alt ?? "";
                    const title = node.attrs?.title ?? "";
                    const width = node.attrs?.width;
                    const height = node.attrs?.height;
                    if (width || height) {
                        const parts = [`src="${src}"`, `alt="${alt}"`];
                        if (title) parts.push(`title="${title}"`);
                        if (width) parts.push(`width="${width}"`);
                        if (height) parts.push(`height="${height}"`);
                        state.write(`<img ${parts.join(" ")} />`);
                        state.closeBlock(node);
                    } else {
                        state.write(
                            `![${state.esc(alt)}](${src}${title ? ` "${title.replace(/"/g, '\\"')}"` : ""})`
                        );
                        state.closeBlock(node);
                    }
                },
                parse: {},
            },
        };
    },
});
import {
    Bold, Italic, Strikethrough, Code, Heading1, Heading2, Heading3,
    List, ListOrdered, Quote, Minus, Undo2, Redo2, CodeSquare,
} from "lucide-vue-next";

const props = withDefaults(defineProps<{
    modelValue?: string;
    placeholder?: string;
    minHeight?: string;
    readonly?: boolean;
}>(), {
    modelValue: "",
    placeholder: "请输入内容...",
    minHeight: "160px",
    readonly: false,
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
}>();

const insertImageFromFile = async (file: File) => {
    if (!file.type.startsWith("image/")) return;
    try {
        const { uploadEditorImage } = await import("@/api/uploads");
        const res: any = await uploadEditorImage(file);
        if (res?.success && res.url) {
            editor.value?.chain().focus().setImage({ src: res.url, alt: file.name || "image" }).run();
        } else {
            console.error("[VortEditor] 上传失败:", res?.error || "unknown");
        }
    } catch (error) {
        console.error("[VortEditor] 上传图片失败:", error);
    }
};

const editor = useEditor({
    content: props.modelValue || "",
    editable: !props.readonly,
    extensions: [
        StarterKit,
        Image.configure({
            inline: false,
            allowBase64: true,
            HTMLAttributes: { class: "vort-editor-image" },
            resize: {
                enabled: true,
                directions: [
                    "top-left", "top", "top-right",
                    "left", "right",
                    "bottom-left", "bottom", "bottom-right",
                ],
                minWidth: 50,
                minHeight: 50,
                alwaysPreserveAspectRatio: true,
            },
        }),
        Markdown.configure({
            transformPastedText: true,
            transformCopiedText: true,
        }),
        Placeholder.configure({ placeholder: props.placeholder }),
    ],
    editorProps: {
        handlePaste(_view, event) {
            const clipboardData = event.clipboardData;
            if (!clipboardData) return false;

            const files = Array.from(clipboardData.files || []).filter((f) => f.type.startsWith("image/"));
            if (files.length > 0) {
                event.preventDefault();
                files.forEach((file) => {
                    void insertImageFromFile(file);
                });
                return true;
            }

            const text = clipboardData.getData("text/plain");
            if (text && MD_PATTERN.test(text)) {
                const ed = editor.value;
                if (ed) {
                    event.preventDefault();
                    const html = mdIt.render(text);
                    ed.chain().focus().insertContent(html).run();
                    return true;
                }
            }

            return false;
        },
        handleDrop(_view, event, _slice, moved) {
            if (moved) return false;
            const files = Array.from(event.dataTransfer?.files || []).filter((f) => f.type.startsWith("image/"));
            if (files.length === 0) return false;
            event.preventDefault();
            files.forEach((file) => {
                void insertImageFromFile(file);
            });
            return true;
        },
    },
    onUpdate: ({ editor: e }) => {
        const md = e.storage.markdown.getMarkdown();
        emit("update:modelValue", md);
    },
});

watch(() => props.modelValue, (val) => {
    const ed = editor.value;
    if (!ed) return;
    const current = ed.storage.markdown.getMarkdown();
    if (val !== current) {
        ed.commands.setContent(val || "");
    }
});

watch(() => props.readonly, (val) => {
    editor.value?.setEditable(!val);
});

onBeforeUnmount(() => {
    editor.value?.destroy();
});

interface ToolItem {
    icon: any;
    title: string;
    action: () => void;
    isActive?: () => boolean;
    type?: "button" | "divider";
}

const toolbarItems: ToolItem[] = [
    { icon: Bold, title: "加粗", action: () => editor.value?.chain().focus().toggleBold().run(), isActive: () => !!editor.value?.isActive("bold") },
    { icon: Italic, title: "斜体", action: () => editor.value?.chain().focus().toggleItalic().run(), isActive: () => !!editor.value?.isActive("italic") },
    { icon: Strikethrough, title: "删除线", action: () => editor.value?.chain().focus().toggleStrike().run(), isActive: () => !!editor.value?.isActive("strike") },
    { icon: Code, title: "行内代码", action: () => editor.value?.chain().focus().toggleCode().run(), isActive: () => !!editor.value?.isActive("code") },
    { type: "divider", icon: null, title: "", action: () => {} },
    { icon: Heading1, title: "标题 1", action: () => editor.value?.chain().focus().toggleHeading({ level: 1 }).run(), isActive: () => !!editor.value?.isActive("heading", { level: 1 }) },
    { icon: Heading2, title: "标题 2", action: () => editor.value?.chain().focus().toggleHeading({ level: 2 }).run(), isActive: () => !!editor.value?.isActive("heading", { level: 2 }) },
    { icon: Heading3, title: "标题 3", action: () => editor.value?.chain().focus().toggleHeading({ level: 3 }).run(), isActive: () => !!editor.value?.isActive("heading", { level: 3 }) },
    { type: "divider", icon: null, title: "", action: () => {} },
    { icon: List, title: "无序列表", action: () => editor.value?.chain().focus().toggleBulletList().run(), isActive: () => !!editor.value?.isActive("bulletList") },
    { icon: ListOrdered, title: "有序列表", action: () => editor.value?.chain().focus().toggleOrderedList().run(), isActive: () => !!editor.value?.isActive("orderedList") },
    { icon: Quote, title: "引用", action: () => editor.value?.chain().focus().toggleBlockquote().run(), isActive: () => !!editor.value?.isActive("blockquote") },
    { icon: CodeSquare, title: "代码块", action: () => editor.value?.chain().focus().toggleCodeBlock().run(), isActive: () => !!editor.value?.isActive("codeBlock") },
    { icon: Minus, title: "分隔线", action: () => editor.value?.chain().focus().setHorizontalRule().run() },
    { type: "divider", icon: null, title: "", action: () => {} },
    { icon: Undo2, title: "撤销", action: () => editor.value?.chain().focus().undo().run() },
    { icon: Redo2, title: "重做", action: () => editor.value?.chain().focus().redo().run() },
];
</script>

<template>
    <div class="vort-editor" :class="{ 'vort-editor--readonly': readonly }">
        <div v-if="!readonly && editor" class="vort-editor__toolbar">
            <template v-for="(item, idx) in toolbarItems" :key="idx">
                <div v-if="item.type === 'divider'" class="vort-editor__toolbar-divider" />
                <button
                    v-else
                    type="button"
                    class="vort-editor__toolbar-btn"
                    :class="{ 'is-active': item.isActive?.() }"
                    :title="item.title"
                    @click="item.action"
                >
                    <component :is="item.icon" :size="15" />
                </button>
            </template>
        </div>
        <EditorContent :editor="editor" class="vort-editor__content" :style="{ minHeight }" @click="editor?.commands.focus()" />
    </div>
</template>

<style>
.vort-editor {
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
    transition: border-color 0.2s;
}
.vort-editor:focus-within {
    border-color: var(--vort-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}
.vort-editor--readonly {
    border-color: transparent;
    background: transparent;
}
.vort-editor--readonly:focus-within {
    border-color: transparent;
    box-shadow: none;
}

.vort-editor__toolbar {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 6px 8px;
    border-bottom: 1px solid #f0f0f0;
    background: #fafafa;
    flex-wrap: wrap;
}
.vort-editor__toolbar-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    background: transparent;
    color: #595959;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
}
.vort-editor__toolbar-btn:hover {
    background: #e6e6e6;
    color: #262626;
}
.vort-editor__toolbar-btn.is-active {
    background: #e0edff;
    color: #3b82f6;
}
.vort-editor__toolbar-divider {
    width: 1px;
    height: 18px;
    background: #e5e5e5;
    margin: 0 4px;
}

.vort-editor__content {
    display: flex;
    flex-direction: column;
    cursor: text;
}
.vort-editor__content .tiptap {
    padding: 12px 14px;
    outline: none;
    font-size: 14px;
    line-height: 1.7;
    color: #262626;
    flex: 1;
    min-height: inherit;
}
.vort-editor__content .tiptap p.is-editor-empty:first-child::before {
    content: attr(data-placeholder);
    float: left;
    color: #bfbfbf;
    pointer-events: none;
    height: 0;
}

.vort-editor__content .tiptap h1 { font-size: 1.5em; font-weight: 700; margin: 0.67em 0; }
.vort-editor__content .tiptap h2 { font-size: 1.25em; font-weight: 600; margin: 0.5em 0; }
.vort-editor__content .tiptap h3 { font-size: 1.1em; font-weight: 600; margin: 0.4em 0; }
.vort-editor__content .tiptap ul { list-style: disc; padding-left: 1.5em; }
.vort-editor__content .tiptap ol { list-style: decimal; padding-left: 1.5em; }
.vort-editor__content .tiptap li { margin: 0.15em 0; }
.vort-editor__content .tiptap blockquote {
    border-left: 3px solid #d9d9d9;
    padding-left: 12px;
    margin: 0.5em 0;
    color: #8c8c8c;
}
.vort-editor__content .tiptap code {
    background: #f5f5f5;
    padding: 0.15em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
    color: #d63384;
}
.vort-editor__content .tiptap pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 0.5em 0;
}
.vort-editor__content .tiptap pre code {
    background: none;
    color: inherit;
    padding: 0;
    border-radius: 0;
    font-size: 0.875em;
}
.vort-editor__content .tiptap hr {
    border: none;
    border-top: 1px solid #e5e5e5;
    margin: 1em 0;
}
.vort-editor__content .tiptap img,
.vort-editor__content .tiptap .vort-editor-image {
    display: block;
    max-width: 100%;
    height: auto;
    margin: 8px 0;
    border-radius: 6px;
}
.vort-editor__content .tiptap strong { font-weight: 700; }
.vort-editor__content .tiptap em { font-style: italic; }
.vort-editor__content .tiptap s { text-decoration: line-through; }

[data-resize-wrapper] {
    display: inline-block;
    max-width: 100%;
    border: 1px solid transparent;
    border-radius: 3px;
    transition: border-color 0.15s;
}
[data-resize-wrapper]:hover,
[data-resize-wrapper].resizing {
    border-color: #3b82f6;
}
[data-resize-wrapper]:hover [data-resize-handle],
[data-resize-wrapper].resizing [data-resize-handle] {
    opacity: 1;
}
[data-resize-handle] {
    width: 8px;
    height: 8px;
    background: #fff;
    border: 1.5px solid #3b82f6;
    border-radius: 50%;
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 10;
    transform: translate(-50%, -50%);
}
[data-resize-handle="top-left"]     { cursor: nwse-resize; top: 0 !important; left: 0 !important; right: auto !important; bottom: auto !important; }
[data-resize-handle="top"]          { cursor: ns-resize;   top: 0 !important; left: 50% !important; right: auto !important; bottom: auto !important; }
[data-resize-handle="top-right"]    { cursor: nesw-resize; top: 0 !important; right: 0 !important; left: auto !important; bottom: auto !important; transform: translate(50%, -50%); }
[data-resize-handle="left"]         { cursor: ew-resize;   top: 50% !important; left: 0 !important; right: auto !important; bottom: auto !important; }
[data-resize-handle="right"]        { cursor: ew-resize;   top: 50% !important; right: 0 !important; left: auto !important; bottom: auto !important; transform: translate(50%, -50%); }
[data-resize-handle="bottom-left"]  { cursor: nesw-resize; bottom: 0 !important; left: 0 !important; right: auto !important; top: auto !important; transform: translate(-50%, 50%); }
[data-resize-handle="bottom"]       { cursor: ns-resize;   bottom: 0 !important; left: 50% !important; right: auto !important; top: auto !important; transform: translate(-50%, 50%); }
[data-resize-handle="bottom-right"] { cursor: nwse-resize; bottom: 0 !important; right: 0 !important; left: auto !important; top: auto !important; transform: translate(50%, 50%); }
</style>
