import axios from "axios";
import { useUserStore } from "@/stores";
import { message } from "@/components/vort";

declare module "axios" {
    interface AxiosRequestConfig {
        /** 跳过拦截器的全局错误提示（组件自行处理时使用） */
        skipErrorMessage?: boolean;
    }
}

const request = axios.create({
    baseURL: "/api",
    timeout: 10000
});

request.interceptors.request.use((config) => {
    const userStore = useUserStore();
    if (userStore.token) {
        config.headers.Authorization = `Bearer ${userStore.token}`;
    }
    return config;
});

request.interceptors.response.use(
    (response) => {
        return response.data;
    },
    (error) => {
        if (error.response?.status === 401) {
            const isLoginRequest = error.config?.url?.includes("/auth/login");
            if (!isLoginRequest) {
                const userStore = useUserStore();
                userStore.logout();
                window.location.href = "/login";
            }
        } else if (!error.config?.skipErrorMessage) {
            message.error(error.response?.data?.detail || error.response?.data?.message || "请求失败");
        }
        return Promise.reject(error);
    }
);

export default request;
