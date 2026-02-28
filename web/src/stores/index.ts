import { createPinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

export default pinia;

export { useUserStore } from "./modules/user";
export { useMenuStore } from "./modules/menu";
export { useTabsStore } from "./modules/tabs";
export { useAppStore } from "./modules/app";
export { useConfigStore } from "./modules/config";
export { usePluginStore } from "./modules/plugin";
