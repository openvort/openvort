<template>
    <div class="flex flex-col gap-4">
        <!-- Build Queue -->
        <div class="bg-white rounded-xl overflow-hidden">
            <div class="px-4 py-3 border-b border-gray-100">
                <span class="text-sm font-medium text-gray-700">构建队列</span>
            </div>
            <div class="p-3">
                <div v-if="queue.length === 0" class="text-xs text-gray-400 px-1">
                    队列中没有构建任务
                </div>
                <div v-for="item in queue" :key="item.id" class="px-1 py-1.5 text-xs">
                    <div class="font-medium text-gray-700 truncate">{{ item.task_name }}</div>
                    <div v-if="item.why" class="text-gray-400 mt-0.5 line-clamp-2">{{ item.why }}</div>
                </div>
            </div>
        </div>

        <!-- Executors -->
        <div class="bg-white rounded-xl overflow-hidden">
            <div class="px-4 py-3 border-b border-gray-100">
                <span class="text-sm font-medium text-gray-700">构建执行状态</span>
            </div>
            <div class="p-2">
                <div
                    v-for="(executor, idx) in executors"
                    :key="idx"
                    class="flex items-center gap-2 px-2 py-1.5 rounded"
                    :class="executor.idle ? '' : 'bg-blue-50'"
                >
                    <span class="text-xs text-gray-400 w-4 text-right shrink-0">{{ idx + 1 }}</span>
                    <template v-if="executor.idle">
                        <span class="text-xs text-gray-400">空闲</span>
                    </template>
                    <template v-else>
                        <div class="flex-1 min-w-0">
                            <div class="text-xs text-gray-700 truncate">{{ executor.current_build?.display_name || '构建中' }}</div>
                            <div v-if="executor.progress >= 0" class="mt-1 h-1 bg-blue-100 rounded-full overflow-hidden">
                                <div
                                    class="h-full bg-blue-500 rounded-full transition-all duration-500"
                                    :style="{ width: `${executor.progress}%` }"
                                />
                            </div>
                        </div>
                    </template>
                </div>
                <div v-if="executors.length === 0" class="text-xs text-gray-400 px-3 py-2">
                    暂无数据
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
defineProps<{
    queue: Array<{ id: number; task_name: string; why: string; stuck: boolean }>;
    executors: Array<{ idle: boolean; progress: number; current_build: { url: string; number: number; display_name: string } | null }>;
}>();
</script>
