<!-- frontend/src/components/AdminUsers.vue -->
<script setup>
import { ref, onMounted } from 'vue';
import { listUsers, setUserRole } from '../api.js';
import { useAuth } from '../composables/useAuth.js';

const { user } = useAuth();

const loading = ref(true);
const busyId = ref('');
const error = ref('');
const users = ref([]);

async function load() {
  loading.value = true;
  error.value = '';
  try {
    users.value = await listUsers();
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

const ROLE_LABEL = { root: '超级管理员', admin: '管理员', user: '普通用户' };

async function toggleRole(u) {
  const next = u.role === 'admin' ? 'user' : 'admin';
  const verb = next === 'admin' ? '设为管理员' : '取消管理员';
  if (!window.confirm(`确定将「${u.username}」${verb}吗？`)) return;
  busyId.value = u.user_id;
  error.value = '';
  try {
    await setUserRole(u.user_id, next);
    await load();
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    busyId.value = '';
  }
}

function fmtDate(s) {
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 16);
}

onMounted(load);
</script>

<template>
  <main class="shell page">
    <div class="crumb"><span class="c-now">用户管理</span></div>

    <div class="au-head">
      <h2>用户管理</h2>
      <button class="btn btn-ghost btn-sm" :disabled="loading" @click="load">刷新</button>
    </div>
    <p class="au-hint">
      仅超级管理员可访问。在这里将普通用户设为管理员（可管理岗位广场与题库），或取消管理员。
      超级管理员账号与当前登录的自己不可修改。
    </p>

    <div v-if="error" class="au-error">{{ error }}</div>

    <div v-if="loading" class="au-empty">加载中…</div>

    <section v-else class="au-card">
      <table class="au-table">
        <thead>
          <tr><th>用户名</th><th>角色</th><th>注册时间</th><th style="text-align:right;">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.user_id">
            <td class="au-name">
              {{ u.username }}
              <span v-if="user && u.user_id === user.user_id" class="au-self">（我）</span>
            </td>
            <td>
              <span class="au-role" :class="u.role">{{ ROLE_LABEL[u.role] || u.role }}</span>
            </td>
            <td class="au-date">{{ fmtDate(u.created_at) }}</td>
            <td style="text-align:right;">
              <button
                v-if="u.role !== 'root' && (!user || u.user_id !== user.user_id)"
                class="btn btn-ghost btn-sm"
                :disabled="busyId === u.user_id"
                @click="toggleRole(u)"
              >
                {{ u.role === 'admin' ? '取消管理员' : '设为管理员' }}
              </button>
              <span v-else class="au-locked">—</span>
            </td>
          </tr>
          <tr v-if="!users.length"><td colspan="4" class="au-empty">暂无用户</td></tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<style scoped>
.au-head { display: flex; align-items: center; gap: 12px; margin: 6px 0 8px; }
.au-head h2 { font-size: 20px; margin: 0; }
.au-hint { color: var(--ink-500); font-size: 13px; margin: 0 0 16px; line-height: 1.6; }
.au-error { padding: 10px 14px; margin-bottom: 14px; border-radius: 10px; background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C); font-size: 13px; }
.au-card { background: #fff; border: 1px solid var(--ink-200); border-radius: 14px; padding: 8px 22px; }
.au-empty { padding: 28px 16px; text-align: center; color: var(--ink-500); font-size: 13px; }
.au-table { width: 100%; border-collapse: collapse; }
.au-table th, .au-table td { padding: 12px 8px; border-bottom: 1px solid var(--ink-100, #F1F5F9); text-align: left; font-size: 14px; }
.au-table th { color: var(--ink-500); font-size: 12px; font-weight: 600; }
.au-name { color: var(--ink-800, #1E293B); font-weight: 600; }
.au-self { color: var(--ink-400, #94A3B8); font-size: 12px; font-weight: 400; }
.au-date { color: var(--ink-500); font-size: 13px; }
.au-role { font-size: 12px; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
.au-role.root { background: var(--violet-100, #EDE9FE); color: var(--violet-600, #7C3AED); }
.au-role.admin { background: var(--brand-50, #EEF2FF); color: var(--brand-700, #4338CA); }
.au-role.user { background: var(--ink-100, #F1F5F9); color: var(--ink-600, #475569); }
.au-locked { color: var(--ink-300, #CBD5E1); }
</style>
