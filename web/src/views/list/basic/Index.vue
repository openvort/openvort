<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Plus, MoreVertical } from "lucide-vue-next";

interface ListItem {
    id: string;
    title: string;
    avatar: string;
    description: string;
    owner: string;
    status: string;
    progress: number;
    updatedAt: string;
}

const loading = ref(true);
const listData = ref<ListItem[]>([]);

onMounted(async () => {
    await new Promise((r) => setTimeout(r, 500));
    listData.value = Array.from({ length: 10 }, (_, i) => ({
        id: String(i + 1),
        title: `项目名称 ${i + 1}`,
        avatar: `https://api.dicebear.com/7.x/identicon/svg?seed=project${i}`,
        description: "这是一段项目描述信息，用于描述项目的基本情况和目标。",
        owner: ["付小小", "曲丽丽", "林东东", "周星星"][i % 4],
        status: ["进行中", "已完成", "已延期"][i % 3],
        progress: Math.floor(Math.random() * 100),
        updatedAt: "2024-03-15 14:30"
    }));
    loading.value = false;
});

const statusColor = (s: string) => ({ "进行中": "blue", "已完成": "green", "已延期": "red" }[s] || "gray");
</script>

<template>
    <div>
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-base font-medium text-gray-800">标准列表</h3>
                <vort-button variant="primary"><Plus :size="14" class="mr-1" /> 新增</vort-button>
            </div>

            <!-- 统计 -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-6 mb-6 p-4 bg-gray-50 rounded-lg">
                <div class="text-center"><div class="text-sm text-gray-400">我的待办</div><div class="text-xl font-semibold text-gray-800 mt-1">8</div></div>
                <div class="text-center"><div class="text-sm text-gray-400">本周任务平均处理时间</div><div class="text-xl font-semibold text-gray-800 mt-1">32 <span class="text-sm font-normal text-gray-400">分钟</span></div></div>
                <div class="text-center"><div class="text-sm text-gray-400">本周完成任务数</div><div class="text-xl font-semibold text-gray-800 mt-1">24</div></div>
            </div>

            <vort-spin :spinning="loading">
                <div class="divide-y divide-gray-100">
                    <div v-for="item in listData" :key="item.id" class="flex flex-col sm:flex-row sm:items-center py-4 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors gap-3 sm:gap-0">
                        <img :src="item.avatar" class="w-12 h-12 rounded-lg sm:mr-4 flex-shrink-0" />
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-sm font-medium text-gray-800">{{ item.title }}</span>
                                <vort-tag :color="statusColor(item.status)" size="sm">{{ item.status }}</vort-tag>
                            </div>
                            <p class="text-xs text-gray-400 truncate">{{ item.description }}</p>
                            <div class="flex items-center gap-4 mt-1.5 text-xs text-gray-400">
                                <span>负责人: {{ item.owner }}</span>
                                <span>更新于 {{ item.updatedAt }}</span>
                            </div>
                        </div>
                        <div class="w-full sm:w-[180px] sm:mx-4">
                            <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
                                <span>进度</span>
                                <span>{{ item.progress }}%</span>
                            </div>
                            <div class="w-full bg-gray-100 rounded-full h-1.5">
                                <div class="bg-blue-500 h-1.5 rounded-full" :style="{ width: item.progress + '%' }"></div>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0">
                            <a class="text-sm text-blue-600 cursor-pointer">编辑</a>
                            <MoreVertical :size="16" class="text-gray-400 cursor-pointer" />
                        </div>
                    </div>
                </div>
            </vort-spin>
        </div>
    </div>
</template>
