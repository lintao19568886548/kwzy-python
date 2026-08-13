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

async function onSubmit() {
  loading.value = true;
  error.value = "";
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/workbench";
    await router.replace(redirect);
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
      <label>
        用户名
        <input v-model="username" class="input" autocomplete="username" required />
      </label>
      <label>
        密码
        <input
          v-model="password"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? "登录中…" : "登录" }}
      </button>
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
