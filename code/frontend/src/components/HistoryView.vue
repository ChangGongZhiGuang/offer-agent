<!-- frontend/src/components/HistoryView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue';
import { listHistory, getHistoryDetail, deleteHistory } from '../api.js';
import TracePanel from './TracePanel.vue';

const items = ref([]);
const loading = ref(true);
const error = ref('');
const deleting = ref('');   // 正在删除的 session_id
const traceOpen = ref(false); // trace 弹层开关

// 选中的单场报告
const selected = ref(null);   // { session_id, role, topic, created_at, report }
const detailLoading = ref(false);

async function loadList() {
  loading.value = true;
  error.value = '';
  try {
    items.value = await listHistory();
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

async function openDetail(item) {
  detailLoading.value = true;
  error.value = '';
  try {
    selected.value = await getHistoryDetail(item.session_id);
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    detailLoading.value = false;
  }
}

function closeDetail() { selected.value = null; }

async function removeItem(it) {
  if (!window.confirm(`确定删除这场面试记录吗？(${it.role} · ${it.topic})`)) return;
  deleting.value = it.session_id;
  error.value = '';
  try {
    await deleteHistory(it.session_id);
    items.value = items.value.filter(x => x.session_id !== it.session_id);
    if (selected.value && selected.value.session_id === it.session_id) closeDetail();
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    deleting.value = '';
  }
}

// ── 报告展示派生 (与 ReportView 同源字段, 精简版) ──
const scoreInt = computed(() => {
  const r = selected.value?.report;
  if (!r) return 0;
  const raw = r.overall_score ?? r.avg_score ?? 0;
  // 分数既可能是 0-5 也可能是 0-100, 归一到 100
  return raw <= 5 ? Math.round(raw * 20) : Math.round(raw);
});
const dims = computed(() => selected.value?.report?.dimensions || []);
const perQuestion = computed(() => selected.value?.report?.per_question || []);
const suggestions = computed(() => selected.value?.report?.suggestions || []);
const summary = computed(() => selected.value?.report?.summary || '');
// 逐题问答 (新历史才有; 旧记录为空则不展示)
const qaList = computed(() => selected.value?.report?.qa || []);

function fmtDate(s) {
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 16);
}
function scoreIntOf(it) {
  const raw = it.overall_score ?? it.avg_score ?? 0;
  return raw <= 5 ? Math.round(raw * 20) : Math.round(raw);
}
function scoreTone(s) {
  const v = s <= 5 ? s : s / 20;
  if (v >= 4) return 'good';
  if (v >= 3) return 'ok';
  if (v >= 2) return 'warn';
  return 'bad';
}

onMounted(loadList);
</script>

<template>
  <main class="shell page">
    <div class="crumb">
      <span class="c-now">我的面试历史</span>
    </div>

    <div class="hist-head">
      <h2>面试历史记录</h2>
      <button class="btn btn-ghost btn-sm" :disabled="loading" @click="loadList">刷新</button>
    </div>

    <div v-if="error" class="hist-error">{{ error }}</div>

    <div class="hist-layout">
      <!-- 列表 -->
      <section class="hist-list">
        <div v-if="loading" class="hist-empty">加载中…</div>
        <div v-else-if="!items.length" class="hist-empty">
          还没有记录。登录状态下完成一场面试后, 这里就会出现记录。
        </div>
        <div
          v-for="it in items"
          :key="it.session_id"
          :class="['hist-item', selected && selected.session_id === it.session_id ? 'active' : '']"
          @click="openDetail(it)"
        >
          <div class="hi-top">
            <span class="hi-role">{{ it.role }}</span>
            <span :class="['hi-score', scoreTone(it.overall_score)]">{{ scoreIntOf(it) }}</span>
          </div>
          <div class="hi-topic">{{ it.topic }}</div>
          <div class="hi-meta">{{ it.answered }} 题 · 平均 {{ (it.avg_score || 0).toFixed(2) }} · {{ fmtDate(it.created_at) }}</div>
          <button
            class="btn btn-ghost btn-sm hi-del"
            :disabled="deleting === it.session_id"
            @click.stop="removeItem(it)"
          >{{ deleting === it.session_id ? '删除中…' : '删除' }}</button>
        </div>
      </section>

      <!-- 详情 -->
      <section class="hist-detail">
        <div v-if="detailLoading" class="hist-empty">报告加载中…</div>
        <div v-else-if="!selected" class="hist-detail-placeholder">
          <svg viewBox="0 0 24 24" fill="none" width="34" height="34"><path d="M4 5h16v14H4z" stroke="#94A3B8" stroke-width="1.6"/><path d="M8 10h8M8 14h5" stroke="#94A3B8" stroke-width="1.6" stroke-linecap="round"/></svg>
          <p>从左侧选择一场面试, 查看完整评分报告。</p>
        </div>
        <div v-else class="report-card">
          <div class="rc-head">
            <div>
              <h3>{{ selected.role }} · 评分报告</h3>
              <p class="rc-sub">{{ selected.topic }} · {{ fmtDate(selected.created_at) }}</p>
            </div>
            <div class="rc-score">
              <span class="rcs-num">{{ scoreInt }}</span>
              <span class="rcs-tot">/ 100</span>
            </div>
            <button class="btn btn-ghost btn-sm rc-close" @click="closeDetail">收起</button>
            <button class="btn btn-ghost btn-sm rc-trace" :disabled="!selected?.session_id" @click="traceOpen = true">重放 trace</button>
          </div>

          <div class="rc-stats">
            {{ selected.report.answered }} 题 · 平均 {{ (selected.report.avg_score || 0).toFixed(2) }} / 5
          </div>

          <!-- 维度得分 -->
          <div v-if="dims.length" class="rc-block">
            <h4>维度得分</h4>
            <div v-for="(d, i) in dims" :key="i" class="dim-row">
              <span class="dim-name">{{ d.name }}</span>
              <div class="dim-track"><div class="dim-fill" :style="{ width: Math.round((d.score || 0) / 5 * 100) + '%' }"></div></div>
              <span class="dim-val">{{ (d.score || 0).toFixed(1) }}</span>
            </div>
          </div>

          <!-- 逐题 -->
          <div v-if="perQuestion.length" class="rc-block">
            <h4>逐题表现</h4>
            <div v-for="(q, i) in perQuestion" :key="i" class="pq-row">
              <span class="pq-n">{{ i + 1 }}</span>
              <div class="pq-main">
                <div class="pq-dim">{{ q.dimension || q.question_id || `第 ${i + 1} 题` }}</div>
                <div v-if="q.notes" class="pq-note">{{ q.notes }}</div>
              </div>
              <span :class="['pq-sc', scoreTone(q.score)]">{{ typeof q.score === 'number' ? q.score.toFixed(1) : '-' }}</span>
            </div>
          </div>

          <!-- 逐题问答原文 -->
          <div v-if="qaList.length" class="rc-block">
            <h4>逐题问答</h4>
            <div v-for="(qa, i) in qaList" :key="i" class="qa-row">
              <div class="qa-head">
                <span class="qa-n">{{ i + 1 }}</span>
                <span class="qa-dim">{{ qa.dimension || qa.question_id || `第 ${i + 1} 题` }}</span>
                <span :class="['qa-sc', scoreTone(qa.score)]">{{ typeof qa.score === 'number' ? qa.score.toFixed(1) : '-' }}</span>
              </div>
              <div class="qa-q">{{ qa.question }}</div>
              <div class="qa-a"><span class="qa-a-tag">你的回答</span>{{ qa.answer }}</div>
              <div v-if="qa.feedback" class="qa-fb">{{ qa.feedback }}</div>
            </div>
          </div>

          <!-- 总评 + 建议 -->
          <div v-if="summary || suggestions.length" class="rc-block">
            <h4>总评与建议</h4>
            <p v-if="summary" class="rc-summary">{{ summary }}</p>
            <ul v-if="suggestions.length" class="rc-sug">
              <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
            </ul>
          </div>
        </div>
      </section>
    </div>

    <TracePanel :session-id="selected?.session_id || ''" :visible="traceOpen" @close="traceOpen = false" />
  </main>
</template>

<style scoped>
.hist-head { display: flex; align-items: center; gap: 12px; margin: 6px 0 18px; }
.hist-head h2 { font-size: 20px; margin: 0; }
.hist-error { padding: 10px 14px; margin-bottom: 14px; border-radius: 10px; background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C); font-size: 13px; }
.hist-layout { display: grid; grid-template-columns: 340px 1fr; gap: 22px; align-items: start; }
.hist-list { display: flex; flex-direction: column; gap: 10px; }
.hist-empty { padding: 28px 16px; text-align: center; color: var(--ink-500); font-size: 13px; background: var(--ink-50, #F8FAFC); border-radius: 12px; border: 1px dashed var(--ink-200); }
.hist-item { text-align: left; padding: 14px 16px; border-radius: 12px; border: 1px solid var(--ink-200); background: #fff; cursor: pointer; transition: all .15s; position: relative; }
.hist-item:hover { border-color: var(--brand-300, #A5B4FC); }
.hist-item.active { border-color: var(--brand-500); box-shadow: 0 0 0 3px var(--brand-50, #EEF2FF); }
.hi-top { display: flex; justify-content: space-between; align-items: center; }
.hi-role { font-weight: 700; color: var(--ink-800, #1E293B); }
.hi-score { font-family: var(--mono, monospace); font-weight: 700; font-size: 15px; }
.hi-score.good { color: var(--green-600); } .hi-score.ok { color: var(--brand-600); }
.hi-score.warn { color: var(--amber-600); } .hi-score.bad { color: var(--red-600); }
.hi-topic { margin: 4px 0; color: var(--ink-600); font-size: 13px; }
.hi-meta { color: var(--ink-400); font-size: 12px; }
.hi-del { position: absolute; right: 12px; bottom: 10px; padding: 2px 10px; font-size: 12px; line-height: 1.6; color: var(--red-600, #DC2626); border-color: var(--ink-200); opacity: 0; transition: opacity .15s; }
.hist-item:hover .hi-del { opacity: 1; }
.hi-del:hover { background: var(--red-50, #FEF2F2); border-color: var(--red-600, #DC2626); }
.pq-sc.good { color: var(--green-600); } .pq-sc.ok { color: var(--brand-600); }
.pq-sc.warn { color: var(--amber-600); } .pq-sc.bad { color: var(--red-600); }
.qa-row { padding: 12px 0; border-top: 1px solid var(--ink-100, #F1F5F9); }
.qa-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.qa-n { width: 20px; height: 20px; border-radius: 6px; background: var(--ink-100, #F1F5F9); color: var(--ink-600); font-size: 11px; display: flex; align-items: center; justify-content: center; flex: none; }
.qa-dim { font-size: 12px; color: var(--ink-500); }
.qa-sc { margin-left: auto; font-weight: 700; font-family: var(--mono, monospace); font-size: 13px; }
.qa-sc.good { color: var(--green-600); } .qa-sc.ok { color: var(--brand-600); }
.qa-sc.warn { color: var(--amber-600); } .qa-sc.bad { color: var(--red-600); }
.qa-q { font-size: 13px; color: var(--ink-800, #1E293B); font-weight: 600; line-height: 1.5; }
.qa-a { margin-top: 6px; font-size: 13px; color: var(--ink-600); line-height: 1.6; background: var(--ink-50, #F8FAFC); border-left: 3px solid var(--brand-300, #A5B4FC); border-radius: 0 8px 8px 0; padding: 8px 10px; white-space: pre-wrap; }
.qa-a-tag { display: inline-block; margin-right: 8px; font-size: 11px; color: var(--brand-600); font-weight: 700; }
.qa-fb { margin-top: 6px; font-size: 12px; color: var(--ink-500); line-height: 1.6; }
.hist-detail { min-height: 200px; }
.hist-detail-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; height: 100%; min-height: 260px; color: var(--ink-400); background: var(--ink-50, #F8FAFC); border-radius: 14px; border: 1px dashed var(--ink-200); }
.report-card { background: #fff; border: 1px solid var(--ink-200); border-radius: 14px; padding: 20px 22px; }
.rc-head { display: flex; align-items: flex-start; gap: 14px; }
.rc-head h3 { margin: 0; font-size: 17px; }
.rc-sub { margin: 3px 0 0; color: var(--ink-500); font-size: 12px; }
.rc-score { margin-left: auto; text-align: right; }
.rcs-num { font-size: 30px; font-weight: 800; color: var(--brand-600); }
.rcs-tot { font-size: 13px; color: var(--ink-400); margin-left: 2px; }
.rc-close { align-self: center; }
.rc-stats { margin: 12px 0 4px; color: var(--ink-600); font-size: 13px; }
.rc-block { margin-top: 18px; }
.rc-block h4 { font-size: 13px; color: var(--ink-700, #334155); margin: 0 0 10px; }
.dim-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.dim-name { width: 96px; font-size: 13px; color: var(--ink-600); }
.dim-track { flex: 1; height: 8px; background: var(--ink-100, #F1F5F9); border-radius: 5px; overflow: hidden; }
.dim-fill { height: 100%; background: var(--brand-500); border-radius: 5px; }
.dim-val { width: 34px; text-align: right; font-size: 13px; font-family: var(--mono, monospace); }
.pq-row { display: flex; gap: 10px; padding: 10px 0; border-top: 1px solid var(--ink-100, #F1F5F9); }
.pq-n { width: 22px; height: 22px; border-radius: 6px; background: var(--ink-100, #F1F5F9); color: var(--ink-600); font-size: 12px; display: flex; align-items: center; justify-content: center; flex: none; }
.pq-main { flex: 1; }
.pq-dim { font-size: 13px; color: var(--ink-700, #334155); }
.pq-note { font-size: 12px; color: var(--ink-500); margin-top: 3px; }
.pq-sc { font-weight: 700; font-family: var(--mono, monospace); }
.rc-summary { font-size: 13px; color: var(--ink-600); line-height: 1.6; margin: 0 0 8px; }
.rc-sug { margin: 0; padding-left: 18px; }
.rc-sug li { font-size: 13px; color: var(--ink-600); margin-bottom: 4px; }
</style>
