<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from "vue";
import { pinyin } from "pinyin-pro";
import { message } from "@openvort/vort-ui";
import { DownOutlined } from "@openvort/vort-ui";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemPriority from "@/components/vort-biz/work-item/WorkItemPriority.vue";
import WorkItemTagPicker from "@/components/vort-biz/work-item/WorkItemTagPicker.vue";
import {
    getVortflowProjects,
    getVortflowStories,
    getVortgitRepos,
    getVortgitRepoBranches,
    getVortflowIterations,
    getVortflowVersions,
    getVortflowDescriptionTemplates,
    getVortflowTags,
    uploadVortflowFile,
} from "@/api";
import { useWorkItemCommon } from "./useWorkItemCommon";
import { formatFileSize } from "@/utils/format";
import type { WorkItemType, Priority, DateRange, NewBugForm, RowItem, AttachmentItem } from "@/components/vort-biz/work-item/WorkItemTable.types";

interface Props {
    type?: WorkItemType;
    title?: string;
    useApi?: boolean;
    projectId?: string;
    parentId?: string;
    parentRecord?: RowItem | null;
    iterationId?: string;
    initialDraft?: NewBugForm | null;
}

const props = withDefaults(defineProps<Props>(), {
    type: "缺陷",
    title: "新建缺陷",
    useApi: false,
    projectId: "",
    parentId: "",
    iterationId: "",
    initialDraft: null,
});

const emit = defineEmits<{
    close: [];
    success: [data: any];
}>();

const {
    priorityOptions,
    priorityLabelMap,
    priorityClassMap,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    ownerGroups,
    getMemberNameById,
    getWorkItemTypeIconClass,
    getWorkItemTypeIcon,
} = useWorkItemCommon();

const FALLBACK_TEMPLATES: Record<WorkItemType, string> = {
    "需求": "",
    "任务": "",
    "缺陷": "",
};

const remoteTemplates = ref<Record<string, string>>({});

const getDescriptionTemplate = (type: WorkItemType): string => {
    if (remoteTemplates.value[type] !== undefined && remoteTemplates.value[type] !== "") {
        return remoteTemplates.value[type];
    }
    return FALLBACK_TEMPLATES[type] ?? "";
};

const todayStr = (): string => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
};

const createInitialBugForm = (): NewBugForm => ({
    title: "",
    owner: "",
    collaborators: [],
    type: props.type,
    planTime: [],
    project: "VortMall",
    projectId: props.projectId || "",
    iteration: "",
    version: "",
    parentId: props.parentId || "",
    storyId: "",
    priority: "" as any,
    tags: [],
    attachments: [],
    repo: "",
    branch: "",
    startAt: "",
    endAt: "",
    remark: "",
    description: getDescriptionTemplate(props.type)
});

// Iteration prop wins over draft value, so switching sidebar iteration before
// reopening the create drawer always reflects the current iteration context.
const resolveInitialIteration = (draftIteration?: string): string => {
    if (props.iterationId && props.iterationId !== "__unplanned__") {
        return props.iterationId;
    }
    return draftIteration || "";
};

const mergeDraftIntoForm = (draft: NewBugForm): NewBugForm => ({
    ...createInitialBugForm(),
    ...draft,
    projectId: props.projectId || draft.projectId || "",
    parentId: props.parentId || draft.parentId || "",
    iteration: resolveInitialIteration(draft.iteration),
});

const createBugForm = reactive<NewBugForm>(
    props.initialDraft ? mergeDraftIntoForm(props.initialDraft) : createInitialBugForm()
);

const createBugPriorityDropdownOpen = ref(false);
const createAssigneeDropdownOpen = ref(false);
const createAssigneeKeyword = ref("");
const createTagDropdownOpen = ref(false);
const createTagKeyword = ref("");
const attachmentUploading = ref(false);
const attachmentInputRef = ref<HTMLInputElement | null>(null);

const triggerAttachmentInput = () => attachmentInputRef.value?.click();

const handleAttachmentFiles = async (e: Event) => {
    const files = (e.target as HTMLInputElement).files;
    if (!files || files.length === 0) return;
    attachmentUploading.value = true;
    try {
        for (const file of Array.from(files)) {
            if (file.size > 20 * 1024 * 1024) {
                message.warning(`文件 ${file.name} 超过 20MB 限制`);
                continue;
            }
            try {
                const res: any = await uploadVortflowFile(file);
                if (res?.error) {
                    message.error(res.error);
                    continue;
                }
                createBugForm.attachments.push({
                    name: res.name || file.name,
                    url: res.url,
                    size: res.size || file.size,
                });
            } catch {
                message.error(`上传 ${file.name} 失败`);
            }
        }
    } finally {
        attachmentUploading.value = false;
        if (attachmentInputRef.value) attachmentInputRef.value.value = "";
    }
};

const removeAttachment = (index: number) => {
    createBugForm.attachments.splice(index, 1);
};

const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const parentStoryOptions = ref<Array<{ id: string; title: string }>>([]);
const apiRepos = ref<Array<{ id: string; name: string }>>([]);
const apiBranches = ref<Array<{ name: string }>>([]);
const apiIterations = ref<Array<{ id: string; name: string; start_date?: string; end_date?: string; owner_id?: string; owner_name?: string }>>([]);
const apiVersions = ref<Array<{ id: string; name: string }>>([]);
const branchLoading = ref(false);

const projectOptions = ["VortMall", "VortAdmin", "VortCMS", "OpenVort"];
const staticIterationOptions = [
    { id: "Sprint 1", name: "Sprint 1" },
    { id: "Sprint 2", name: "Sprint 2" },
    { id: "Sprint 3", name: "Sprint 3" },
];
const staticVersionOptions = [
    { id: "v1.0.0", name: "v1.0.0" },
    { id: "v1.1.0", name: "v1.1.0" },
    { id: "v1.2.0", name: "v1.2.0" },
];
const staticRepoOptions = [
    { id: "frontend", name: "frontend" },
    { id: "backend", name: "backend" },
    { id: "mobile", name: "mobile" },
];
const staticBranchOptions = [
    { name: "main" },
    { name: "develop" },
    { name: "feature/xxx" },
];

const createProjectOptions = computed(() => {
    if (props.useApi && apiProjects.value.length > 0) {
        return apiProjects.value.map((item) => item.name);
    }
    return projectOptions;
});

const repoSelectOptions = computed(() => (props.useApi ? apiRepos.value : staticRepoOptions));
const branchSelectOptions = computed(() => (props.useApi ? apiBranches.value : staticBranchOptions));
const iterationSelectOptions = computed(() => (props.useApi ? apiIterations.value : staticIterationOptions));
const versionSelectOptions = computed(() => (props.useApi ? apiVersions.value : staticVersionOptions));

type MemberSearchMeta = {
    normalizedName: string;
    fullPinyin: string;
    initialsCombos: string[];
};

const memberSearchMetaCache = new Map<string, MemberSearchMeta>();

const getMemberSearchMeta = (name: string): MemberSearchMeta => {
    const cached = memberSearchMetaCache.get(name);
    if (cached) return cached;

    const initialsArr = pinyin(name, { pattern: "first", type: "array", multiple: true });
    const initialsCombos = initialsArr.reduce<string[]>((acc, cur) => {
        const options = String(cur)
            .split(" ")
            .map((item) => item.toLowerCase())
            .filter(Boolean);

        if (acc.length === 0) return options;

        const result: string[] = [];
        for (const prefix of acc) {
            for (const option of options) {
                result.push(prefix + option);
            }
        }
        return result;
    }, []);

    const meta: MemberSearchMeta = {
        normalizedName: name.toLowerCase(),
        fullPinyin: pinyin(name, { toneType: "none", type: "array" }).join("").toLowerCase(),
        initialsCombos
    };
    memberSearchMetaCache.set(name, meta);
    return meta;
};

const getMatchScore = (source: string, keyword: string, exactScore: number, prefixScore: number, includeScore: number): number => {
    if (!source) return 0;
    if (source === keyword) return exactScore;
    if (source.startsWith(keyword)) return prefixScore;
    if (source.includes(keyword)) return includeScore;
    return 0;
};

const getMemberKeywordScore = (name: string, keyword: string): number => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return 1;

    const meta = getMemberSearchMeta(name);

    const directScore = getMatchScore(meta.normalizedName, kw, 120, 110, 80);
    if (directScore > 0) return directScore;

    const fullPinyinScore = getMatchScore(meta.fullPinyin, kw, 100, 95, 60);
    if (fullPinyinScore > 0) return fullPinyinScore;

    let initialsBestScore = 0;
    for (const combo of meta.initialsCombos) {
        initialsBestScore = Math.max(initialsBestScore, getMatchScore(combo, kw, 90, 85, 50));
    }
    return initialsBestScore;
};

const SUGGESTED_OWNER_GROUP_LABEL = "迭代负责人";

const currentIterationOwnerName = computed(() => {
    const iterId = createBugForm.iteration;
    if (!iterId || iterId === "__unplanned__") return "";
    const iter = apiIterations.value.find((item) => item.id === iterId);
    if (!iter) return "";
    if (iter.owner_name) return iter.owner_name;
    return getMemberNameById(iter.owner_id || "") || "";
});

const prioritizedOwnerGroups = computed(() => {
    const suggested = currentIterationOwnerName.value;
    if (!suggested) return ownerGroups.value;
    const baseGroups = ownerGroups.value
        .map((group) => ({
            label: group.label,
            members: group.members.filter((member) => member !== suggested),
        }))
        .filter((group) => group.members.length > 0);
    const hasSuggested = ownerGroups.value.some((group) => group.members.includes(suggested));
    if (!hasSuggested) return ownerGroups.value;
    return [
        { label: SUGGESTED_OWNER_GROUP_LABEL, members: [suggested] },
        ...baseGroups,
    ];
});

const filteredCreateAssigneeGroups = computed(() => {
    const kw = createAssigneeKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members
                .map((member, index) => ({
                    member,
                    index,
                    score: getMemberKeywordScore(member, kw)
                }))
                .filter((item) => item.score > 0)
                .sort((a, b) => b.score - a.score || a.index - b.index)
                .map((item) => item.member)
        }))
        .filter((g) => g.members.length > 0);
});

const isCreateOwner = (member: string): boolean => {
    return createBugForm.owner === member;
};

const isCreateCollaborator = (member: string): boolean => {
    return createBugForm.collaborators.includes(member);
};

const createOwnerDisplayText = computed(() => {
    if (createBugForm.owner) return createBugForm.owner;
    if (createBugForm.collaborators.length > 0) return "无负责人";
    return "指派负责人/协作者";
});

const toggleCreateAssigneeMenu = () => {
    createAssigneeDropdownOpen.value = !createAssigneeDropdownOpen.value;
    if (!createAssigneeDropdownOpen.value) createAssigneeKeyword.value = "";
};

const setCreateOwner = (member: string) => {
    createBugForm.owner = member || "";
    createBugForm.collaborators = createBugForm.collaborators.filter((x) => x !== member);
};

const toggleCreateCollaborator = (member: string) => {
    const list = [...createBugForm.collaborators];
    if (createBugForm.owner === member) {
        createBugForm.owner = "";
        if (!list.includes(member)) list.unshift(member);
        createBugForm.collaborators = list;
        return;
    }
    const idx = list.indexOf(member);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(member);
    }
    createBugForm.collaborators = list;
};

const selectCreateBugPriority = (value: Priority) => {
    createBugForm.priority = value;
    createBugPriorityDropdownOpen.value = false;
};

const toggleCreateBugPriorityMenu = () => {
    createBugPriorityDropdownOpen.value = !createBugPriorityDropdownOpen.value;
};

const tagDefinitions = ref<Array<{ id: string; name: string; color: string }>>([]);
const tagOptions = computed(() => tagDefinitions.value.map((t) => t.name));

const tagColorFallback = ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"];
const getTagColor = (tag: string): string => {
    const def = tagDefinitions.value.find((t) => t.name === tag);
    if (def?.color) return def.color;
    let hash = 0;
    for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
    return tagColorFallback[hash % tagColorFallback.length]!;
};

const loadTagDefinitions = async () => {
    try {
        const res: any = await getVortflowTags();
        tagDefinitions.value = ((res?.items || []) as any[]).map((t) => ({
            id: String(t.id || ""),
            name: String(t.name || ""),
            color: String(t.color || ""),
        })).filter((t) => t.name);
    } catch {
        tagDefinitions.value = [];
    }
};

const filteredTagOptions = computed(() => {
    const kw = createTagKeyword.value.trim();
    if (!kw) return tagOptions.value;
    return tagOptions.value.filter((t) => t.includes(kw));
});

const currentCreateType = computed(() => props.type || createBugForm.type);
const isTaskChildCreate = computed(() => currentCreateType.value === "任务" && Boolean(createBugForm.parentId));

const shouldShowParentSelector = computed(() => {
    return currentCreateType.value === "需求";
});

const shouldShowStorySelector = computed(() => {
    return currentCreateType.value === "缺陷" || (currentCreateType.value === "任务" && !createBugForm.parentId);
});

const storySelectorPlaceholder = computed(() => "选择关联需求（可选）");
const taskParentRecord = computed(() => props.parentRecord || null);

const isStoryOptionValid = (storyId?: string): boolean => {
    if (!storyId) return false;
    return parentStoryOptions.value.some((item) => item.id === storyId);
};

const resolveSelectedProjectId = (): string => {
    if (!apiProjects.value.length) return createBugForm.projectId || props.projectId || "";
    const selected = String(createBugForm.project || "").trim();
    const match = apiProjects.value.find((item) => item.name === selected || item.id === selected);
    if (match) return match.id;
    if (createBugForm.projectId && apiProjects.value.some((item) => item.id === createBugForm.projectId)) {
        return createBugForm.projectId;
    }
    return props.projectId || apiProjects.value[0]?.id || "";
};

const loadApiProjects = async () => {
    if (!props.useApi) return;
    const res: any = await getVortflowProjects();
    apiProjects.value = ((res?.items || []) as any[]).map((item) => ({
        id: String(item.id || ""),
        name: String(item.name || item.id || ""),
    })).filter((item) => item.id && item.name);
    const initialProjectId = props.projectId || createBugForm.projectId || apiProjects.value[0]?.id || "";
    if (!initialProjectId) return;
    const matchedProject = apiProjects.value.find((item) => item.id === initialProjectId) || apiProjects.value[0];
    if (!matchedProject) return;
    createBugForm.projectId = matchedProject.id;
    createBugForm.project = matchedProject.name;
};

const loadParentStoryOptions = async () => {
    if (!props.useApi || (!shouldShowParentSelector.value && !shouldShowStorySelector.value)) {
        parentStoryOptions.value = [];
        createBugForm.storyId = "";
        return;
    }
    const selectedProjectId = resolveSelectedProjectId();
    if (!selectedProjectId) {
        parentStoryOptions.value = [];
        createBugForm.storyId = "";
        return;
    }
    const res: any = await getVortflowStories({
        project_id: selectedProjectId,
        page: 1,
        page_size: 100,
    });
    parentStoryOptions.value = ((res?.items || []) as any[]).map((item) => ({
        id: String(item.id || ""),
        title: String(item.title || item.id || ""),
    })).filter((item) => item.id && item.title);
    if (createBugForm.parentId && !parentStoryOptions.value.some((item) => item.id === createBugForm.parentId)) {
        createBugForm.parentId = "";
    }
    if (createBugForm.storyId && !isStoryOptionValid(createBugForm.storyId)) {
        createBugForm.storyId = "";
    }
};

const loadRepos = async () => {
    if (!props.useApi) return;
    const selectedProjectId = resolveSelectedProjectId();
    if (!selectedProjectId) {
        apiRepos.value = [];
        apiBranches.value = [];
        createBugForm.repo = "";
        createBugForm.branch = "";
        return;
    }
    const res: any = await getVortgitRepos({
        project_id: selectedProjectId,
        page: 1,
        page_size: 100,
    });
    apiRepos.value = ((res?.items || []) as any[])
        .map((item) => ({
            id: String(item.id || ""),
            name: String(item.name || item.full_name || item.id || ""),
        }))
        .filter((item) => item.id && item.name);
    if (createBugForm.repo && !apiRepos.value.some((item) => item.id === createBugForm.repo)) {
        createBugForm.repo = "";
        createBugForm.branch = "";
        apiBranches.value = [];
    }
};

const loadBranches = async (repoId?: string) => {
    if (!props.useApi) return;
    if (!repoId) {
        apiBranches.value = [];
        createBugForm.branch = "";
        return;
    }
    branchLoading.value = true;
    try {
        const res: any = await getVortgitRepoBranches(repoId);
        apiBranches.value = ((res?.items || []) as any[])
            .map((item) => ({
                name: String(item.name || ""),
            }))
            .filter((item) => item.name);
        if (createBugForm.branch && !apiBranches.value.some((item) => item.name === createBugForm.branch)) {
            createBugForm.branch = "";
        }
    } catch {
        apiBranches.value = [];
        createBugForm.branch = "";
    } finally {
        branchLoading.value = false;
    }
};

const loadIterations = async () => {
    if (!props.useApi) return;
    const selectedProjectId = resolveSelectedProjectId();
    if (!selectedProjectId) {
        apiIterations.value = [];
        createBugForm.iteration = "";
        return;
    }
    const res: any = await getVortflowIterations({
        project_id: selectedProjectId,
        page: 1,
        page_size: 100,
    });
    apiIterations.value = ((res?.items || []) as any[])
        .map((item) => ({
            id: String(item.id || ""),
            name: String(item.name || item.id || ""),
            start_date: item.start_date || "",
            end_date: item.end_date || "",
            owner_id: String(item.owner_id || ""),
            owner_name: String(item.owner_name || ""),
        }))
        .filter((item) => item.id && item.name);
    if (createBugForm.iteration && !apiIterations.value.some((item) => item.id === createBugForm.iteration)) {
        createBugForm.iteration = "";
    }
    // Pre-select iteration from prop (skip special __unplanned__ value)
    if (!createBugForm.iteration && props.iterationId && props.iterationId !== "__unplanned__") {
        if (apiIterations.value.some((item) => item.id === props.iterationId)) {
            createBugForm.iteration = props.iterationId;
        }
    }
};

const loadVersions = async () => {
    if (!props.useApi) return;
    const selectedProjectId = resolveSelectedProjectId();
    if (!selectedProjectId) {
        apiVersions.value = [];
        createBugForm.version = "";
        return;
    }
    const res: any = await getVortflowVersions({
        project_id: selectedProjectId,
        page: 1,
        page_size: 100,
    });
    apiVersions.value = ((res?.items || []) as any[])
        .map((item) => ({
            id: String(item.id || ""),
            name: String(item.name || item.id || ""),
        }))
        .filter((item) => item.id && item.name);
    if (createBugForm.version && !apiVersions.value.some((item) => item.id === createBugForm.version)) {
        createBugForm.version = "";
    }
};

const loadProjectLinkedOptions = async (resetSelections = false) => {
    if (!props.useApi) return;
    if (resetSelections) {
        createBugForm.iteration = "";
        createBugForm.version = "";
        createBugForm.repo = "";
        createBugForm.branch = "";
        apiBranches.value = [];
    }
    await Promise.all([
        loadParentStoryOptions(),
        loadRepos(),
        loadIterations(),
        loadVersions(),
    ]);
};

const createBugPlanTimeModel = computed<any>({
    get: () => (createBugForm.planTime.length === 2 ? [...createBugForm.planTime] as DateRange : undefined),
    set: (value) => {
        if (Array.isArray(value) && value.length === 2) {
            createBugForm.planTime = [String(value[0] || ""), String(value[1] || "")] as DateRange;
            return;
        }
        createBugForm.planTime = [];
    }
});

const toggleCreateTagMenu = () => {
    createTagDropdownOpen.value = !createTagDropdownOpen.value;
    if (!createTagDropdownOpen.value) createTagKeyword.value = "";
};

const toggleCreateTagOption = (tag: string) => {
    const list = [...createBugForm.tags];
    const idx = list.indexOf(tag);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(tag);
    }
    createBugForm.tags = list;
};

const resetForm = () => {
    Object.assign(createBugForm, createInitialBugForm());
    if (props.projectId) {
        createBugForm.projectId = props.projectId;
    }
    if (props.useApi && apiProjects.value.length > 0) {
        const matchedProject =
            apiProjects.value.find((item) => item.id === createBugForm.projectId)
            || apiProjects.value.find((item) => item.name === createBugForm.project)
            || apiProjects.value[0];
        if (matchedProject) {
            createBugForm.projectId = matchedProject.id;
            createBugForm.project = matchedProject.name;
        }
    }
    if (props.parentId) {
        createBugForm.parentId = props.parentId;
        if (currentCreateType.value === "任务") {
            createBugForm.storyId = "";
        }
    }
    if (props.iterationId && props.iterationId !== "__unplanned__") {
        if (apiIterations.value.some((item) => item.id === props.iterationId)) {
            createBugForm.iteration = props.iterationId;
        }
    }
};

const resolvePlanTime = (): NewBugForm["planTime"] => {
    const pt = createBugForm.planTime;
    if (pt.length === 2 && pt[0] && pt[1]) return [...pt] as NewBugForm["planTime"];
    if (createBugForm.iteration && createBugForm.iteration !== "__unplanned__") {
        const iter = apiIterations.value.find((item) => item.id === createBugForm.iteration);
        if (iter) {
            const s = iter.start_date?.split("T")[0] || "";
            const e = iter.end_date?.split("T")[0] || "";
            if (s || e) return [s || e, e || s] as NewBugForm["planTime"];
        }
    }
    return [...pt] as NewBugForm["planTime"];
};

const submitForm = (): NewBugForm | null => {
    const title = createBugForm.title.trim();
    if (!title) {
        message.warning("请填写标题");
        return null;
    }
    return {
        ...createBugForm,
        collaborators: [...createBugForm.collaborators],
        planTime: resolvePlanTime(),
        tags: [...createBugForm.tags],
        attachments: [...createBugForm.attachments],
    };
};

const handleCancel = () => {
    resetForm();
    emit("close");
};

const getFormData = (): NewBugForm => ({
    ...createBugForm,
    collaborators: [...createBugForm.collaborators],
    planTime: resolvePlanTime(),
    tags: [...createBugForm.tags],
    attachments: [...createBugForm.attachments],
});

const getDescriptionTemplateForCurrentType = (): string => getDescriptionTemplate(createBugForm.type as WorkItemType);

defineExpose({
    submit: submitForm,
    reset: resetForm,
    cancel: handleCancel,
    getFormData,
    getDescriptionTemplateForCurrentType,
});

watch(() => props.initialDraft, (draft) => {
    if (draft) {
        Object.assign(createBugForm, mergeDraftIntoForm(draft));
    }
});

onMounted(async () => {
    try {
        const res: any = await getVortflowDescriptionTemplates();
        if (res?.items) {
            remoteTemplates.value = res.items;
            if (!createBugForm.description || createBugForm.description === FALLBACK_TEMPLATES[props.type]) {
                createBugForm.description = getDescriptionTemplate(props.type);
            }
        }
    } catch { /* use fallback */ }

    await loadMemberOptions();
    await loadTagDefinitions();
    if (props.useApi) {
        await loadApiProjects();
        await loadProjectLinkedOptions();
        if (createBugForm.repo) {
            await loadBranches(createBugForm.repo);
        }
    }
});

watch(() => props.parentId, (value) => {
    createBugForm.parentId = value || "";
    if (currentCreateType.value === "任务" && value) {
        createBugForm.storyId = "";
    }
});

watch(() => props.projectId, async (value) => {
    if (!value) return;
    createBugForm.projectId = value;
    const match = apiProjects.value.find((item) => item.id === value);
    if (match && createBugForm.project !== match.name) {
        createBugForm.project = match.name;
    }
    await loadProjectLinkedOptions(true);
});

watch(() => createBugForm.project, async (_value, oldValue) => {
    if (!props.useApi) return;
    const previousProjectId = createBugForm.projectId;
    createBugForm.projectId = resolveSelectedProjectId();
    const projectChanged = oldValue !== undefined && previousProjectId !== createBugForm.projectId;
    await loadProjectLinkedOptions(projectChanged);
});

watch(() => createBugForm.type, async (value, oldValue) => {
    if (oldValue) {
        const oldTemplate = getDescriptionTemplate(oldValue as WorkItemType);
        if (!createBugForm.description || createBugForm.description === oldTemplate) {
            createBugForm.description = getDescriptionTemplate(value as WorkItemType);
        }
    }

    if (value === "需求") {
        createBugForm.storyId = "";
        await loadParentStoryOptions();
        return;
    }
    createBugForm.parentId = "";
    if (value === "任务" || value === "缺陷") {
        await loadParentStoryOptions();
        return;
    }
    createBugForm.storyId = "";
    parentStoryOptions.value = [];
});

const fillPlanTimeFromIteration = (iterationId: string) => {
    if (!iterationId || iterationId === "__unplanned__") return;
    if (createBugForm.planTime.length === 2 && createBugForm.planTime[0] && createBugForm.planTime[1]) return;
    const iter = apiIterations.value.find((item) => item.id === iterationId);
    if (!iter) return;
    const startDate = iter.start_date?.split("T")[0] || "";
    const endDate = iter.end_date?.split("T")[0] || "";
    if (startDate || endDate) {
        createBugForm.planTime = [startDate || endDate, endDate || startDate];
    }
};

watch(() => createBugForm.iteration, (iterationId) => {
    fillPlanTimeFromIteration(iterationId);
});

watch(() => createBugForm.repo, async (value, oldValue) => {
    if (!props.useApi) return;
    if (value === oldValue) return;
    if (!value) {
        apiBranches.value = [];
        createBugForm.branch = "";
        return;
    }
    createBugForm.branch = "";
    await loadBranches(value);
});
</script>

<template>
    <div class="create-bug-drawer">
        <div class="create-bug-main">
            <div class="create-bug-row create-bug-row-full">
                <div class="create-bug-field">
                    <label class="create-bug-label">标题 <span class="required">*</span></label>
                    <vort-input v-model="createBugForm.title" placeholder="请填写" />
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">负责人/协作者</label>
                    <div class="bug-detail-info-assignee create-assignee-wrapper w-full" @click.stop>
                        <WorkItemMemberPicker
                            mode="assignee"
                            :owner="createBugForm.owner"
                            :collaborators="createBugForm.collaborators"
                            :groups="prioritizedOwnerGroups"
                            :open="createAssigneeDropdownOpen"
                            v-model:keyword="createAssigneeKeyword"
                            :dropdown-width="280"
                            :dropdown-max-height="320"
                            :bordered="false"
                            :get-avatar-bg="getAvatarBg"
                            :get-avatar-label="getAvatarLabel"
                            :get-avatar-url="getMemberAvatarUrl"
                            :filter-score="getMemberKeywordScore"
                            @update:open="(open) => { createAssigneeDropdownOpen = open; if (!open) createAssigneeKeyword = ''; }"
                            @update:owner="(value) => { createBugForm.owner = value; }"
                            @update:collaborators="(value) => { createBugForm.collaborators = value; }"
                        >
                            <template #trigger="{ open }">
                                <div
                                    class="detail-assignee-trigger create-assignee-trigger"
                                    :class="open ? 'active' : ''"
                                    tabindex="0"
                                    @click.stop="toggleCreateAssigneeMenu"
                                >
                                    <div class="detail-assignee-split">
                                        <div class="detail-assignee-owner">
                                            <span
                                                v-if="createBugForm.owner"
                                                class="detail-assignee-avatar overflow-hidden"
                                                :style="{ backgroundColor: getAvatarBg(createBugForm.owner) }"
                                            >
                                                <img v-if="getMemberAvatarUrl(createBugForm.owner)" :src="getMemberAvatarUrl(createBugForm.owner)" class="w-full h-full object-cover" />
                                                <template v-else>{{ getAvatarLabel(createBugForm.owner) }}</template>
                                            </span>
                                            <span class="detail-assignee-owner-name" :class="!createBugForm.owner ? 'text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]' : 'text-[var(--vort-text,rgba(0,0,0,0.88))]'">
                                                {{ createOwnerDisplayText }}
                                            </span>
                                        </div>
                                        <span v-if="createBugForm.collaborators.length > 0" class="detail-assignee-separator">/</span>
                                        <div v-if="createBugForm.collaborators.length > 0" class="detail-assignee-collaborators detail-collab-stack">
                                            <template v-if="createBugForm.collaborators.length > 0">
                                                <span
                                                    v-for="name in createBugForm.collaborators"
                                                    :key="'create-collab-' + name"
                                                    class="detail-assignee-avatar overflow-hidden"
                                                    :style="{ backgroundColor: getAvatarBg(name) }"
                                                    :title="name"
                                                >
                                                    <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full object-cover" />
                                                    <template v-else>{{ getAvatarLabel(name) }}</template>
                                                </span>
                                            </template>
                                        </div>
                                    </div>
                                    <span class="vort-select-arrow ml-auto" :class="{ 'vort-select-arrow-open': open }">
                                        <DownOutlined />
                                    </span>
                                </div>
                            </template>
                        </WorkItemMemberPicker>
                    </div>
                </div>
                <div v-if="!props.type || props.type === '缺陷'" class="create-bug-field">
                    <label class="create-bug-label">类型 <span class="required">*</span></label>
                    <vort-select v-model="createBugForm.type">
                        <vort-select-option value="缺陷">缺陷</vort-select-option>
                        <vort-select-option value="需求">需求</vort-select-option>
                        <vort-select-option value="任务">任务</vort-select-option>
                    </vort-select>
                </div>
                <div v-if="shouldShowParentSelector" class="create-bug-field">
                    <label class="create-bug-label">父需求</label>
                    <vort-select v-model="createBugForm.parentId" placeholder="选择父需求" allow-clear>
                        <vort-select-option value="">无</vort-select-option>
                        <vort-select-option
                            v-for="item in parentStoryOptions"
                            :key="item.id"
                            :value="item.id"
                        >
                            {{ item.title }}
                        </vort-select-option>
                    </vort-select>
                </div>
                <div v-else-if="isTaskChildCreate" class="create-bug-field">
                    <label class="create-bug-label">父任务</label>
                    <div class="create-readonly-field">
                        <div class="create-readonly-title">
                            <span class="work-type-icon-small create-parent-icon" :class="getWorkItemTypeIconClass('任务')">
                                <component :is="getWorkItemTypeIcon('任务')" :size="12" />
                            </span>
                            <span class="create-readonly-no">{{ taskParentRecord?.workNo || createBugForm.parentId }}</span>
                            <span class="create-readonly-main">{{ taskParentRecord?.title || "已选择父任务" }}</span>
                        </div>
                        <div class="create-readonly-hint">将自动继承父任务关联的需求</div>
                    </div>
                </div>
                <div v-if="shouldShowStorySelector" class="create-bug-field">
                    <label class="create-bug-label">关联需求</label>
                    <vort-select v-model="createBugForm.storyId" :placeholder="storySelectorPlaceholder" allow-clear>
                        <vort-select-option value="">无</vort-select-option>
                        <vort-select-option
                            v-for="item in parentStoryOptions"
                            :key="`story-${item.id}`"
                            :value="item.id"
                        >
                            {{ item.title }}
                        </vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">计划时间</label>
                    <vort-range-picker
                        v-model="createBugPlanTimeModel"
                        value-format="YYYY-MM-DD"
                        format="YYYY-MM-DD"
                        separator="~"
                        :placeholder="['未设置', '未设置']"
                    />
                </div>
                <div class="create-bug-field">
                    <label class="create-bug-label">关联项目</label>
                    <vort-select v-model="createBugForm.project">
                        <vort-select-option v-for="item in createProjectOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">迭代</label>
                    <vort-select v-model="createBugForm.iteration" placeholder="选择迭代" allow-clear>
                        <vort-select-option v-for="item in iterationSelectOptions" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="create-bug-field">
                    <label class="create-bug-label">版本</label>
                    <vort-select v-model="createBugForm.version" placeholder="选择版本" allow-clear>
                        <vort-select-option v-for="item in versionSelectOptions" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row create-bug-row-full">
                <div class="create-bug-field">
                    <label class="create-bug-label">描述</label>
                    <VortEditor v-model="createBugForm.description" placeholder="请填写描述内容" min-height="260px" />
                </div>
            </div>
        </div>

        <div class="create-bug-side">
            <div class="create-bug-field">
                <label class="create-bug-label">优先级</label>
                <WorkItemPriority
                    :model-value="(createBugForm.priority || 'none') as Priority"
                    :open="createBugPriorityDropdownOpen"
                    @update:open="(open) => { createBugPriorityDropdownOpen = open; }"
                    @change="selectCreateBugPriority"
                >
                    <template #default>
                        <div
                            class="create-bug-priority-trigger"
                            :class="createBugPriorityDropdownOpen ? 'active' : ''"
                            tabindex="0"
                            @click.stop="toggleCreateBugPriorityMenu"
                        >
                            <span
                                v-if="createBugForm.priority"
                                class="priority-pill"
                                :class="priorityClassMap[createBugForm.priority]"
                            >
                                {{ priorityLabelMap[createBugForm.priority] }}
                            </span>
                            <span v-else class="text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]">请选择</span>
                            <span class="vort-select-arrow ml-auto" :class="{ 'vort-select-arrow-open': createBugPriorityDropdownOpen }">
                                <DownOutlined />
                            </span>
                        </div>
                    </template>
                </WorkItemPriority>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">标签</label>
                <WorkItemTagPicker
                    :model-value="createBugForm.tags"
                    :options="tagOptions"
                    :open="createTagDropdownOpen"
                    v-model:keyword="createTagKeyword"
                    :get-tag-color="getTagColor"
                    @update:open="(open) => { createTagDropdownOpen = open; if (!open) createTagKeyword = ''; }"
                    @update:model-value="(value) => { createBugForm.tags = value; }"
                >
                    <template #trigger="{ open }">
                        <div
                            class="create-tag-trigger"
                            :class="open ? 'active' : ''"
                            tabindex="0"
                            @click.stop="toggleCreateTagMenu"
                        >
                            <div class="create-tag-preview">
                                <template v-if="createBugForm.tags.length > 0">
                                    <span
                                        v-for="tag in createBugForm.tags.slice(0, 3)"
                                        :key="'create-tag-chip-' + tag"
                                        class="px-1.5 py-0.5 rounded text-xs text-white inline-block"
                                        :style="{ backgroundColor: getTagColor(tag) }"
                                    >
                                        {{ tag }}
                                    </span>
                                    <span v-if="createBugForm.tags.length > 3" class="text-gray-400 text-xs">+{{ createBugForm.tags.length - 3 }}</span>
                                </template>
                                <span v-else class="text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]">选择标签</span>
                            </div>
                            <span class="vort-select-arrow" :class="{ 'vort-select-arrow-open': open }">
                                <DownOutlined />
                            </span>
                        </div>
                    </template>
                </WorkItemTagPicker>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">关联仓库</label>
                <vort-select v-model="createBugForm.repo" placeholder="选择仓库" allow-clear>
                    <vort-select-option v-for="item in repoSelectOptions" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                </vort-select>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">关联分支</label>
                <vort-select
                    v-model="createBugForm.branch"
                    :placeholder="createBugForm.repo ? (branchLoading ? '分支加载中' : '选择分支') : '请先选择仓库'"
                    :disabled="!createBugForm.repo"
                    allow-clear
                >
                    <vort-select-option v-for="item in branchSelectOptions" :key="item.name" :value="item.name">{{ item.name }}</vort-select-option>
                </vort-select>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">实际开始时间</label>
                <vort-date-picker
                    v-model="createBugForm.startAt"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    :show-time="true"
                    placeholder="选择日期时间"
                />
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">实际结束时间</label>
                <vort-date-picker
                    v-model="createBugForm.endAt"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    :show-time="true"
                    placeholder="选择日期时间"
                />
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">附件</label>
                <input
                    ref="attachmentInputRef"
                    type="file"
                    multiple
                    style="display: none"
                    @change="handleAttachmentFiles"
                />
                <div class="attachment-list" v-if="createBugForm.attachments.length > 0">
                    <div
                        v-for="(att, idx) in createBugForm.attachments"
                        :key="att.url"
                        class="attachment-item"
                    >
                        <div class="attachment-info">
                            <span class="attachment-name" :title="att.name">{{ att.name }}</span>
                            <span class="attachment-size">{{ formatFileSize(att.size) }}</span>
                        </div>
                        <button type="button" class="attachment-remove" @click="removeAttachment(idx)">×</button>
                    </div>
                </div>
                <button
                    type="button"
                    class="attachment-add-btn"
                    :disabled="attachmentUploading"
                    @click="triggerAttachmentInput"
                >
                    {{ attachmentUploading ? "上传中..." : "+ 添加附件" }}
                </button>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">备注说明</label>
                <vort-input v-model="createBugForm.remark" placeholder="测试用备注" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.create-bug-drawer {
    display: flex;
    gap: 32px;
    height: 100%;
}

.create-bug-main {
    flex: 1;
    overflow-y: auto;
    padding-right: 8px;
}

.create-bug-side {
    width: 280px;
    flex-shrink: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.create-bug-row {
    display: flex;
    gap: 24px;
    margin-bottom: 24px;
}

.create-bug-row-full {
    flex-direction: column;
}

.create-bug-field {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.create-bug-field :deep(.vort-popover-trigger) {
    width: 100%;
}

.create-readonly-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 32px;
    padding: 8px 11px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #f8fafc;
}

.create-readonly-title {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    color: #1e293b;
    font-size: 14px;
}

.create-parent-icon {
    flex-shrink: 0;
}

.create-readonly-no {
    flex-shrink: 0;
    color: #64748b;
    font-size: 12px;
    font-weight: 500;
}

.create-readonly-main {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.create-readonly-hint {
    color: #64748b;
    font-size: 12px;
    line-height: 1.4;
}

.create-assignee-wrapper :deep(.vort-popover-trigger) {
    width: 100%;
}

.create-bug-side .create-bug-field {
    flex: none;
}

.create-bug-label {
    font-size: 13px;
    font-weight: 500;
    color: #334155;
}

.create-bug-label .required {
    color: #ef4444;
    margin-left: 2px;
}

.bug-detail-info-assignee {
    cursor: pointer;
}

.detail-assignee-trigger {
    display: flex;
    align-items: center;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid transparent;
    width: 100%;
    min-height: 32px;
}

.detail-assignee-trigger:hover,
.detail-assignee-trigger.active {
    background: #f8fafc;
    border-color: #e2e8f0;
}

.create-assignee-trigger {
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-assignee-trigger:hover,
.create-assignee-trigger.active {
    border-color: var(--vort-primary, #1456f0);
    background: #fff;
}

.create-assignee-trigger:focus-within,
.create-assignee-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.detail-assignee-split {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
}

.detail-assignee-owner {
    display: flex;
    align-items: center;
    gap: 6px;
}

.detail-assignee-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-size: 11px;
    color: white;
    font-weight: 500;
    flex-shrink: 0;
}

.detail-assignee-owner-name {
    font-size: 14px;
}

.detail-assignee-separator {
    color: #cbd5e1;
    font-size: 14px;
    margin: 0 6px;
}

.detail-assignee-collaborators {
    display: flex;
    align-items: center;
    gap: 4px;
}

.detail-assignee-add {
    background: #f1f5f9 !important;
    color: #94a3b8 !important;
    font-size: 14px !important;
    border: 1px dashed #cbd5e1;
}

.detail-assignee-dropdown {
    width: 280px;
    padding: 12px;
}

.detail-assignee-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    border-radius: 4px;
    margin-bottom: 2px;
    cursor: pointer;
    gap: 12px;
}

.detail-assignee-row:hover {
    background: #f8fafc;
}

.detail-assignee-row.is-owner-row {
    background: #eff6ff;
}

.detail-assignee-row.is-collaborator-row {
    background: #ecfdf5;
}

.detail-assignee-row-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
}

.detail-assignee-row-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
}

.role-btn {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
    line-height: 18px;
}

.role-btn.btn-owner {
    color: var(--vort-primary, #1456f0);
    border-color: var(--vort-primary, #1456f0);
    background: transparent;
}
.role-btn.btn-owner:hover {
    background: var(--vort-primary-shadow, rgba(20, 86, 240, 0.05));
}
.role-btn.btn-owner.is-active {
    color: #94a3b8;
    border-color: #cbd5e1;
    background: transparent;
    cursor: not-allowed;
}

.role-btn.btn-collab {
    color: #10b981;
    border-color: #10b981;
    background: transparent;
}
.role-btn.btn-collab:hover {
    background: rgba(16, 185, 129, 0.05);
}
.role-btn.btn-collab.is-active {
    color: #fff;
    background: #10b981;
    border-color: #10b981;
}

.vort-select-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: transform var(--vort-transition-colors, 0.2s);
}

.vort-select-arrow-open {
    transform: rotate(180deg);
}

.ml-auto {
    margin-left: auto;
}

.create-bug-priority-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-height: 32px;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-bug-priority-trigger:hover,
.create-bug-priority-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.create-bug-priority-trigger:focus-within,
.create-bug-priority-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.create-bug-priority-menu {
    padding: 8px;
}

.create-bug-priority-option {
    width: 100%;
    justify-content: flex-start !important;
    padding: 8px 12px !important;
}

.create-bug-priority-option.is-selected {
    background: #eff6ff;
}

.priority-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid;
}

.create-tag-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 32px;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-tag-trigger:hover,
.create-tag-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.create-tag-trigger:focus-within,
.create-tag-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.create-tag-preview {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
}

.attachment-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.attachment-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #f8fafc;
}

.attachment-info {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex: 1;
}

.attachment-name {
    font-size: 13px;
    color: #334155;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.attachment-size {
    font-size: 12px;
    color: #94a3b8;
    flex-shrink: 0;
}

.attachment-remove {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: transparent;
    color: #94a3b8;
    font-size: 16px;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.15s;
}

.attachment-remove:hover {
    color: #ef4444;
    background: #fef2f2;
}

.attachment-add-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 12px;
    border: 1px dashed #cbd5e1;
    border-radius: 6px;
    background: #fff;
    color: #64748b;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    width: 100%;
}

.attachment-add-btn:hover:not(:disabled) {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.attachment-add-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}
</style>
