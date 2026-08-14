<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";
import type { Envelope, PageResult } from "@/api/types";

const items = ref<Array<Record<string, unknown>>>([]);
const error = ref("");
const success = ref("");
const loading = ref(true);
const status = ref("");
const form = ref({
  park_id: "",
  party_id: "",
  bill_id: "",
  level: "L1",
});
const updateForm = ref({ id: "", level: "L2", note: "" });
const runForm = ref({ as_of: new Date().toISOString().slice(0, 10), park_id: "" });
const runPreview = ref<Record<string, unknown> | null>(null);
const selectedCase = ref<Record<string, unknown> | null>(null);
const records = ref<Array<Record<string, unknown>>>([]);
const recordForm = ref({ action_type: "CALL", note: "", next_follow_up_at: "" });

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<PageResult<Record<string, unknown>>>>(
      "/collection/cases",
      { params: { page: 1, page_size: 50, status: status.value || undefined } }
    );
    items.value = data.data.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function create() {
  error.value = "";
  try {
    await http.post("/collection/cases", {
      park_id: Number(form.value.park_id),
      party_id: Number(form.value.party_id),
      bill_id: Number(form.value.bill_id),
      level: form.value.level,
    });
    success.value = "案件已创建";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  }
}

async function updateCase() {
  error.value = "";
  try {
    const id = Number(updateForm.value.id);
    const current = items.value.find((item) => Number(item.id) === id);
    if (!current) throw new Error("请先刷新并选择有效案件");
    await http.patch(`/collection/cases/${id}`, {
      expected_version: Number(current.lock_version),
      level: updateForm.value.level,
      remark: updateForm.value.note || undefined,
    });
    success.value = "案件已更新";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "更新失败";
  }
}

async function closeCase(id: number) {
  if (!window.confirm("确认关闭该催缴案件？")) return;
  try {
    const current = items.value.find((item) => Number(item.id) === id);
    if (!current) throw new Error("案件已不在当前列表，请刷新");
    await http.patch(`/collection/cases/${id}`, {
      expected_version: Number(current.lock_version),
      status: "CLOSED",
    });
    success.value = "案件已关闭";
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "关闭失败";
  }
}

async function previewDunning() {
  error.value = "";
  try {
    const { data } = await http.get<Envelope<Record<string, unknown>>>("/collection/runs/preview", {
      params: {
        as_of: runForm.value.as_of,
        park_id: runForm.value.park_id ? Number(runForm.value.park_id) : undefined,
      },
    });
    runPreview.value = data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "账龄预览失败";
  }
}

async function applyDunning() {
  if (!runPreview.value || !window.confirm(`确认按账龄策略处理 ${runPreview.value.total || 0} 张欠费账单？`)) return;
  try {
    await http.post(
      "/collection/runs",
      {
        as_of: runForm.value.as_of,
        park_id: runForm.value.park_id ? Number(runForm.value.park_id) : null,
      },
      { headers: { "Idempotency-Key": `dunning-${runForm.value.as_of}-${runForm.value.park_id || "all"}-${Date.now()}` } }
    );
    success.value = "账龄催缴运行完成，未连接的外部通道没有伪造发送。";
    runPreview.value = null;
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "催缴运行失败";
  }
}

async function openHistory(row: Record<string, unknown>) {
  selectedCase.value = row;
  error.value = "";
  try {
    const { data } = await http.get<Envelope<Array<Record<string, unknown>>>>(
      `/collection/cases/${row.id}/records`
    );
    records.value = data.data;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "催缴轨迹加载失败";
  }
}

async function addRecord() {
  if (!selectedCase.value) return;
  try {
    await http.post(`/collection/cases/${selectedCase.value.id}/records`, {
      action_type: recordForm.value.action_type,
      note: recordForm.value.note || null,
      next_follow_up_at: recordForm.value.next_follow_up_at || null,
      channel: null,
      source_ref: null,
    });
    success.value = ["SMS", "WECHAT", "EMAIL"].includes(recordForm.value.action_type)
      ? "外部通道未连接，记录为 NOT_CONFIGURED，没有伪造送达。"
      : "催缴过程已追加记录。";
    recordForm.value.note = "";
    await openHistory(selectedCase.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "记录失败";
  }
}

onMounted(load);
</script>

<template>
  <section class="card panel">
    <header class="head">
      <div>
        <h2 data-testid="collection-title">催缴案件</h2>
        <p class="muted">过程记录，不替代收款核销</p>
      </div>
      <div class="tools">
        <select v-model="status" class="input" data-testid="collection-status-filter" @change="load">
          <option value="">全部状态</option>
          <option value="OPEN">OPEN</option>
          <option value="CLOSED">CLOSED</option>
        </select>
        <button class="btn btn-ghost" type="button" @click="load">刷新</button>
      </div>
    </header>

    <section class="run-panel" data-testid="dunning-run-panel">
      <div><b>自动账龄分级</b><small class="muted">L1 1–7 天 / L2 8–30 天 / L3 31–60 天 / L4 61+ 天</small></div>
      <input v-model="runForm.as_of" class="input" type="date" aria-label="账龄截止日" />
      <input v-model="runForm.park_id" class="input" placeholder="园区 ID（可空）" />
      <button class="btn btn-ghost" type="button" data-testid="dunning-preview-btn" @click="previewDunning">预览</button>
      <button v-if="runPreview" v-permission="'collection:run'" class="btn" type="button" data-testid="dunning-apply-btn" @click="applyDunning">执行</button>
    </section>
    <div v-if="runPreview" class="preview" data-testid="dunning-preview-result">欠费 {{ runPreview.total }} 笔，共 ¥ {{ runPreview.amount }}；预览不会创建案件。</div>

    <form class="create" data-testid="collection-create-form" @submit.prevent="create">
      <input
        v-model="form.park_id"
        class="input"
        data-testid="collection-park-id"
        placeholder="园区ID"
        required
      />
      <input
        v-model="form.party_id"
        class="input"
        data-testid="collection-party-id"
        placeholder="主体ID"
        required
      />
      <input
        v-model="form.bill_id"
        class="input"
        data-testid="collection-bill-id"
        placeholder="账单ID"
        required
      />
      <select v-model="form.level" class="input" data-testid="collection-level">
        <option>L1</option>
        <option>L2</option>
        <option>L3</option>
        <option>L4</option>
      </select>
      <button
        v-permission="'collection:write'"
        class="btn"
        data-testid="collection-create-btn"
        type="submit"
      >
        创建案件
      </button>
    </form>

    <form class="create" data-testid="collection-update-form" @submit.prevent="updateCase">
      <input
        v-model="updateForm.id"
        class="input"
        data-testid="collection-update-id"
        placeholder="案件ID"
        required
      />
      <select v-model="updateForm.level" class="input" data-testid="collection-update-level">
        <option>L1</option>
        <option>L2</option>
        <option>L3</option>
        <option>L4</option>
      </select>
      <input
        v-model="updateForm.note"
        class="input"
        data-testid="collection-note"
        placeholder="备注"
      />
      <button
        v-permission="'collection:write'"
        class="btn"
        data-testid="collection-update-btn"
        type="submit"
      >
        更新
      </button>
    </form>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-if="error" class="error" data-testid="collection-error">{{ error }}</p>
    <p v-if="success" class="ok" data-testid="collection-success">{{ success }}</p>
    <table v-if="!loading" class="table" data-testid="collection-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账单</th>
          <th>主体</th>
          <th>级别</th>
          <th>欠费/逾期</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)" :data-testid="`collection-row-${row.id}`">
          <td data-testid="collection-id-cell">{{ row.id }}</td>
          <td>{{ row.bill_id }}</td>
          <td>{{ row.party_id }}</td>
          <td data-testid="collection-level-cell">{{ row.level }}</td>
          <td>{{ row.amount_snapshot }}<small>{{ row.overdue_days }} 天</small></td>
          <td><span class="badge" data-testid="collection-status-cell">{{ row.status }}</span></td>
          <td class="ops">
            <button class="btn btn-ghost" type="button" data-testid="collection-history-btn" @click="openHistory(row)">轨迹</button>
            <button
              v-if="row.status === 'OPEN'"
              v-permission="'collection:write'"
              class="btn"
              type="button"
              data-testid="collection-close-btn"
              @click="closeCase(Number(row.id))"
            >
              关闭
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="7" class="muted">暂无案件</td>
        </tr>
      </tbody>
    </table>
    <div v-if="selectedCase" class="drawer-backdrop" @click.self="selectedCase = null">
      <aside class="drawer card" data-testid="collection-history-drawer">
        <header class="drawer-head"><div><p class="eyebrow">COLLECTION TRACE</p><h3>案件 #{{ selectedCase.id }} · {{ selectedCase.level }}</h3></div><button class="close" type="button" aria-label="关闭" @click="selectedCase = null">×</button></header>
        <div class="facts"><span>欠费<b>¥ {{ selectedCase.amount_snapshot }}</b></span><span>逾期<b>{{ selectedCase.overdue_days }} 天</b></span><span>下次动作<b>{{ selectedCase.next_action_at || '未设置' }}</b></span><span>版本<b>{{ selectedCase.lock_version }}</b></span></div>
        <form class="record-form" @submit.prevent="addRecord">
          <select v-model="recordForm.action_type" class="input" data-testid="collection-record-action"><option>CALL</option><option>VISIT</option><option>NOTICE</option><option>NOTE</option><option>SMS</option><option>WECHAT</option><option>EMAIL</option></select>
          <input v-model="recordForm.next_follow_up_at" class="input" type="datetime-local" />
          <textarea v-model="recordForm.note" class="input textarea" placeholder="联系结果与后续动作" maxlength="2000" />
          <button v-permission="'collection:write'" class="btn" data-testid="collection-record-btn" type="submit">追加过程记录</button>
        </form>
        <article v-for="record in records" :key="String(record.id)" class="record"><div><b>{{ record.action_type }}</b> <span class="badge">{{ record.status }}</span></div><small>{{ record.created_at }} · {{ record.note || '无备注' }}</small></article>
        <p v-if="!records.length" class="muted">暂无过程记录</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.panel {
  padding: 1rem;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}
.tools {
  display: flex;
  gap: 0.5rem;
}
.run-panel { display: grid; grid-template-columns: minmax(210px, 1.4fr) repeat(4, minmax(110px, .7fr)); gap: .6rem; align-items: center; padding: .8rem; border-radius: 12px; background: #edf7fb; margin: 1rem 0; }.run-panel small, .table td small { display: block; }.preview { padding: .75rem; border-left: 3px solid #0891b2; background: #f0f9ff; }.ops { display: flex; gap: .4rem; }.drawer-backdrop { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; background: rgba(3,19,35,.44); }.drawer { width: min(580px,100%); height: 100%; overflow-y: auto; padding: 1.25rem; border-radius: 18px 0 0 18px; }.drawer-head { display: flex; justify-content: space-between; }.close { border: 0; background: transparent; font-size: 2rem; cursor: pointer; }.eyebrow { color: #0e7490; font-size: .72rem; font-weight: 800; letter-spacing: .14em; }.facts { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; margin: 1rem 0; }.facts span, .record { padding: .75rem; border-radius: 10px; background: #f4f7fa; }.facts b { display: block; }.record-form { display: grid; gap: .6rem; margin: 1rem 0; }.textarea { min-height: 90px; }.record { margin: .5rem 0; }.record small { display: block; }.table { min-width: 800px; }.panel { min-width: 0; overflow-x: auto; }
.create {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.6rem;
  margin: 1rem 0;
}
.ok {
  color: #047857;
}
@media (max-width: 800px) { .run-panel { grid-template-columns: 1fr 1fr; }.drawer { border-radius: 0; } }
</style>
