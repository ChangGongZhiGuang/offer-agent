<!-- frontend/src/components/QuestionBankView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue';
import {
  listQuestions, createQuestion, updateQuestion, deleteQuestion,
  listPositions, createPosition, deletePosition,
} from '../api.js';

// ── 状态 ──────────────────────────────────────────────────────
const positions   = ref([]);
const questions   = ref([]);
const posFilter   = ref('all');
const search      = ref('');
const diffFilter  = ref('');
const page        = ref(1);
const PER_PAGE    = 6;

// 弹窗：录入/编辑题目 (editingId 为 null=录入, 非空=编辑)
const qModal      = ref(false);
const editingId   = ref(null);
const fText       = ref('');
const fPos        = ref('');
const fDim        = ref('');
const fAnswer     = ref('');
const fDiff       = ref('mid');
const fFu         = ref('');
const fTextError  = ref(false);
const saving      = ref(false);

// 弹窗：添加岗位
const posModal    = ref(false);
const fPosName    = ref('');
const fPosColor   = ref('#4F46E5');
const fPosError   = ref(false);
const savingPos   = ref(false);

// Toast
const toastMsg    = ref('');
const toastShow   = ref(false);
let toastTimer    = null;

const PALETTE = [
  '#4F46E5','#EA580C','#7C3AED','#0284C7',
  '#059669','#DC2626','#D97706','#0F172A',
];

const DIFF_MAP = {
  easy: { label: '简单', cls: 'diff-easy' },
  mid:  { label: '中等', cls: 'diff-mid'  },
  hard: { label: '困难', cls: 'diff-hard' },
};

// ── 计算属性 ──────────────────────────────────────────────────
const filtered = computed(() => {
  return questions.value.filter(q => {
    if (posFilter.value !== 'all' && q.role !== posFilter.value) return false;
    if (diffFilter.value && q.diff !== diffFilter.value) return false;
    if (search.value) {
      const s = search.value.toLowerCase();
      if (!(q.stem + ' ' + (q.topic || '')).toLowerCase().includes(s)) return false;
    }
    return true;
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PER_PAGE)));

const pageItems = computed(() => {
  const start = (page.value - 1) * PER_PAGE;
  return filtered.value.slice(start, start + PER_PAGE);
});

const pgFrom = computed(() =>
  filtered.value.length === 0 ? 0 : (page.value - 1) * PER_PAGE + 1);
const pgTo = computed(() =>
  Math.min(page.value * PER_PAGE, filtered.value.length));

const statTotal = computed(() => questions.value.length);
const statPos   = computed(() => positions.value.length);
const statHard  = computed(() => questions.value.filter(q => q.diff === 'hard').length);
const statFu    = computed(() => questions.value.filter(q => q.fu && q.fu.trim()).length);

// ── 辅助 ──────────────────────────────────────────────────────
function hex2bg(hex) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0,2),16), g = parseInt(h.slice(2,4),16), b = parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},0.10)`;
}

function posColor(roleName) {
  const p = positions.value.find(p => p.name === roleName);
  return p ? p.color : '#64748B';
}

function padId(id) { return String(id).padStart(3, '0'); }

function toast(msg) {
  toastMsg.value = msg;
  toastShow.value = true;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastShow.value = false; }, 2200);
}

// ── 数据加载 ──────────────────────────────────────────────────
async function loadAll() {
  const [pos, qs] = await Promise.all([listPositions(), listQuestions()]);
  positions.value = pos;
  questions.value = qs;
  if (!fPos.value && pos.length > 0) fPos.value = pos[0].name;
}

onMounted(loadAll);

// ── 过滤/翻页 ─────────────────────────────────────────────────
function setFilter(role) { posFilter.value = role; page.value = 1; }
function onSearch(e) { search.value = e.target.value; page.value = 1; }
function onDiffChange(e) { diffFilter.value = e.target.value; page.value = 1; }

// ── 删除题目 ──────────────────────────────────────────────────
async function delQuestion(id) {
  await deleteQuestion(id);
  questions.value = questions.value.filter(q => q.id !== id);
  toast(`已删除题目 #${padId(id)}`);
}

// ── 录入题目弹窗 ──────────────────────────────────────────────
function openQModal() {
  editingId.value = null;
  fText.value = ''; fDim.value = ''; fAnswer.value = ''; fFu.value = '';
  fDiff.value = 'mid'; fTextError.value = false;
  if (posFilter.value !== 'all') {
    const p = positions.value.find(p => p.name === posFilter.value || p.id === posFilter.value);
    fPos.value = p ? p.name : (positions.value[0]?.name || '');
  } else {
    fPos.value = positions.value[0]?.name || '';
  }
  qModal.value = true;
}

// ── 编辑题目弹窗 ──────────────────────────────────────────────
function openEditModal(q) {
  editingId.value = q.id;
  fText.value = q.stem || '';
  fPos.value = q.role || (positions.value[0]?.name || '');
  fDim.value = (q.topic && q.topic !== '通用') ? q.topic : '';
  fAnswer.value = q.answer || '';
  fDiff.value = q.diff || 'mid';
  fFu.value = q.fu || '';
  fTextError.value = false;
  qModal.value = true;
}

async function saveQuestion() {
  if (!fText.value.trim()) { fTextError.value = true; return; }
  saving.value = true;
  try {
    const payload = {
      stem: fText.value.trim(), role: fPos.value,
      topic: fDim.value.trim() || '通用', answer: fAnswer.value.trim(),
      difficulty: fDiff.value, fu: fFu.value.trim(),
    };
    if (editingId.value) {
      const q = await updateQuestion(editingId.value, payload);
      const i = questions.value.findIndex(x => x.id === editingId.value);
      if (i !== -1) questions.value[i] = q;
      qModal.value = false;
      toast('题目已更新');
    } else {
      const ts = Date.now();
      const rand = Math.random().toString(36).slice(2, 6);
      const q = await createQuestion({ id: `q-${ts}-${rand}`, ...payload });
      const BACK = { easy: 'easy', medium: 'mid', hard: 'hard' };
      questions.value.unshift({ ...q, diff: BACK[q.difficulty] || q.difficulty });
      page.value = 1;
      qModal.value = false;
      toast('题目已录入题库');
    }
  } finally {
    saving.value = false;
  }
}

// ── 添加岗位弹窗 ──────────────────────────────────────────────
function openPosModal() {
  fPosName.value = ''; fPosError.value = false;
  fPosColor.value = PALETTE[positions.value.length % PALETTE.length];
  posModal.value = true;
}

async function delPosition(p) {
  const cnt = questions.value.filter(q => q.role === p.name).length;
  const msg = cnt > 0
    ? `确定删除岗位「${p.name}」？其下 ${cnt} 道题目将一并删除，不可恢复。`
    : `确定删除岗位「${p.name}」？`;
  if (!confirm(msg)) return;
  try {
    await deletePosition(p.id);
    positions.value = positions.value.filter(x => x.id !== p.id);
    questions.value = questions.value.filter(q => q.role !== p.name);
    if (posFilter.value === p.name) posFilter.value = 'all';
    toast(cnt > 0 ? `已删除岗位「${p.name}」及 ${cnt} 道题目` : `已删除岗位「${p.name}」`);
  } catch (e) {
    toast(e.message || '删除失败');
  }
}

async function savePosition() {
  if (!fPosName.value.trim()) { fPosError.value = true; return; }
  savingPos.value = true;
  try {
    const p = await createPosition({ name: fPosName.value.trim(), color: fPosColor.value });
    positions.value.push(p);
    posFilter.value = p.name;
    posModal.value = false;
    toast(`已添加岗位「${p.name}」`);
  } finally {
    savingPos.value = false;
  }
}

// ESC 关闭弹窗
function onKeydown(e) { if (e.key === 'Escape') { qModal.value = false; posModal.value = false; } }
</script>

<template>
  <div @keydown="onKeydown" tabindex="-1" style="outline:none;">

  <main class="shell qb-page">
    <!-- 面包屑 -->
    <div class="crumb">
      <span>OfferAgent</span><span>/</span><span class="c-now">题库管理</span>
    </div>

    <!-- 标题行 -->
    <div class="head-row">
      <div>
        <h1 class="ptitle">题库管理 · 录入题目</h1>
        <p class="psub">按岗位维护题库。Examiner 出题时从这里检索去重，追问树定义答得好 / 答得卡的分支走向。</p>
      </div>
      <div class="row" style="gap:10px;">
        <button class="btn btn-ghost" @click="openPosModal">
          <svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          添加岗位
        </button>
        <button class="btn btn-primary" @click="openQModal">
          <svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          录入题目
        </button>
      </div>
    </div>

    <!-- 统计栏 -->
    <div class="stats">
      <div class="stat"><div class="s-n">{{ statTotal }}</div><div class="s-l"><span class="sd" style="background:var(--brand-500);"></span>题目总数</div></div>
      <div class="stat"><div class="s-n">{{ statPos }}</div><div class="s-l"><span class="sd" style="background:var(--ember-500);"></span>覆盖岗位</div></div>
      <div class="stat"><div class="s-n">{{ statHard }}</div><div class="s-l"><span class="sd" style="background:var(--ember-600);"></span>高难度题</div></div>
      <div class="stat"><div class="s-n">{{ statFu }}</div><div class="s-l"><span class="sd" style="background:var(--green-600);"></span>含追问树</div></div>
    </div>

    <!-- 主布局 -->
    <div class="layout">
      <!-- 侧边栏：岗位分类 -->
      <aside class="side">
        <div class="side-h">
          <span class="sh-t">岗位分类</span>
          <button class="add-pos" title="添加岗位" @click="openPosModal">
            <svg viewBox="0 0 24 24" fill="none" width="14" height="14"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
          </button>
        </div>
        <div class="pos-list">
          <div :class="['pos-item', posFilter === 'all' ? 'on' : '']" @click="setFilter('all')">
            <span class="pdot" style="background:var(--ink-400);"></span>
            <span class="pname">全部岗位</span>
            <span class="pcount">{{ questions.length }}</span>
          </div>
          <div
            v-for="p in positions" :key="p.id"
            :class="['pos-item', posFilter === p.name ? 'on' : '']"
            @click="setFilter(p.name)"
          >
            <span class="pdot" :style="{ background: p.color }"></span>
            <span class="pname">{{ p.name }}</span>
            <span class="pcount">{{ questions.filter(q => q.role === p.name).length }}</span>
            <button class="pos-del" title="删除岗位" @click.stop="delPosition(p)">
              <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
            </button>
          </div>
        </div>
      </aside>

      <!-- 题目列表面板 -->
      <section class="panel">
        <div class="toolbar">
          <div class="search">
            <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M20 20l-3-3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            <input :value="search" @input="onSearch" placeholder="搜索题目内容、维度…">
          </div>
          <select class="filter-sel" :value="diffFilter" @change="onDiffChange">
            <option value="">全部难度</option>
            <option value="easy">简单</option>
            <option value="mid">中等</option>
            <option value="hard">困难</option>
          </select>
        </div>

        <div id="tableWrap">
          <table>
            <thead>
              <tr>
                <th style="width:64px;">编号</th>
                <th>题目 · 维度</th>
                <th style="width:130px;">岗位</th>
                <th style="width:90px;">难度</th>
                <th style="width:104px;text-align:right;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in pageItems" :key="q.id">
                <td><span class="q-id">#{{ padId(q.id) }}</span></td>
                <td>
                  <div class="q-text">{{ q.stem }}</div>
                  <div class="q-fu"><span class="tag-mono">{{ q.topic || '通用' }}</span></div>
                  <div v-if="q.fu && q.fu.trim()" class="q-fu" style="color:var(--ink-500);">
                    <svg viewBox="0 0 24 24" fill="none" width="12" height="12"><path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    追问：{{ q.fu }}
                  </div>
                </td>
                <td class="col-pos">
                  <span class="pos-tag"
                    :style="{ background: hex2bg(posColor(q.role)), color: posColor(q.role) }">
                    <span class="pt-dot" :style="{ background: posColor(q.role) }"></span>
                    {{ q.role }}
                  </span>
                </td>
                <td>
                  <span :class="['diff', DIFF_MAP[q.diff]?.cls || 'diff-mid']">
                    {{ DIFF_MAP[q.diff]?.label || q.diff }}
                  </span>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="icon-btn" title="编辑" @click="openEditModal(q)">
                      <svg viewBox="0 0 24 24" fill="none"><path d="M4 20h4L18.5 9.5a2.12 2.12 0 00-3-3L5 17v3z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M13.5 6.5l3 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
                    </button>
                    <button class="icon-btn del" title="删除" @click="delQuestion(q.id)">
                      <svg viewBox="0 0 24 24" fill="none"><path d="M5 7h14M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m2 0v12a1 1 0 01-1 1H8a1 1 0 01-1-1V7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="filtered.length === 0" class="empty">
            <svg viewBox="0 0 24 24" fill="none"><path d="M9 3h7l4 4v14H5V5a2 2 0 012-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 13h6M9 17h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            <div>没有匹配的题目</div>
          </div>
        </div>

        <div class="pager">
          <div class="p-info">第 <b>{{ pgFrom }}</b>–<b>{{ pgTo }}</b> 条 · 共 <b>{{ filtered.length }}</b> 条</div>
          <div class="pages">
            <button class="pg-btn" :disabled="page <= 1" @click="page--">
              <svg viewBox="0 0 24 24" fill="none"><path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button
              v-for="n in totalPages" :key="n"
              :class="['pg-btn', n === page ? 'on' : '']"
              @click="page = n"
            >{{ n }}</button>
            <button class="pg-btn" :disabled="page >= totalPages" @click="page++">
              <svg viewBox="0 0 24 24" fill="none"><path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>
      </section>
    </div>
  </main>

  <!-- 录入题目弹窗 -->
  <div :class="['modal-mask', qModal ? 'open' : '']" @click.self="qModal = false">
    <div class="modal">
      <div class="modal-h">
        <span class="mh-ic">
          <svg viewBox="0 0 24 24" fill="none" width="20" height="20"><path d="M9 3h7l4 4v14H5V5a2 2 0 012-2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M12 11v5M9.5 13.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        </span>
        <div>
          <h3>{{ editingId ? '编辑题目' : '录入新题目' }}</h3>
          <div class="mh-sub">{{ editingId ? '修改题目内容与归类，保存后即时生效' : '填写题目内容并归类，可选填追问引导' }}</div>
        </div>
      </div>
      <div class="modal-b">
        <div class="field">
          <label>题目内容 <span class="req">*</span></label>
          <textarea
            v-model="fText"
            :style="fTextError ? 'border-color:var(--red-600)' : ''"
            @input="fTextError = false"
            placeholder="例如：在主从复制架构下，从库为什么可能读到已过期但未删除的数据？"
          ></textarea>
        </div>
        <div class="field-row">
          <div class="field">
            <label>归属岗位 <span class="req">*</span></label>
            <select v-model="fPos">
              <option v-for="p in positions" :key="p.id" :value="p.name">{{ p.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>考察维度</label>
            <input v-model="fDim" placeholder="如 缓存 / Redis">
          </div>
        </div>
        <div class="field">
          <label>参考答案</label>
          <textarea v-model="fAnswer" placeholder="如 SETNX + 过期时间 + 唯一 value，释放时校验 value" style="min-height:72px;"></textarea>
        </div>
        <div class="field">
          <label>难度</label>
          <div class="seg-pick">
            <button :class="fDiff === 'easy' ? 'on' : ''" @click="fDiff = 'easy'">简单</button>
            <button :class="fDiff === 'mid'  ? 'on' : ''" @click="fDiff = 'mid'">中等</button>
            <button :class="fDiff === 'hard' ? 'on' : ''" @click="fDiff = 'hard'">困难</button>
          </div>
        </div>
        <div class="field">
          <label>追问引导（可选）</label>
          <input v-model="fFu" placeholder="如 答得好 → 深挖持久化取舍；答得卡 → 提示先想 key 失效瞬间">
        </div>
      </div>
      <div class="modal-f">
        <button class="btn btn-ghost" @click="qModal = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveQuestion">
          {{ saving ? '保存中…' : (editingId ? '保存修改' : '保存题目') }}
        </button>
      </div>
    </div>
  </div>

  <!-- 添加岗位弹窗 -->
  <div :class="['modal-mask', posModal ? 'open' : '']" @click.self="posModal = false">
    <div class="modal sm">
      <div class="modal-h">
        <span class="mh-ic" style="background:var(--ember-50);color:var(--ember-600);">
          <svg viewBox="0 0 24 24" fill="none" width="20" height="20"><path d="M3 7a2 2 0 012-2h5l2 2h6a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
        </span>
        <div><h3>添加岗位</h3><div class="mh-sub">新建一个题库分类，如「前端」「算法」</div></div>
      </div>
      <div class="modal-b">
        <div class="field">
          <label>岗位名称 <span class="req">*</span></label>
          <input
            v-model="fPosName"
            :style="fPosError ? 'border-color:var(--red-600)' : ''"
            @input="fPosError = false"
            placeholder="如 前端工程师"
          >
        </div>
        <div class="field">
          <label>标识色</label>
          <div class="swatches">
            <div
              v-for="c in PALETTE" :key="c"
              :class="['swatch', fPosColor === c ? 'on' : '']"
              :style="{ background: c }"
              @click="fPosColor = c"
            ></div>
          </div>
        </div>
      </div>
      <div class="modal-f">
        <button class="btn btn-ghost" @click="posModal = false">取消</button>
        <button class="btn btn-ember" :disabled="savingPos" @click="savePosition">
          {{ savingPos ? '添加中…' : '添加岗位' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Toast -->
  <div :class="['toast', toastShow ? 'show' : '']">
    <svg viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#34D399" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span>{{ toastMsg }}</span>
  </div>

  </div>
</template>

<style scoped>
.qb-page { padding:30px 0 70px; }
.crumb { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink-400); margin-bottom:18px; }
.crumb .c-now { color:var(--ink-700); font-weight:600; }

.head-row { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:24px; }
.ptitle { font-size:30px; letter-spacing:-0.025em; }
.psub { color:var(--ink-500); font-size:15px; margin-top:7px; max-width:620px; }

/* stat strip */
.stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:24px; }
.stat { background:var(--paper); border:1px solid var(--ink-200); border-radius:var(--r-lg); padding:16px 18px; box-shadow:var(--sh-xs); }
.stat .s-n { font-family:var(--font-display); font-size:26px; font-weight:700; color:var(--ink-950); }
.stat .s-l { font-size:12.5px; color:var(--ink-500); margin-top:3px; display:flex; align-items:center; gap:6px; }
.stat .s-l .sd { width:7px; height:7px; border-radius:50%; }

/* layout */
.layout { display:grid; grid-template-columns:240px 1fr; gap:22px; align-items:start; }

/* sidebar */
.side { background:var(--paper); border:1px solid var(--ink-200); border-radius:var(--r-lg); box-shadow:var(--sh-xs); padding:16px; position:sticky; top:84px; }
.side-h { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.side-h .sh-t { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:var(--ink-400); }
.add-pos { width:24px; height:24px; border-radius:7px; display:grid; place-items:center; background:var(--brand-50); color:var(--brand-600); transition:background .15s; border:none; cursor:pointer; }
.add-pos:hover { background:var(--brand-100); }
.pos-list { display:flex; flex-direction:column; gap:3px; }
.pos-item { display:flex; align-items:center; gap:10px; padding:9px 11px; border-radius:var(--r-sm); font-size:13.5px; color:var(--ink-700); cursor:pointer; transition:background .14s; }
.pos-item:hover { background:var(--ink-50); }
.pos-item.on { background:var(--ink-900); color:#fff; }
.pos-item .pdot { width:9px; height:9px; border-radius:50%; flex:none; }
.pos-item .pname { flex:1; font-weight:500; }
.pos-item .pcount { font-family:var(--font-mono); font-size:11.5px; color:var(--ink-400); }
.pos-item.on .pcount { color:var(--ink-300); }
.pos-item .pos-del { display:none; width:20px; height:20px; border-radius:6px; place-items:center; flex:none; border:none; cursor:pointer; background:none; color:var(--ink-400); transition:all .14s; }
.pos-item:hover .pos-del { display:grid; }
.pos-item:hover .pcount { display:none; }
.pos-item .pos-del:hover { background:var(--red-50, #FEF2F2); color:var(--red-600, #DC2626); }
.pos-item.on .pos-del { color:var(--ink-300); }
.pos-item.on .pos-del:hover { background:rgba(255,255,255,.18); color:#fff; }

/* panel */
.panel { background:var(--paper); border:1px solid var(--ink-200); border-radius:var(--r-lg); box-shadow:var(--sh-sm); overflow:hidden; }
.toolbar { display:flex; align-items:center; gap:12px; padding:16px 20px; border-bottom:1px solid var(--ink-100); }
.search { flex:1; display:flex; align-items:center; gap:9px; height:40px; padding:0 14px; background:var(--ink-50); border:1px solid var(--ink-200); border-radius:var(--r-md); color:var(--ink-400); }
.search svg { width:16px; height:16px; }
.search input { border:none; outline:none; flex:1; font-family:inherit; font-size:14px; color:var(--ink-800); background:none; }
.filter-sel { height:40px; padding:0 12px; border:1px solid var(--ink-200); border-radius:var(--r-md); background:var(--paper); font-family:inherit; font-size:13.5px; color:var(--ink-700); font-weight:500; cursor:pointer; }

/* table */
table { width:100%; border-collapse:collapse; }
thead th { text-align:left; font-size:11.5px; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-400); padding:13px 16px; border-bottom:1px solid var(--ink-100); background:var(--ink-50); }
tbody td { padding:15px 16px; border-bottom:1px solid var(--ink-100); font-size:14px; vertical-align:top; }
tbody tr { transition:background .12s; }
tbody tr:hover { background:var(--ink-50); }
tbody tr:last-child td { border-bottom:0; }
.q-id { font-family:var(--font-mono); font-size:12px; color:var(--ink-400); white-space:nowrap; }
.q-text { color:var(--ink-900); font-weight:500; line-height:1.5; max-width:440px; }
.q-fu { font-size:12px; color:var(--ink-400); margin-top:5px; display:flex; align-items:center; gap:6px; }
.col-pos { white-space:nowrap; }
.pos-tag { display:inline-flex; align-items:center; gap:6px; height:26px; padding:0 11px; border-radius:var(--r-full); font-size:12.5px; font-weight:600; }
.pos-tag .pt-dot { width:7px; height:7px; border-radius:50%; }
.diff { display:inline-flex; font-size:11.5px; font-weight:700; padding:3px 10px; border-radius:var(--r-full); white-space:nowrap; }
.diff-easy { background:var(--green-50); color:var(--green-700); }
.diff-mid { background:var(--sky-100); color:var(--sky-600); }
.diff-hard { background:var(--ember-100); color:var(--ember-700); }
.row-actions { display:flex; gap:6px; justify-content:flex-end; }
.icon-btn { width:32px; height:32px; border-radius:var(--r-sm); display:grid; place-items:center; color:var(--ink-400); transition:all .14s; border:none; cursor:pointer; background:none; }
.icon-btn:hover { background:var(--ink-100); color:var(--ink-700); }

/* empty */
.empty { display:flex; flex-direction:column; align-items:center; gap:12px; padding:52px 20px; color:var(--ink-300); }
.empty svg { width:40px; height:40px; }
.empty div { font-size:14px; }

/* pager */
.pager { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; border-top:1px solid var(--ink-100); }
.p-info { font-size:13px; color:var(--ink-500); }
.pages { display:flex; align-items:center; gap:4px; }
.pg-btn { width:32px; height:32px; border-radius:var(--r-sm); display:grid; place-items:center; font-size:13px; font-weight:500; color:var(--ink-600); background:none; border:none; cursor:pointer; transition:all .12s; }
.pg-btn:hover:not(:disabled) { background:var(--ink-100); }
.pg-btn.on { background:var(--brand-600); color:#fff; }
.pg-btn:disabled { opacity:.4; cursor:not-allowed; }
.pg-btn svg { width:16px; height:16px; }

/* modal */
.modal-mask { position:fixed; inset:0; background:rgba(15,23,42,.45); display:flex; align-items:center; justify-content:center; z-index:60; opacity:0; pointer-events:none; transition:opacity .18s; }
.modal-mask.open { opacity:1; pointer-events:auto; }
.modal { background:var(--paper); border-radius:var(--r-xl); box-shadow:var(--sh-lg); width:520px; max-width:calc(100vw - 40px); }
.modal.sm { width:380px; }
.modal-h { display:flex; align-items:flex-start; gap:14px; padding:22px 24px 18px; border-bottom:1px solid var(--ink-100); }
.mh-ic { width:40px; height:40px; border-radius:12px; background:var(--brand-50); color:var(--brand-600); display:grid; place-items:center; flex:none; }
.modal-h h3 { font-size:16px; margin-bottom:3px; }
.mh-sub { font-size:13px; color:var(--ink-500); }
.modal-b { padding:18px 24px; display:flex; flex-direction:column; gap:16px; }
.field { display:flex; flex-direction:column; gap:6px; }
.field label { font-size:13px; font-weight:600; color:var(--ink-700); }
.field input, .field select, .field textarea {
  height:40px; padding:0 12px; border:1px solid var(--ink-200); border-radius:var(--r-md);
  font-family:inherit; font-size:14px; color:var(--ink-900); background:var(--paper);
  outline:none; transition:border-color .15s;
}
.field textarea { height:88px; padding:10px 12px; resize:vertical; line-height:1.5; }
.field input:focus, .field select:focus, .field textarea:focus { border-color:var(--brand-400); box-shadow:var(--ring); }
.field-row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.req { color:var(--red-600); }
.seg-pick { display:flex; gap:0; border:1px solid var(--ink-200); border-radius:var(--r-md); overflow:hidden; }
.seg-pick button { flex:1; height:38px; font-size:13.5px; font-weight:500; color:var(--ink-600); background:var(--paper); border:none; cursor:pointer; transition:all .12s; }
.seg-pick button:hover { background:var(--ink-50); }
.seg-pick button.on { background:var(--brand-600); color:#fff; }
.swatches { display:flex; gap:8px; flex-wrap:wrap; }
.swatch { width:30px; height:30px; border-radius:8px; cursor:pointer; border:2px solid transparent; transition:transform .12s; }
.swatch:hover { transform:scale(1.12); }
.swatch.on { border-color:var(--ink-900); box-shadow:0 0 0 2px #fff inset; }
.modal-f { display:flex; align-items:center; justify-content:flex-end; gap:10px; padding:0 24px 22px; }

/* toast */
.toast { position:fixed; bottom:26px; left:50%; transform:translateX(-50%) translateY(20px); background:var(--ink-900); color:#fff; padding:12px 20px; border-radius:var(--r-md); font-size:13.5px; font-weight:500; box-shadow:var(--sh-lg); opacity:0; pointer-events:none; transition:all .25s ease; display:flex; align-items:center; gap:9px; z-index:90; }
.toast.show { opacity:1; transform:translateX(-50%) translateY(0); }
.toast svg { width:16px; height:16px; }
</style>
