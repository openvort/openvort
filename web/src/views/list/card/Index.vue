<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Star, Download, Plus } from "lucide-vue-next";

interface CardItem {
    id: string;
    title: string;
    cover: string;
    description: string;
    stars: number;
    downloads: number;
    tags: string[];
}

const loading = ref(true);
const listData = ref<CardItem[]>([]);

onMounted(async () => {
    await new Promise((r) => setTimeout(r, 500));
    listData.value = Array.from({ length: 12 }, (_, i) => ({
        id: String(i + 1),
        title: `应用 ${i + 1}`,
        cover: `https://picsum.photos/seed/${i + 10}/300/200`,
        description: "一个关于技术的应用描述，包含关键信息和概述。",
        stars: Math.floor(Math.random() * 500),
        downloads: Math.floor(Math.random() * 10000),
        tags: [["Vue", "前端"], ["React", "TypeScript"], ["Node.js", "后端"], ["Python", "数据"]][i % 4]
    }));
    loading.value = false;
});
</script>

<template>
    <div>
        <vort-card :shadow="false" class="mb-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">卡片列表</h3>
                <div class="flex items-center gap-3">
                    <vort-input-search placeholder="搜索应用" class="w-[220px]" />
                </div>
            </div>
        </vort-card>

        <vort-spin :spinning="loading">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <!-- 新增卡片 -->
                <div class="bg-white rounded-xl border-2 border-dashed border-gray-200 flex items-center justify-center min-h-[260px] cursor-pointer hover:border-blue-400 transition-colors group">
                    <div class="text-center">
                        <Plus :size="32" class="text-gray-300 mx-auto mb-2 group-hover:text-blue-400 transition-colors" />
                        <span class="text-sm text-gray-400 group-hover:text-blue-500">新增应用</span>
                    </div>
                </div>

                <!-- 应用卡片 -->
                <div v-for="item in listData" :key="item.id" class="bg-white rounded-xl overflow-hidden cursor-pointer group hover:bg-gray-50 transition-colors">
                    <div class="h-[140px] bg-gray-100 overflow-hidden">
                        <img :src="item.cover" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                    </div>
                    <div class="p-4">
                        <h4 class="text-sm font-medium text-gray-800 mb-1">{{ item.title }}</h4>
                        <p class="text-xs text-gray-400 line-clamp-2 mb-3">{{ item.description }}</p>
                        <div class="flex items-center gap-2 mb-3">
                            <vort-tag v-for="tag in item.tags" :key="tag" size="sm">{{ tag }}</vort-tag>
                        </div>
                        <div class="flex items-center justify-between text-xs text-gray-400 border-t border-gray-100 pt-3">
                            <span class="flex items-center gap-1"><Star :size="12" /> {{ item.stars }}</span>
                            <span class="flex items-center gap-1"><Download :size="12" /> {{ item.downloads.toLocaleString() }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </vort-spin>
    </div>
</template>
