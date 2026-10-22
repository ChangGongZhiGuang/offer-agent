<!-- frontend/src/components/AdminUsers.vue -->
<script setup>
import { ref, onMounted } from 'vue';
import { listUsers, setUserRole, adminDeactivateUser, adminRestoreUser } from '../api.js';
import { useAuth } from '../composables/useAuth.js';

const { user } = useAuth();

const loading = ref(true);
const busyId = ref('');
const error = ref('');
const users = ref([]);

// 注销他人二次确认: 弹窗内必须输入对方用户名全文匹配
const cancelTarget = ref(null);
const cancelInput = ref('');
const cancelError = ref('');

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

function openCancel(u) {
  cancelTarget.value = u;
  cancelInput.value = '';
  cancelError.value = '';
}
function closeCancel() {
  cancelTarget.value = null;
  cancelInput.value = '';
  cancelError.value = '';
}

async function confirmCancel() {
  const t = cancelTarget.value;
  if (!t) return;
  if (cancelInput.value !== t.username) {
    cancelError.value = `请输入正确的用户名「${t.username}」以确认注销`;
    return;
  }
  busyId.value = t.user_id;
  cancelError.value = '';
  try {
    await adminDeactivateUser(t.user_id);
    closeCancel();
    await load();
  } catch (e) {
    cancelError.value = e.message || String(e);
  } finally {
    busyId.value = '';
  }
}

async function restore(u) {
  if (!window.confirm(`确定恢复已注销账号「${u.username}」吗？`)) return;
  busyId.value = u.user_id;
  error.value = '';
  try {
    await adminRestoreUser(u.user_id);
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
      仅超级管理员可访问。在这里将普通用户设为管理员（可管理岗位广场与题库），或取消管理员；
      也可注销普通用户/管理员账号（软删除, 数据保留, 可恢复）。超级管理员账号与当前登录的自己不可注销。
    </p>

    <div v-if="error" class="au-error">{{ error }}</div>

    <div v-if="loading" class="au-empty">加载中…</div>

    <section v-else class="au-card">
      <table class="au-table">
        <thead>
          <tr><th>用户名</th><th>角色</th><th>状态</th><th>注册时间</th><th style="text-align:right;">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.user_id" :class="{ 'au-dead': u.status === 'deleted' }">
            <td class="au-name">
              {{ u.username }}
              <span v-if="user && u.user_id === user.user_id" class="au-self">（我）</span>
            </td>
            <td>
              <span class="au-role" :class="u.role">{{ ROLE_LABEL[u.role] || u.role }}</span>
            </td>
            <td>
              <span class="au-status" :class="u.status === 'deleted' ? 'deleted' : 'active'">
                {{ u.status === 'deleted' ? '已注销' : '正常' }}
              </span>
            </td>
            <td class="au-date">{{ fmtDate(u.created_at) }}</td>
            <td style="text-align:right;">
              <template v-if="u.status === 'deleted'">
                <button class="btn btn-ghost btn-sm" :disabled="busyId === u.user_id" @click="restore(u)">恢复</button>
              </template>
              <template v-else>
                <button
                  v-if="u.role !== 'root' && (!user || u.user_id !== user.user_id)"
                  class="btn btn-ghost btn-sm"
                  :disabled="busyId === u.user_id"
                  @click="toggleRole(u)"
                >
                  {{ u.role === 'admin' ? '取消管理员' : '设为管理员' }}
                </button>
                <button
                  v-if="u.role !== 'root' && (!user || u.user_id !== user.user_id)"
                  class="btn btn-sm au-cancel"
                  :disabled="busyId === u.user_id"
                  @click="openCancel(u)"
                >注销</button>
                <span v-if="u.role === 'root' || (user && u.user_id === user.user_id)" class="au-locked">—</span>
              </template>
            </td>
          </tr>
          <tr v-if="!users.length"><td colspan="5" class="au-empty">暂无用户</td></tr>
        </tbody>
      </table>
    </section>

    <!-- 注销二次确认弹窗: 必须输入对方用户名全文匹配 -->
    <div v-if="cancelTarget" class="au-mask" @click.self="closeCancel">
      <div class="au-confirm">
        <h3>注销账号</h3>
        <p class="au-c-tip">
          即将注销「<b>{{ cancelTarget.username }}</b>」。
          注销后该账号无法登录, 历史/简历数据保留, 后续可在本页恢复。
        </p>
        <p class="au-c-label">请输入对方用户名 <b>「{{ cancelTarget.username }}」</b> 以确认：</p>
        <input
          v-model="cancelInput"
          class="au-c-input"
          :class="{ invalid: cancelError }"
          placeholder="逐字输入用户名"
          @keyup.enter="confirmCancel"
        />
        <div v-if="cancelError" class="au-c-err">{{ cancelError }}</div>
        <div class="au-c-actions">
          <button class="btn btn-ghost btn-sm" @click="closeCancel">取消</button>
          <button class="btn btn-sm au-cancel" :disabled="busyId === cancelTarget.user_id" @click="confirmCancel">
            {{ busyId === cancelTarget.user_id ? '处理中…' : '确认注销' }}
          </button>
        </div>
      </div>
    </div>
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

/* 状态列与注销/恢复: scoped 样式自定义 */
.au-status { font-size: 12px; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
.au-status.active { background: var(--green-50, #F0FDF4); color: var(--green-700, #15803D); }
.au-status.deleted { background: var(--ink-100, #F1F5F9); color: var(--ink-400, #94A3B8); }
.au-cancel { background: var(--red-600, #DC2626); color: #fff; border: none; margin-left: 8px; }
.au-cancel:hover:not(:disabled) { background: var(--red-700, #B91C1C); }
tr.au-dead td { opacity: .55; }

.au-mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: center; justify-content: center; z-index: 60; }
.au-confirm { background: #fff; border-radius: 14px; box-shadow: 0 20px 50px rgba(15,23,42,.22); width: 400px; max-width: calc(100vw - 40px); padding: 20px 22px; }
.au-confirm h3 { font-size: 16px; margin: 0 0 10px; color: var(--red-700, #B91C1C); }
.au-c-tip { font-size: 13px; color: var(--ink-600, #475569); margin: 0 0 12px; line-height: 1.6; }
.au-c-label { font-size: 13px; color: var(--ink-700, #334155); margin: 0 0 6px; }
.au-c-input {
  width: 100%; box-sizing: border-box; height: 38px; padding: 0 12px;
  border: 1px solid var(--ink-200, #E2E8F0); border-radius: 8px;
  font-family: inherit; font-size: 14px; outline: none;
}
.au-c-input:focus { border-color: var(--red-500, #EF4444); }
.au-c-input.invalid { border-color: var(--red-500, #EF4444); }
.au-c-err { margin-top: 8px; font-size: 12px; color: var(--red-700, #B91C1C); }
.au-c-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
</style>
