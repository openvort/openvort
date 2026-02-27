import { defineStore } from "pinia";
import { reactive } from "vue";

/** 简化的系统配置 Store */
export const useConfigStore = defineStore("config", () => {
    const config = reactive<Record<string, any>>({
        pageSize: 20
    });

    const get = (key: string) => config[key];

    const set = (key: string, value: any) => {
        config[key] = value;
    };

    return { config, get, set };
});
