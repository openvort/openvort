import { ref, computed, watch, nextTick, type Ref } from "vue";
import type { MentionMember, SlashCommand, HashTagCategory, HashTagItem } from "../types";
import { getChatMembers, getVortflowBugs, getVortflowTasks, getVortflowStories, getVortflowMilestones } from "@/api";
import { pinyin } from "pinyin-pro";

const slashCommands: SlashCommand[] = [
    { name: "/new", label: "/new", description: "重置上下文" },
    { name: "/status", label: "/status", description: "查看会话状态" },
    { name: "/compact", label: "/compact", description: "压缩上下文" },
    { name: "/think", label: "/think", description: "设置思考级别 (off|low|medium|high)" },
    { name: "/usage", label: "/usage", description: "设置用量显示 (off|tokens|full)" },
    { name: "/help", label: "/help", description: "显示帮助" },
];

const allHashTagCategories: HashTagCategory[] = [
    { key: 'bug', label: '#bug', description: '缺陷跟踪', plugin: 'vortflow' },
    { key: 'task', label: '#task', description: '任务管理', plugin: 'vortflow' },
    { key: 'story', label: '#story', description: '需求列表', plugin: 'vortflow' },
    { key: 'milestone', label: '#milestone', description: '里程碑', plugin: 'vortflow' },
];

interface UseChatMentionsOptions {
    inputText: Ref<string>;
    pluginStore: { extensions: ReadonlyArray<{ plugin: string }> };
}

export function useChatMentions(options: UseChatMentionsOptions) {
    const { inputText, pluginStore } = options;

    const showMentionPanel = ref(false);
    const showCommandPanel = ref(false);
    const showHashTagPanel = ref(false);
    const mentionMembers = ref<MentionMember[]>([]);
    const filteredCommands = ref<SlashCommand[]>([]);
    const mentionActiveIndex = ref(0);
    const commandActiveIndex = ref(0);
    const hashTagActiveIndex = ref(0);
    const mentionQuery = ref("");
    const commandQuery = ref("");
    const hashTagQuery = ref("");
    const panelStyle = ref({ left: '0px' });
    let mentionStartPos = -1;
    let hashTagStartPos = -1;

    const hashTagLevel = ref<'category' | 'items'>('category');
    const hashTagSelectedCategory = ref<HashTagCategory | null>(null);
    const hashTagItems = ref<HashTagItem[]>([]);
    const hashTagItemsLoading = ref(false);

    const allMembers = ref<MentionMember[]>([]);
    let allMembersLoaded = false;

    const availableHashTagCategories = computed(() => {
        const enabledPlugins = new Set(pluginStore.extensions.map(e => e.plugin));
        return allHashTagCategories.filter(c => enabledPlugins.has(c.plugin));
    });

    const filteredHashTagCategories = computed(() => {
        if (!hashTagQuery.value) return availableHashTagCategories.value;
        const kw = hashTagQuery.value.toLowerCase();
        return availableHashTagCategories.value.filter(
            c => c.key.includes(kw) || c.label.includes(kw) || c.description.includes(kw)
        );
    });

    const filteredHashTagItems = computed(() => {
        if (!hashTagQuery.value) return hashTagItems.value;
        const kw = hashTagQuery.value.toLowerCase();
        return hashTagItems.value.filter(
            item => item.id.toLowerCase().includes(kw) || item.title.toLowerCase().includes(kw)
        );
    });

    const hashTagDisplayList = computed(() => {
        if (hashTagLevel.value === 'category') return filteredHashTagCategories.value;
        return filteredHashTagItems.value;
    });

    const isAnyPanelOpen = computed(() => showMentionPanel.value || showCommandPanel.value || showHashTagPanel.value);

    async function ensureMembersLoaded() {
        if (allMembersLoaded) return;
        try {
            const res: any = await getChatMembers("", 200);
            allMembers.value = res?.members || [];
            allMembersLoaded = true;
        } catch { /* ignore */ }
    }

    function matchPinyin(name: string, keyword: string): boolean {
        if (!keyword) return true;
        const kw = keyword.toLowerCase();

        if (name.toLowerCase().includes(kw)) return true;

        const fullPy = pinyin(name, { toneType: 'none', type: 'array' }).join('').toLowerCase();
        if (fullPy.includes(kw)) return true;

        const initialsArr = pinyin(name, { pattern: 'first', type: 'array', multiple: true });
        const combos = initialsArr.reduce<string[]>((acc, cur) => {
            const curOptions = typeof cur === 'string' ? cur.split(' ') : [cur];
            if (acc.length === 0) return curOptions.map(o => o.toLowerCase());
            const result: string[] = [];
            for (const prefix of acc) {
                for (const opt of curOptions) {
                    result.push(prefix + opt.toLowerCase());
                }
            }
            return result;
        }, []);

        return combos.some(c => c.includes(kw));
    }

    function filterMembersByKeyword(keyword: string): MentionMember[] {
        if (!keyword) return allMembers.value.slice(0, 20);
        return allMembers.value.filter(m =>
            matchPinyin(m.name, keyword) ||
            (m.email && m.email.toLowerCase().includes(keyword.toLowerCase()))
        ).slice(0, 20);
    }

    async function searchMembers(keyword: string) {
        await ensureMembersLoaded();
        mentionMembers.value = filterMembersByKeyword(keyword);
        mentionActiveIndex.value = 0;
        showMentionPanel.value = mentionMembers.value.length > 0;
    }

    function updatePanelPosition() {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        const container = document.querySelector('.relative.px-6') as HTMLElement;
        if (!textarea || !container) return;

        const mirror = document.createElement('div');
        const style = window.getComputedStyle(textarea);
        const mirrorProps = [
            'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing',
            'wordSpacing', 'textIndent', 'whiteSpace', 'wordWrap', 'overflowWrap',
            'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
            'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
            'boxSizing', 'width',
        ];
        mirror.style.position = 'absolute';
        mirror.style.visibility = 'hidden';
        mirror.style.overflow = 'hidden';
        for (const prop of mirrorProps) {
            (mirror.style as any)[prop] = style.getPropertyValue(prop.replace(/([A-Z])/g, '-$1').toLowerCase());
        }
        document.body.appendChild(mirror);

        const text = textarea.value.substring(0, textarea.selectionStart);
        mirror.textContent = text;
        const span = document.createElement('span');
        span.textContent = '|';
        mirror.appendChild(span);

        const textareaRect = textarea.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const spanRect = span.getBoundingClientRect();
        const mirrorRect = mirror.getBoundingClientRect();

        document.body.removeChild(mirror);

        const cursorLeft = textareaRect.left + (spanRect.left - mirrorRect.left) - textarea.scrollLeft;
        const relativeLeft = Math.max(0, cursorLeft - containerRect.left);

        panelStyle.value = { left: `${relativeLeft}px` };
    }

    function closeAllPanels() {
        showMentionPanel.value = false;
        showCommandPanel.value = false;
        showHashTagPanel.value = false;
        hashTagLevel.value = 'category';
        hashTagSelectedCategory.value = null;
    }

    function filterCommandsByKeyword(keyword: string) {
        const kw = keyword.toLowerCase();
        filteredCommands.value = slashCommands.filter(
            c => c.name.toLowerCase().includes(kw) || c.description.includes(kw)
        );
        showCommandPanel.value = filteredCommands.value.length > 0;
    }

    function handleInput() {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (!textarea) return;

        const cursorPos = textarea.selectionStart;
        const text = textarea.value;
        const textBeforeCursor = text.substring(0, cursorPos);

        const atMatch = textBeforeCursor.match(/@([^\s@]*)$/);
        if (atMatch) {
            mentionStartPos = cursorPos - atMatch[1].length - 1;
            mentionQuery.value = atMatch[1];
            mentionActiveIndex.value = 0;
            showCommandPanel.value = false;
            showHashTagPanel.value = false;
            updatePanelPosition();
            searchMembers(atMatch[1]);
            return;
        }

        if (availableHashTagCategories.value.length > 0) {
            const hashMatch = textBeforeCursor.match(/#([^\s#]*)$/);
            if (hashMatch) {
                hashTagStartPos = cursorPos - hashMatch[1].length - 1;
                showMentionPanel.value = false;
                showCommandPanel.value = false;

                const rawQuery = hashMatch[1];
                const slashIdx = rawQuery.indexOf('/');
                if (slashIdx >= 0) {
                    const catKey = rawQuery.substring(0, slashIdx);
                    const itemQuery = rawQuery.substring(slashIdx + 1);
                    const cat = availableHashTagCategories.value.find(c => c.key === catKey);
                    if (cat) {
                        if (hashTagSelectedCategory.value?.key !== cat.key) {
                            hashTagSelectedCategory.value = cat;
                            hashTagLevel.value = 'items';
                            loadHashTagItems(cat.key);
                        }
                        hashTagQuery.value = itemQuery;
                        hashTagActiveIndex.value = 0;
                        showHashTagPanel.value = true;
                        updatePanelPosition();
                        return;
                    }
                }

                const exactCat = availableHashTagCategories.value.find(c => c.key === rawQuery);
                if (exactCat && hashTagLevel.value === 'category') {
                    hashTagSelectedCategory.value = exactCat;
                    hashTagLevel.value = 'items';
                    hashTagQuery.value = '';
                    hashTagActiveIndex.value = 0;
                    showHashTagPanel.value = true;
                    updatePanelPosition();
                    loadHashTagItems(exactCat.key);
                    return;
                }

                if (hashTagLevel.value !== 'items') {
                    hashTagLevel.value = 'category';
                    hashTagSelectedCategory.value = null;
                }
                hashTagQuery.value = rawQuery;
                hashTagActiveIndex.value = 0;
                showHashTagPanel.value = hashTagDisplayList.value.length > 0 || hashTagLevel.value === 'items';
                updatePanelPosition();
                return;
            }
        }

        const slashMatch = textBeforeCursor.match(/^\/(\S*)$/);
        if (slashMatch) {
            commandQuery.value = slashMatch[1];
            commandActiveIndex.value = 0;
            showMentionPanel.value = false;
            showHashTagPanel.value = false;
            updatePanelPosition();
            filterCommandsByKeyword(slashMatch[1]);
            return;
        }

        closeAllPanels();
    }

    // Trigger handleInput on inputText changes
    watch(inputText, () => {
        nextTick(() => handleInput());
    });

    function selectMention(member: MentionMember) {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (!textarea) return;

        const before = inputText.value.substring(0, mentionStartPos);
        const after = inputText.value.substring(textarea.selectionStart);
        inputText.value = before + `@${member.name} ` + after;
        showMentionPanel.value = false;

        nextTick(() => {
            const newPos = mentionStartPos + member.name.length + 2;
            textarea.selectionStart = textarea.selectionEnd = newPos;
            textarea.focus();
        });
    }

    function selectCommand(cmd: SlashCommand) {
        inputText.value = cmd.name + " ";
        showCommandPanel.value = false;

        nextTick(() => {
            const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
            if (textarea) {
                textarea.selectionStart = textarea.selectionEnd = inputText.value.length;
                textarea.focus();
            }
        });
    }

    async function loadHashTagItems(categoryKey: string) {
        hashTagItemsLoading.value = true;
        hashTagItems.value = [];
        try {
            let res: any;
            switch (categoryKey) {
                case 'bug':
                    res = await getVortflowBugs({ page: 1, page_size: 20 });
                    hashTagItems.value = (res?.items || res?.bugs || []).map((b: any) => ({
                        id: b.id || b.bug_id, title: b.title, state: b.state, priority: b.severity, category: 'bug'
                    }));
                    break;
                case 'task':
                    res = await getVortflowTasks({ page: 1, page_size: 20 });
                    hashTagItems.value = (res?.items || res?.tasks || []).map((t: any) => ({
                        id: t.id || t.task_id, title: t.title, state: t.state, category: 'task'
                    }));
                    break;
                case 'story':
                    res = await getVortflowStories({ page: 1, page_size: 20 });
                    hashTagItems.value = (res?.items || res?.stories || []).map((s: any) => ({
                        id: s.id || s.story_id, title: s.title, state: s.state, priority: s.priority, category: 'story'
                    }));
                    break;
                case 'milestone':
                    res = await getVortflowMilestones({ page: 1, page_size: 20 });
                    hashTagItems.value = (res?.items || res?.milestones || []).map((m: any) => ({
                        id: m.id || m.milestone_id, title: m.name || m.title, state: m.status, category: 'milestone'
                    }));
                    break;
            }
        } catch { /* ignore */ }
        hashTagItemsLoading.value = false;
    }

    function selectHashTagCategory(cat: HashTagCategory) {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (!textarea) return;

        const before = inputText.value.substring(0, hashTagStartPos);
        const after = inputText.value.substring(textarea.selectionStart);
        inputText.value = before + `#${cat.key}/` + after;
        hashTagSelectedCategory.value = cat;
        hashTagLevel.value = 'items';
        hashTagQuery.value = '';
        hashTagActiveIndex.value = 0;
        loadHashTagItems(cat.key);

        nextTick(() => {
            const newPos = hashTagStartPos + cat.key.length + 2;
            textarea.selectionStart = textarea.selectionEnd = newPos;
            textarea.focus();
        });
    }

    function selectHashTagItem(item: HashTagItem) {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (!textarea) return;

        const before = inputText.value.substring(0, hashTagStartPos);
        const after = inputText.value.substring(textarea.selectionStart);
        const tag = `#${item.category}/${item.title}#id:${item.id} `;
        inputText.value = before + tag + after;
        closeAllPanels();

        nextTick(() => {
            const newPos = hashTagStartPos + tag.length;
            textarea.selectionStart = textarea.selectionEnd = newPos;
            textarea.focus();
        });
    }

    function scrollActiveItemIntoView(type: 'mention' | 'command' | 'hashtag') {
        nextTick(() => {
            const attr = type === 'mention' ? 'data-mention-index' : type === 'command' ? 'data-command-index' : 'data-hashtag-index';
            const idx = type === 'mention' ? mentionActiveIndex.value : type === 'command' ? commandActiveIndex.value : hashTagActiveIndex.value;
            const el = document.querySelector(`[${attr}="${idx}"]`) as HTMLElement;
            if (el) el.scrollIntoView({ block: 'nearest' });
        });
    }

    function handlePanelKeydown(e: KeyboardEvent) {
        if (showMentionPanel.value) {
            const list = mentionMembers.value;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                mentionActiveIndex.value = (mentionActiveIndex.value + 1) % list.length;
                scrollActiveItemIntoView('mention');
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                mentionActiveIndex.value = (mentionActiveIndex.value - 1 + list.length) % list.length;
                scrollActiveItemIntoView('mention');
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                e.stopPropagation();
                if (list[mentionActiveIndex.value]) selectMention(list[mentionActiveIndex.value]);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                showMentionPanel.value = false;
            }
            return true;
        }
        if (showCommandPanel.value) {
            const list = filteredCommands.value;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                commandActiveIndex.value = (commandActiveIndex.value + 1) % list.length;
                scrollActiveItemIntoView('command');
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                commandActiveIndex.value = (commandActiveIndex.value - 1 + list.length) % list.length;
                scrollActiveItemIntoView('command');
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                e.stopPropagation();
                if (list[commandActiveIndex.value]) selectCommand(list[commandActiveIndex.value]);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                showCommandPanel.value = false;
            }
            return true;
        }
        if (showHashTagPanel.value) {
            const list = hashTagDisplayList.value;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                hashTagActiveIndex.value = (hashTagActiveIndex.value + 1) % (list.length || 1);
                scrollActiveItemIntoView('hashtag');
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                hashTagActiveIndex.value = (hashTagActiveIndex.value - 1 + (list.length || 1)) % (list.length || 1);
                scrollActiveItemIntoView('hashtag');
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                e.stopPropagation();
                if (hashTagLevel.value === 'category') {
                    const cat = filteredHashTagCategories.value[hashTagActiveIndex.value];
                    if (cat) selectHashTagCategory(cat as HashTagCategory);
                } else {
                    const item = filteredHashTagItems.value[hashTagActiveIndex.value];
                    if (item) selectHashTagItem(item as HashTagItem);
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                if (hashTagLevel.value === 'items') {
                    hashTagLevel.value = 'category';
                    hashTagSelectedCategory.value = null;
                    hashTagQuery.value = '';
                    hashTagActiveIndex.value = 0;
                    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
                    if (textarea) {
                        const before = inputText.value.substring(0, hashTagStartPos);
                        const after = inputText.value.substring(textarea.selectionStart);
                        inputText.value = before + '#' + after;
                        nextTick(() => {
                            textarea.selectionStart = textarea.selectionEnd = hashTagStartPos + 1;
                            textarea.focus();
                        });
                    }
                } else {
                    showHashTagPanel.value = false;
                }
            } else if (e.key === 'Backspace' && hashTagLevel.value === 'items' && !hashTagQuery.value) {
                e.preventDefault();
                hashTagLevel.value = 'category';
                hashTagSelectedCategory.value = null;
                const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
                if (textarea) {
                    const before = inputText.value.substring(0, hashTagStartPos);
                    const after = inputText.value.substring(textarea.selectionStart);
                    inputText.value = before + '#' + after;
                    nextTick(() => {
                        textarea.selectionStart = textarea.selectionEnd = hashTagStartPos + 1;
                        textarea.focus();
                    });
                }
            }
            return true;
        }
        return false;
    }

    function handleClickOutsidePanel(e: MouseEvent) {
        const target = e.target as HTMLElement;
        if (!target.closest('.mention-panel') && !target.closest('.chat-textarea')) {
            closeAllPanels();
        }
    }

    return {
        showMentionPanel,
        showCommandPanel,
        showHashTagPanel,
        mentionMembers,
        filteredCommands,
        mentionActiveIndex,
        commandActiveIndex,
        hashTagActiveIndex,
        panelStyle,
        hashTagLevel,
        hashTagSelectedCategory,
        hashTagItems,
        hashTagItemsLoading,
        filteredHashTagCategories,
        filteredHashTagItems,
        selectMention,
        selectCommand,
        selectHashTagCategory,
        selectHashTagItem,
        hashTagQuery,
        handlePanelKeydown,
        closeAllPanels,
        isAnyPanelOpen,
        handleClickOutsidePanel,
    };
}
