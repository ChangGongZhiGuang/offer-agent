<!-- frontend/src/components/AuthView.vue -->
<script setup>
import { ref, computed } from 'vue';
import { useAuth } from '../composables/useAuth.js';

const emit = defineEmits(['success', 'close']);
const { login, register, busy, error } = useAuth();

// tab: 'login' | 'register'
const tab = ref('login');
const username = ref('');
const password = ref('');
const confirm = ref('');

// 用户名: 3-16 位字母/数字/-/_  (与后端规则一致)
const USERNAME_RE = /^[A-Za-z0-9_-]{3,16}$/;

const localError = ref('');
const usernameOk = computed(() => USERNAME_RE.test(username.value));
const canSubmit = computed(() => {
  if (!usernameOk.value) return false;
  if (password.value.length < 6) return false;
  if (tab.value === 'register' && password.value !== confirm.value) return false;
  return !busy.value;
});

function switchTab(t) {
  tab.value = t;
  localError.value = '';
  error.value = '';
}

async function submit() {
  localError.value = '';
  if (!usernameOk.value) { localError.value = '用户名需为 3-16 位字母/数字/-/_'; return; }
  if (password.value.length < 6) { localError.value = '密码至少 6 位'; return; }
  if (tab.value === 'register' && password.value !== confirm.value) {
    localError.value = '两次输入的密码不一致'; return;
  }
  try {
    if (tab.value === 'login') await login(username.value, password.value);
    else await register(username.value, password.value);
    emit('success');
  } catch (_) {
    // 错误已由 composable 写入 error.value, 模板展示
  }
}
</script>

<template>
  <div class="modal-mask open" @click.self="emit('close')">
    <div class="modal auth-modal">
      <div class="modal-h">
        <span class="mh-ic">
          <svg viewBox="0 0 24 24" fill="none" width="20" height="20"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.7"/><path d="M4 20a8 8 0 0116 0" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        </span>
        <div>
          <h3>{{ tab === 'login' ? '登录 OfferAgent' : '注册新账号' }}</h3>
          <p class="mh-sub">登录后可保存并回看你的面试历史</p>
        </div>
      </div>

      <div class="modal-b">
        <div class="seg-pick auth-tabs">
          <button :class="{ on: tab === 'login' }" @click="switchTab('login')">登录</button>
          <button :class="{ on: tab === 'register' }" @click="switchTab('register')">注册</button>
        </div>

        <div class="field">
          <label>用户名 <span class="req">*</span></label>
          <input
            v-model="username"
            :class="{ invalid: username && !usernameOk }"
            placeholder="3-16 位字母 / 数字 / - / _"
            autocomplete="username"
            @keyup.enter="submit"
          />
          <span v-if="username && !usernameOk" class="field-hint err">不符合命名规则</span>
        </div>

        <div class="field">
          <label>密码 <span class="req">*</span></label>
          <input
            v-model="password"
            type="password"
            placeholder="至少 6 位"
            :autocomplete="tab === 'login' ? 'current-password' : 'new-password'"
            @keyup.enter="submit"
          />
        </div>

        <div v-if="tab === 'register'" class="field">
          <label>确认密码 <span class="req">*</span></label>
          <input
            v-model="confirm"
            type="password"
            placeholder="再输入一次密码"
            :class="{ invalid: confirm && confirm !== password }"
            autocomplete="new-password"
            @keyup.enter="submit"
          />
          <span v-if="confirm && confirm !== password" class="field-hint err">两次输入不一致</span>
        </div>

        <div v-if="localError || error" class="auth-error">{{ localError || error }}</div>
      </div>

      <div class="modal-f">
        <button class="btn btn-ghost" @click="emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="!canSubmit" @click="submit">
          {{ busy ? '处理中…' : (tab === 'login' ? '登录' : '注册并登录') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 弹窗遮罩与卡片: 与题库页同构, 但 scoped 样式不跨组件共享, 故在此自带一份 */
.modal-mask { position:fixed; inset:0; background:rgba(15,23,42,.45); display:flex; align-items:center; justify-content:center; z-index:60; opacity:1; pointer-events:auto; }
.modal { background:var(--paper); border-radius:var(--r-xl); box-shadow:var(--sh-lg); width:520px; max-width:calc(100vw - 40px); }
.modal-h { display:flex; align-items:flex-start; gap:14px; padding:22px 24px 18px; border-bottom:1px solid var(--ink-100); }
.mh-ic { width:40px; height:40px; border-radius:12px; background:var(--brand-50); color:var(--brand-600); display:grid; place-items:center; flex:none; }
.modal-h h3 { font-size:16px; margin-bottom:3px; }
.modal-b { padding:18px 24px; display:flex; flex-direction:column; gap:16px; }
.modal-f { display:flex; align-items:center; justify-content:flex-end; gap:10px; padding:0 24px 22px; }
.field { display:flex; flex-direction:column; gap:6px; }
.field label { font-size:13px; font-weight:600; color:var(--ink-700); }
.field input {
  height:40px; padding:0 12px; border:1px solid var(--ink-200); border-radius:var(--r-md);
  font-family:inherit; font-size:14px; color:var(--ink-900); background:var(--paper);
  outline:none; transition:border-color .15s;
}
.field input:focus { border-color:var(--brand-400); }
.req { color:var(--red-600); }

.auth-modal { width: 380px; max-width: 92vw; }
.mh-sub { margin: 2px 0 0; font-size: 12px; color: var(--ink-500); }
.auth-tabs { display: flex; gap: 0; margin-bottom: 18px; }
.auth-tabs button {
  flex: 1; padding: 9px 0; border: 1px solid var(--ink-200); background: #fff;
  color: var(--ink-600); font-weight: 600; cursor: pointer; font-size: 14px;
}
.auth-tabs button:first-child { border-radius: 8px 0 0 8px; }
.auth-tabs button:last-child { border-radius: 0 8px 8px 0; border-left: none; }
.auth-tabs button.on { background: var(--brand-500); border-color: var(--brand-500); color: #fff; }
.field input.invalid { border-color: var(--red-500, #EF4444); }
.field-hint { display: block; margin-top: 4px; font-size: 12px; }
.field-hint.err { color: var(--red-600, #DC2626); }
.auth-error {
  margin-top: 6px; padding: 9px 12px; border-radius: 8px; font-size: 13px;
  background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C);
  border: 1px solid rgba(220, 38, 38, .18);
}
</style>
