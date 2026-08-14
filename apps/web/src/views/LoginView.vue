<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const username = ref("admin");
const password = ref("");
const loading = ref(false);
const error = ref("");
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

function firstAllowedPath(): string {
  const candidates: Array<{ path: string; perm?: string | string[] }> = [
    { path: "/workbench", perm: "work_item:read" },
    { path: "/parties", perm: "party:read" },
    { path: "/rent-control", perm: "unit:read" },
    { path: "/records-seal", perm: "record:read" },
    { path: "/workforce", perm: "workforce:read" },
    { path: "/parks", perm: "park:read" },
    { path: "/todos", perm: "work_item:read" },
    { path: "/leads", perm: "lead:read" },
    { path: "/system", perm: ["identity.user.read", "identity.org.read"] },
  ];
  for (const c of candidates) {
    if (!c.perm || auth.can(c.perm) || auth.can("*")) return c.path;
  }
  return "/forbidden";
}

async function onSubmit() {
  loading.value = true;
  error.value = "";
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect =
      typeof route.query.redirect === "string" ? route.query.redirect : firstAllowedPath();
    // If redirect target is still denied, fall back
    const target = redirect.startsWith("/") ? redirect : firstAllowedPath();
    await router.replace(target);
    if (router.currentRoute.value.name === "forbidden" || router.currentRoute.value.name === "login") {
      await router.replace(firstAllowedPath());
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="card form" @submit.prevent="onSubmit">
      <h1>KWZY 智慧园区</h1>
      <p class="muted">创新运营台 · 登录后进入工作台</p>
      <label for="login-username">
        用户名
        <input
          id="login-username"
          v-model="username"
          class="input"
          autocomplete="username"
          required
        />
      </label>
      <label for="login-password">
        密码
        <input
          id="login-password"
          v-model="password"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <button class="btn" type="submit" data-testid="login-submit" :disabled="loading">
        {{ loading ? "登录中…" : "登录" }}
      </button>
      <p v-if="error" class="error" data-testid="login-error">{{ error }}</p>
    </form>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1rem;
}
.form {
  width: min(420px, 100%);
  padding: 1.5rem;
  display: grid;
  gap: 0.85rem;
}
label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.92rem;
}
h1 {
  margin: 0;
  font-size: 1.4rem;
}
</style>
