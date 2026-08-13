import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { registerPermission } from "./directives/permission";
import "./styles.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
registerPermission(app);
app.mount("#app");
