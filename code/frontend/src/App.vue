<script setup>
import { ref, onMounted } from 'vue';
import JobBoard from './components/JobBoard.vue';
import SetupView from './components/SetupView.vue';
import PlanView from './components/PlanView.vue';
import InterviewView from './components/InterviewView.vue';
import ReportView from './components/ReportView.vue';
import QuestionBankView from './components/QuestionBankView.vue';
import AuthView from './components/AuthView.vue';
import HistoryView from './components/HistoryView.vue';
import ResumeView from './components/ResumeView.vue';
import AdminUsers from './components/AdminUsers.vue';
import { useAuth } from './composables/useAuth.js';

// 登录态 (模块级单例)
const { user, isAuthenticated, isAdmin, isRoot, logout, refreshMe } = useAuth();
const authOpen = ref(false);        // 登录/注册弹层开关
const userMenuOpen = ref(false);    // 右上角用户下拉开关

onMounted(refreshMe);

// 状态机: jobboard → setup → plan → interview → report
const view = ref('jobboard');
const selectedJob = ref(null);
const session = ref(null);
const report = ref(null);

function onSelectJob(job) {
  selectedJob.value = job;
  view.value = 'setup';
}
function onStarted(payload) {
  session.value = payload;
  view.value = 'plan';
}
function onStartInterview() {
  view.value = 'interview-a';
}
function onFinished(r) {
  report.value = r;
  view.value = 'report';
}
function restart() {
  selectedJob.value = null;
  session.value = null;
  report.value = null;
  view.value = 'jobboard';
}

function onAuthSuccess() {
  authOpen.value = false;
}
async function onLogout() {
  await logout();
  userMenuOpen.value = false;
  // 登出后若停在历史记录/我的简历/用户管理页, 退回岗位广场
  if (['history', 'resume', 'users'].includes(view.value)) view.value = 'jobboard';
}

const isInterview = (v) => v === 'interview-a';

// Nav 跳转：根据当前状态决定能跳到哪
function navTo(target) {
  if (target === 'jobboard') {
    view.value = 'jobboard';
    return;
  }
  if (target === 'history') {
    view.value = isAuthenticated.value ? 'history' : view.value;
    return;
  }
  if (target === 'resume') {
    view.value = isAuthenticated.value ? 'resume' : view.value;
    return;
  }
  if (target === 'users') {
    // 仅超级管理员可进入用户管理
    view.value = isRoot.value ? 'users' : view.value;
    return;
  }
  if (target === 'qbank') {
    // 仅管理员可进题库管理
    view.value = isAdmin.value ? 'qbank' : view.value;
    return;
  }
  if (target === 'setup') {
    // 有 selectedJob 就带着跳回投递准备，没有就先去岗位广场选
    view.value = selectedJob.value || view.value !== 'jobboard' ? 'setup' : 'jobboard';
    return;
  }
  if (target === 'interview') {
    if (session.value) {
      // 已有会话，回到方向选择或直接回面试
      view.value = isInterview(view.value) ? view.value : 'interview-a';
    } else {
      // 没有会话，先去投递准备创建
      view.value = 'setup';
    }
    return;
  }
  if (target === 'report') {
    if (report.value) {
      view.value = 'report';
    }
    // 没有报告时不跳转（link 视觉上灰暗即可）
  }
}
</script>

<template>
  <nav class="nav">
    <div class="shell">
      <div class="brand">
        <span class="glyph">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 2.5l2.2 6.1 6.3.3-4.9 4 1.7 6.1L12 19.4 6.7 23l1.7-6.1-4.9-4 6.3-.3z" fill="#fff" opacity=".95"/>
          </svg>
        </span>
        OfferAgent
      </div>
      <div class="nav-links">
        <a :class="{ active: view === 'jobboard' }" @click="navTo('jobboard')">岗位广场</a>
        <a :class="{ active: view === 'setup' }" @click="navTo('setup')">我的投递</a>
        <a :class="{ active: isInterview(view) || view === 'plan' }" @click="navTo('interview')">模拟面试</a>
        <a :class="{ active: view === 'report', disabled: !report }" @click="navTo('report')">面试报告</a>
        <a v-if="isAuthenticated" :class="{ active: view === 'history' }" @click="navTo('history')">历史记录</a>
        <a v-if="isAdmin" :class="{ active: view === 'qbank' }" @click="navTo('qbank')">题库管理</a>
      </div>
      <div class="grow"></div>

      <!-- 右上角: 登录/注册 或 用户区 -->
      <div class="user-area">
        <template v-if="!isAuthenticated">
          <button class="btn btn-ghost btn-sm" @click="authOpen = true">登录 / 注册</button>
        </template>
        <div v-else class="user-menu-wrap">
          <button class="user-chip" @click="userMenuOpen = !userMenuOpen">
            <span class="user-avatar">{{ (user?.username || '?').slice(0, 1).toUpperCase() }}</span>
            <span class="user-name">{{ user?.username }}</span>
            <span v-if="isRoot" class="role-badge root">超级管理员</span>
            <span v-else-if="isAdmin" class="role-badge admin">管理员</span>
            <svg viewBox="0 0 24 24" fill="none" width="14" height="14"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
          <div v-if="userMenuOpen" class="user-dropdown">
            <button @click="navTo('resume'); userMenuOpen = false">我的简历</button>
            <button @click="navTo('history'); userMenuOpen = false">历史记录</button>
            <button v-if="isRoot" @click="navTo('users'); userMenuOpen = false">用户管理</button>
            <button class="danger" @click="onLogout">退出登录</button>
          </div>
        </div>
      </div>

      <div v-if="view === 'jobboard' && !isAuthenticated" class="row" style="gap:12px;margin-left:12px;">
        <span class="badge badge-ink mono">v0.9 · agent harness</span>
      </div>
      <span v-else-if="view === 'setup'" class="phase-pill" style="background:var(--brand-50);color:var(--brand-700);">
        <span class="dot" style="background:var(--brand-500);"></span>Phase · Assembler
      </span>
      <span v-else-if="view === 'plan'" class="phase-pill" style="background:var(--brand-50);color:var(--brand-700);">
        <span class="dot" style="background:var(--brand-500);"></span>Phase · PLAN
      </span>
      <span v-else-if="isInterview(view)" class="phase-pill" style="background:var(--ember-50);color:var(--ember-700);">
        <span class="dot" style="background:var(--ember-500);"></span>Phase · EXECUTE
      </span>
      <span v-else-if="view === 'report'" class="phase-pill" style="background:var(--green-50);color:var(--green-700);">
        <span class="dot" style="background:var(--green-600);"></span>Phase · HALT · 完成
      </span>
      <span v-else-if="view === 'qbank'" class="phase-pill" style="background:var(--violet-100);color:var(--violet-600);">
        <span class="dot" style="background:var(--violet-600);"></span>admin · 题库
      </span>
      <span v-else-if="view === 'history'" class="phase-pill" style="background:var(--brand-50);color:var(--brand-700);">
        <span class="dot" style="background:var(--brand-500);"></span>我的历史
      </span>
      <span v-else-if="view === 'resume'" class="phase-pill" style="background:var(--brand-50);color:var(--brand-700);">
        <span class="dot" style="background:var(--brand-500);"></span>我的简历
      </span>
      <span v-else-if="view === 'users'" class="phase-pill" style="background:var(--violet-100);color:var(--violet-600);">
        <span class="dot" style="background:var(--violet-600);"></span>root · 用户管理
      </span>
    </div>
  </nav>

  <JobBoard v-if="view === 'jobboard'" @select-job="onSelectJob" />
  <SetupView v-else-if="view === 'setup'" :job="selectedJob" @started="onStarted" />
  <PlanView v-else-if="view === 'plan' && session" :session="session" @start-interview="onStartInterview" />
  <InterviewView v-else-if="view === 'interview-a' && session" :session="session" @finished="onFinished" />
  <ReportView v-else-if="view === 'report' && report" :report="report" :session-id="session?.session_id || ''" @restart="restart" />
  <HistoryView v-else-if="view === 'history' && isAuthenticated" />
  <ResumeView v-else-if="view === 'resume' && isAuthenticated" />
  <AdminUsers v-else-if="view === 'users' && isRoot" />
  <QuestionBankView v-else-if="view === 'qbank' && isAdmin" />

  <!-- 登录 / 注册 弹层 -->
  <AuthView v-if="authOpen" @success="onAuthSuccess" @close="authOpen = false" />
</template>

<style scoped>
.user-area { margin-left: 12px; }
.user-menu-wrap { position: relative; }
.user-chip {
  display: flex; align-items: center; gap: 8px; padding: 4px 10px 4px 4px;
  border: 1px solid var(--ink-200); border-radius: 999px; background: #fff;
  cursor: pointer; color: var(--ink-700, #334155);
}
.user-chip:hover { border-color: var(--brand-300, #A5B4FC); }
.user-avatar {
  width: 26px; height: 26px; border-radius: 50%; background: var(--brand-500);
  color: #fff; font-size: 13px; font-weight: 700; display: flex;
  align-items: center; justify-content: center;
}
.user-name { font-size: 13px; font-weight: 600; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.role-badge {
  font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 999px;
}
.role-badge.root { background: var(--violet-100, #EDE9FE); color: var(--violet-600, #7C3AED); }
.role-badge.admin { background: var(--brand-50, #EEF2FF); color: var(--brand-700, #4338CA); }
.user-dropdown {
  position: absolute; right: 0; top: calc(100% + 6px); min-width: 140px;
  background: #fff; border: 1px solid var(--ink-200); border-radius: 10px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, .12); padding: 6px; z-index: 40;
}
.user-dropdown button {
  display: block; width: 100%; text-align: left; padding: 8px 10px; border: none;
  background: none; border-radius: 7px; cursor: pointer; font-size: 13px; color: var(--ink-700, #334155);
}
.user-dropdown button:hover { background: var(--ink-50, #F8FAFC); }
.user-dropdown button.danger { color: var(--red-600, #DC2626); }
</style>
