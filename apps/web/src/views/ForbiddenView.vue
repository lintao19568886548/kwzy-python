<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <section class="card panel" data-testid="forbidden-page">
    <h2>无访问权限</h2>
    <p class="muted">当前账号无权访问该页面。请联系管理员分配权限，或返回已授权模块。</p>
    <button class="btn" type="button" data-testid="forbidden-back" @click="router.push('/parties')">
      返回
    </button>
  </section>
</template>

<style scoped>
.panel {
  padding: 1.5rem;
  max-width: 520px;
}
</style>
