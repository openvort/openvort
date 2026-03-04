<script setup lang="ts">
import { ref, shallowRef } from "vue";
import { z } from "zod";
import { useCrudPage } from "@/hooks";
import axios from "axios";
import { Plus } from "lucide-vue-next";

interface UserItem {
    id: string;
    username: string;
    realName: string;
    email: string;
    phone: string;
    role: string;
    department: string;
    status: number;
    createdAt: string;
}

// 表单/详情组件
const FormComponent = shallowRef<any>(null);
const DetailComponent = shallowRef<any>(null);

const fetchUsers = async (params: any) => {
    const query = new URLSearchParams(params).toString();
    const res = await axios.get(`/api/system/users?${query}`);
    return res.data.data;
};

const { listData, loading, total, filterParams, showPagination, rowSelection, hasSelection, selectedIds, loadData, onSearchSubmit, resetParams } =
    useCrudPage<UserItem, { page: number; size: number; keyword: string; status: string }>({
        api: fetchUsers,
        defaultParams: { page: 1, size: 10, keyword: "", status: "" }
    });

// 抽屉相关
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<UserItem>>({});
const formRef = ref();

const userValidationSchema = z.object({
    username: z.string().min(1, '用户名不能为空'),
    realName: z.string().min(1, '姓名不能为空'),
    email: z.string().email('请输入有效的邮箱地址').optional().or(z.literal('')),
    phone: z.string().optional().or(z.literal('')),
    role: z.string().optional().or(z.literal('')),
    department: z.string().optional().or(z.literal('')),
});

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增用户";
    currentRow.value = {};
    drawerVisible.value = true;
};

const handleEdit = (row: UserItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑用户";
    currentRow.value = { ...row };
    drawerVisible.value = true;
};

const handleView = (row: UserItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "用户详情";
    currentRow.value = { ...row };
    drawerVisible.value = true;
};

const handleDrawerOk = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    drawerVisible.value = false;
    loadData();
};

// 初始加载
loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- 搜索区域 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">查询表格</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="输入用户名/姓名搜索"
                        allow-clear
                        class="flex-1 sm:w-[220px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.status" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option value="1">启用</vort-select-option>
                        <vort-select-option value="2">禁用</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- 表格 -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false" :row-selection="rowSelection" size="large">
                <vort-table-column label="用户名" prop="username" :width="120" />
                <vort-table-column label="姓名" prop="realName" :width="100" />
                <vort-table-column label="邮箱" prop="email" :width="180" />
                <vort-table-column label="手机号" prop="phone" :width="140" />
                <vort-table-column label="角色" prop="role" :width="100" />
                <vort-table-column label="部门" prop="department" :width="100" />
                <vort-table-column label="状态" :width="80">
                    <template #default="{ row }">
                        <vort-tag :color="row.status === 1 ? 'green' : 'red'">{{ row.status === 1 ? '启用' : '禁用' }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="创建时间" prop="createdAt" :width="170" />
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除？" @confirm="() => {}">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>

            <!-- 分页 -->
            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="filterParams.page"
                    v-model:page-size="filterParams.size"
                    :total="total"
                    show-total-info
                    show-size-changer
                    show-quick-jumper
                    @change="loadData"
                />
            </div>
        </div>

        <!-- 抽屉 -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="600">
            <!-- 查看模式 -->
            <div v-if="drawerMode === 'view' && currentRow.id" class="space-y-4">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div><span class="text-sm text-gray-400">用户名</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.username }}</div></div>
                    <div><span class="text-sm text-gray-400">姓名</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.realName }}</div></div>
                    <div><span class="text-sm text-gray-400">邮箱</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.email }}</div></div>
                    <div><span class="text-sm text-gray-400">手机号</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.phone }}</div></div>
                    <div><span class="text-sm text-gray-400">角色</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.role }}</div></div>
                    <div><span class="text-sm text-gray-400">部门</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.department }}</div></div>
                    <div><span class="text-sm text-gray-400">状态</span><div class="mt-1"><vort-tag :color="currentRow.status === 1 ? 'green' : 'red'">{{ currentRow.status === 1 ? '启用' : '禁用' }}</vort-tag></div></div>
                    <div><span class="text-sm text-gray-400">创建时间</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.createdAt }}</div></div>
                </div>
            </div>

            <!-- 编辑/新增模式 -->
            <div v-else>
                <vort-form ref="formRef" :model="currentRow" :rules="userValidationSchema" label-width="80px">
                    <vort-form-item label="用户名" name="username" required has-feedback><vort-input v-model="currentRow.username" placeholder="请输入用户名" /></vort-form-item>
                    <vort-form-item label="姓名" name="realName" required has-feedback><vort-input v-model="currentRow.realName" placeholder="请输入姓名" /></vort-form-item>
                    <vort-form-item label="邮箱" name="email" has-feedback><vort-input v-model="currentRow.email" placeholder="请输入邮箱" /></vort-form-item>
                    <vort-form-item label="手机号" name="phone"><vort-input v-model="currentRow.phone" placeholder="请输入手机号" /></vort-form-item>
                    <vort-form-item label="角色" name="role"><vort-input v-model="currentRow.role" placeholder="请选择角色" /></vort-form-item>
                    <vort-form-item label="部门" name="department"><vort-input v-model="currentRow.department" placeholder="请选择部门" /></vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" @click="handleDrawerOk">确定</vort-button>
                </div>
            </div>
        </vort-drawer>
    </div>
</template>
