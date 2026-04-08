import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useUserStore = defineStore(
    "user",
    () => {
        const token = ref<string>("");
        const mustChangePassword = ref(false);
        const userInfo = ref<{
            member_id: string;
            name: string;
            email: string;
            avatar_url: string;
            position: string;
            department: string;
            roles: string[];
            platform_accounts: Record<string, string>;
        }>({
            member_id: "",
            name: "",
            email: "",
            avatar_url: "",
            position: "",
            department: "",
            roles: [],
            platform_accounts: {}
        });

        const isLoggedIn = () => !!token.value;

        const isAdmin = computed(() => userInfo.value.roles.includes("admin") || userInfo.value.roles.includes("demo"));

        const isDemo = computed(() => userInfo.value.roles.includes("demo"));

        const hasRole = (role: string) => {
            if (role === "admin" && userInfo.value.roles.includes("demo")) return true;
            return userInfo.value.roles.includes(role);
        };

        const setToken = (t: string) => {
            token.value = t;
        };

        const setUserInfo = (info: typeof userInfo.value) => {
            userInfo.value = info;
        };

        const setMustChangePassword = (v: boolean) => {
            mustChangePassword.value = v;
        };

        const logout = () => {
            token.value = "";
            mustChangePassword.value = false;
            userInfo.value = {
                member_id: "",
                name: "",
                email: "",
                avatar_url: "",
                position: "",
                department: "",
                roles: [],
                platform_accounts: {}
            };
        };

        return { token, userInfo, mustChangePassword, isLoggedIn, isAdmin, isDemo, hasRole, setToken, setUserInfo, setMustChangePassword, logout };
    },
    { persist: true }
);
