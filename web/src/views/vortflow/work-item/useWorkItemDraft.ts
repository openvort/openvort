import type { NewBugForm, WorkItemType } from "@/components/vort-biz/work-item/WorkItemTable.types";

const DRAFT_KEY_PREFIX = "vortflow_create_draft_";
const DRAFT_EXPIRE_MS = 24 * 60 * 60 * 1000;

interface DraftEnvelope {
    formData: NewBugForm;
    parentId: string;
    savedAt: number;
}

function getDraftKey(type: WorkItemType): string {
    return `${DRAFT_KEY_PREFIX}${type}`;
}

function isFormDirty(formData: NewBugForm, descriptionTemplate: string): boolean {
    if (formData.title.trim()) return true;
    if (formData.owner) return true;
    if (formData.collaborators.length > 0) return true;
    if (formData.tags.length > 0) return true;
    if (formData.priority) return true;
    if (formData.remark.trim()) return true;
    if (formData.repo) return true;
    if (formData.branch) return true;
    if (formData.storyId) return true;
    if (formData.startAt) return true;
    if (formData.endAt) return true;
    if (formData.planTime.length === 2) return true;
    if (formData.description && formData.description !== descriptionTemplate) return true;
    return false;
}

export function useWorkItemDraft() {
    const saveDraft = (type: WorkItemType, formData: NewBugForm, parentId = "", descriptionTemplate = "") => {
        if (!isFormDirty(formData, descriptionTemplate)) return;
        try {
            const envelope: DraftEnvelope = {
                formData: {
                    ...formData,
                    collaborators: [...formData.collaborators],
                    planTime: [...formData.planTime] as NewBugForm["planTime"],
                    tags: [...formData.tags],
                },
                parentId,
                savedAt: Date.now(),
            };
            sessionStorage.setItem(getDraftKey(type), JSON.stringify(envelope));
        } catch { /* quota exceeded or private mode */ }
    };

    const loadDraft = (type: WorkItemType, parentId = ""): NewBugForm | null => {
        try {
            const raw = sessionStorage.getItem(getDraftKey(type));
            if (!raw) return null;
            const envelope: DraftEnvelope = JSON.parse(raw);
            if (Date.now() - envelope.savedAt > DRAFT_EXPIRE_MS) {
                sessionStorage.removeItem(getDraftKey(type));
                return null;
            }
            if (envelope.parentId !== parentId) return null;
            return envelope.formData;
        } catch {
            return null;
        }
    };

    const clearDraft = (type: WorkItemType) => {
        try {
            sessionStorage.removeItem(getDraftKey(type));
        } catch { /* ignore */ }
    };

    return { saveDraft, loadDraft, clearDraft };
}
