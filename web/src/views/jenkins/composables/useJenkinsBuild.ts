import { ref } from "vue";
import { triggerJenkinsBuild, getJenkinsBuildLog, getJenkinsBuildStatus, abortJenkinsBuild } from "@/api/jenkins";
import { message } from "@/components/vort";

export function useJenkinsBuild() {
    const buildTriggering = ref(false);
    const buildLog = ref("");
    const buildLogLoading = ref(false);
    const buildLogTruncated = ref(false);
    const buildLogLineCount = ref(0);

    async function trigger(instanceId: string, jobName: string, parameters?: Record<string, any>) {
        buildTriggering.value = true;
        try {
            await triggerJenkinsBuild(instanceId, { job_name: jobName, parameters });
            message.success("构建已触发");
            return true;
        } catch {
            return false;
        } finally {
            buildTriggering.value = false;
        }
    }

    async function loadBuildLog(instanceId: string, jobName: string, buildNumber: number, tailLines: number = 200) {
        buildLogLoading.value = true;
        try {
            const res: any = await getJenkinsBuildLog(instanceId, jobName, buildNumber, tailLines);
            buildLog.value = res.log || "";
            buildLogTruncated.value = res.truncated || false;
            buildLogLineCount.value = res.line_count || 0;
        } catch {
            buildLog.value = "";
        } finally {
            buildLogLoading.value = false;
        }
    }

    async function abortBuild(instanceId: string, jobName: string, buildNumber: number) {
        try {
            await abortJenkinsBuild(instanceId, jobName, buildNumber);
            message.success("已发送中断请求");
            return true;
        } catch {
            return false;
        }
    }

    async function checkBuildStatus(instanceId: string, jobName: string, buildNumber: number) {
        try {
            const res: any = await getJenkinsBuildStatus(instanceId, jobName, buildNumber);
            return res.build || null;
        } catch {
            return null;
        }
    }

    return {
        buildTriggering,
        buildLog,
        buildLogLoading,
        buildLogTruncated,
        buildLogLineCount,
        trigger,
        abortBuild,
        loadBuildLog,
        checkBuildStatus,
    };
}
