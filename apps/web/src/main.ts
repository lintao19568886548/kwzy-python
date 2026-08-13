import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";
import { registerPermission } from "./directives/permission";
import "./styles.css";

async function bootstrap() {
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  registerPermission(app);

  // Hydrate session before any route guard runs — token alone is not enough for RBAC.
  const auth = useAuthStore(pinia);
  if (auth.accessToken) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clearSession();
    }
  }

  app.use(router);
  await router.isReady();
  app.mount("#app");
}

void bootstrap();
