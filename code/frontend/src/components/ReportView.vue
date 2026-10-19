<script setup>
import { computed, ref } from 'vue';
import TracePanel from './TracePanel.vue';

const props = defineProps({
  report: { type: Object, required: true },
  sessionId: { type: String, default: '' },
});
const emit = defineEmits(['restart']);

const traceOpen = ref(false);

// Score ring math: avg_score 0-5 → 0-100, circumference = 2π×60 = 376.99
const circumference = 376.99;
const scoreInt = computed(() => Math.round((props.report.avg_score || 0) * 20));
const dashoffset = computed(() => circumference * (1 - scoreInt.value / 100));

// Match % derived from score
const matchPct = computed(() => Math.max(30, scoreInt.value - 2));

// 逐题数据：新后端用 per_question，兼容旧的 details 字段
const details = computed(() => props.report.per_question || props.report.details || []);

// LLM 总评与改进建议（新字段）
const summary = computed(() => props.report.summary || '');
const suggestions = computed(() => props.report.suggestions || []);
const weaknessTags = computed(() => props.report.weakness_tags || []);

// 维度得分：直接用后端按维度聚合的 dimensions:[{name,score}]
const dimBars = computed(() => {
  const dims = props.report.dimensions || [];
  return dims.map((d) => ({
    label: d.name,
    score: d.score,
    pct: Math.round(((d.score || 0) / 5) * 100),
  }));
});

// Radar polygon: 5 axes, pentagon, center (140,140), r=110
const radarAngles = [-90, -18, 54, 126, 198]; // degrees
const outerPts = radarAngles.map(a => {
  const r = a * Math.PI / 180;
  return { x: 140 + 110 * Math.cos(r), y: 140 + 110 * Math.sin(r) };
});
const radarData = computed(() => {
  const bars = dimBars.value;
  return outerPts.map((pt, i) => {
    const score = bars[i]?.score ?? (props.report.avg_score || 0);
    const ratio = score / 5;
    const a = radarAngles[i] * Math.PI / 180;
    return { x: 140 + 110 * ratio * Math.cos(a), y: 140 + 110 * ratio * Math.sin(a) };
  });
});
const radarPolygon = computed(() =>
  radarData.value.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
);
const radarLabels = computed(() => {
  const bars = dimBars.value;
  const defaults = ['缓存', '并发', '分布式', '数据库', '消息队列'];
  return outerPts.map((pt, i) => ({
    ...pt,
    label: bars[i]?.label ?? defaults[i] ?? `维度${i + 1}`,
  }));
});

// Per-question helpers
function scoreColor(s) {
  if (typeof s !== 'number') return 'var(--ink-400)';
  if (s >= 4) return 'var(--green-600)';
  if (s >= 3) return 'var(--brand-600)';
  if (s >= 2) return 'var(--amber-600)';
  return 'var(--red-600)';
}
function scoreBg(s) {
  if (typeof s !== 'number') return { bg: 'var(--ink-100)', color: 'var(--ink-500)' };
  if (s >= 4) return { bg: 'var(--green-100)', color: 'var(--green-700)' };
  if (s >= 3) return { bg: 'var(--brand-50)', color: 'var(--brand-700)' };
  if (s >= 2) return { bg: 'var(--amber-100)', color: 'var(--amber-600)' };
  return { bg: 'var(--red-100)', color: 'var(--red-700)' };
}
function barColor(s) {
  if (s >= 4) return 'var(--green-600)';
  if (s >= 3) return 'var(--brand-500)';
  if (s >= 2) return 'var(--amber-500)';
  return 'var(--red-500,#F87171)';
}
function scoreLabel(s) {
  return typeof s === 'number' ? s.toFixed(1) : '-';
}

const verdictText = computed(() => {
  const s = scoreInt.value;
  if (s >= 80) return '建议：表现优秀，可直接进入下一轮';
  if (s >= 60) return '建议：基本达标，补强弱点后可进入下一轮';
  return '建议：需系统补强，再次模拟后再投递';
});

// Strengths (q score ≥ 4)
const strengths = computed(() =>
  details.value.filter(d => d.score >= 4)
);
// Weaknesses (q score < 3)
const weaknesses = computed(() =>
  details.value.filter(d => typeof d.score === 'number' && d.score < 3)
);

// Overclaim: look for high score variance
const hasOverclaim = computed(() => {
  const ds = details.value;
  if (ds.length < 2) return false;
  const scores = ds.map(d => d.score || 0);
  const max = Math.max(...scores);
  const min = Math.min(...scores);
  return max - min >= 2;
});
</script>

<template>
  <main class="shell page">
    <!-- breadcrumb -->
    <div class="crumb">
      <a @click.prevent="emit('restart')">多轮面试</a>
      <span>/</span>
      <span class="c-now">结构化评分报告</span>
    </div>

    <!-- stepper (all done) -->
    <div class="stepwrap">
      <div class="stepper">
        <div class="step">
          <span class="step-num done">
            <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span class="step-label done">投递准备</span>
        </div>
        <div class="step-line done"></div>
        <div class="step">
          <span class="step-num done">
            <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span class="step-label done">面试规划</span>
        </div>
        <div class="step-line done"></div>
        <div class="step">
          <span class="step-num done">
            <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span class="step-label done">多轮面试</span>
        </div>
        <div class="step-line done"></div>
        <div class="step">
          <span class="step-num now">3</span>
          <span class="step-label now">评分报告</span>
        </div>
      </div>
    </div>

    <!-- hero score band -->
    <div class="report-hero">
      <div class="hero-grid">
        <!-- score ring -->
        <div class="scorering">
          <svg viewBox="0 0 140 140" width="140" height="140">
            <circle cx="70" cy="70" r="60" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="12"/>
            <circle
              cx="70" cy="70" r="60"
              fill="none"
              stroke="url(#scoreGrad)"
              stroke-width="12"
              stroke-linecap="round"
              :stroke-dasharray="circumference"
              :stroke-dashoffset="dashoffset"
              transform="rotate(-90 70 70)"
            />
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#6366F1"/>
                <stop offset="1" stop-color="#34D399"/>
              </linearGradient>
            </defs>
          </svg>
          <div class="sc-val">
            <span class="sc-num">{{ scoreInt }}</span>
            <span class="sc-tot">/ 100 综合</span>
          </div>
        </div>

        <!-- mid info -->
        <div class="hero-mid">
          <h1>{{ report.role || '模拟面试' }} · 评分报告</h1>
          <div class="candidate">
            {{ report.answered }} 题 · {{ (report.avg_score || 0).toFixed(2) }} / 5 平均分 · {{ report.topic || '' }}
          </div>
          <div class="verdict-pill">
            <svg viewBox="0 0 24 24" fill="none" width="16" height="16">
              <path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            {{ verdictText }}
          </div>
        </div>

        <!-- right: match + actions -->
        <div class="hero-right">
          <div class="hr-stat">
            <div class="hr-n" style="color:#6EE7B7;">{{ matchPct }}%</div>
            <div class="hr-l">与 JD 匹配度</div>
          </div>
          <div class="hero-actions">
            <button class="btn-glass" :disabled="!sessionId" @click="traceOpen = true">
              <svg viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>
              重放 · trace
            </button>
            <button class="btn-glass">导出 PDF</button>
          </div>
        </div>
      </div>
    </div>

    <!-- main layout -->
    <div class="report-layout">
      <!-- left: dimension scores + per-question -->
      <div class="stack" style="gap:22px;">
        <!-- dimension scores panel -->
        <div class="panel">
          <div class="panel-h">
            <h3>维度得分</h3>
            <span class="tag-mono" style="margin-left:auto;">Grader 汇总 · rubric 1–5</span>
          </div>
          <div class="panel-b">
            <div class="dim-grid">
              <!-- radar chart -->
              <svg viewBox="0 0 280 270" width="280">
                <!-- grid pentagons -->
                <polygon points="140,30 244.6,106 204.7,229 75.3,229 35.4,106" fill="none" stroke="#E2E8F0" stroke-width="1"/>
                <polygon points="140,67.4 209,117.6 182.7,198.7 97.3,198.7 71,117.6" fill="none" stroke="#E2E8F0" stroke-width="1"/>
                <polygon points="140,103.7 174.5,128.8 161.3,169.4 118.7,169.4 105.5,128.8" fill="none" stroke="#EEF1F5" stroke-width="1"/>
                <!-- axes -->
                <g stroke="#E2E8F0" stroke-width="1">
                  <line x1="140" y1="140" x2="140" y2="30"/>
                  <line x1="140" y1="140" x2="244.6" y2="106"/>
                  <line x1="140" y1="140" x2="204.7" y2="229"/>
                  <line x1="140" y1="140" x2="75.3" y2="229"/>
                  <line x1="140" y1="140" x2="35.4" y2="106"/>
                </g>
                <!-- data polygon -->
                <polygon :points="radarPolygon" fill="rgba(99,102,241,.18)" stroke="#6366F1" stroke-width="2.2"/>
                <g fill="#6366F1">
                  <circle v-for="(p,i) in radarData" :key="i" :cx="p.x" :cy="p.y" r="3.5"/>
                </g>
                <!-- labels -->
                <g font-family="Manrope,sans-serif" font-size="11.5" font-weight="600" fill="#475569" text-anchor="middle">
                  <text v-for="(l,i) in radarLabels" :key="i" :x="l.x + (l.x < 120 ? -14 : l.x > 160 ? 14 : 0)" :y="l.y + (l.y < 60 ? -8 : l.y > 200 ? 16 : 0)">{{ l.label }}</text>
                </g>
              </svg>

              <!-- dimension bars -->
              <div class="bars">
                <div v-for="(dim, i) in dimBars" :key="i" class="bar-row">
                  <div class="b-top">
                    <span class="b-name">{{ dim.label }}</span>
                    <span class="b-score" :style="{ color: barColor(dim.score) }">{{ dim.score.toFixed(1) }}</span>
                  </div>
                  <div class="b-track">
                    <div class="b-fill" :style="{ width: dim.pct + '%', background: barColor(dim.score) }"></div>
                  </div>
                </div>
                <div v-if="!dimBars.length" class="hint-text">暂无维度数据。</div>
              </div>
            </div>
          </div>
        </div>

        <!-- per-question breakdown -->
        <div class="panel">
          <div class="panel-h">
            <h3>逐题表现</h3>
            <span class="tag-mono" style="margin-left:auto;">episodic memory · 重放</span>
          </div>
          <div class="panel-b" style="padding-top:8px;padding-bottom:8px;">
            <div v-if="!details.length" class="hint-text">没有逐题数据。</div>
            <div v-for="(d, i) in details" :key="i" class="qrow">
              <span class="q-n" :style="{ background: scoreBg(d.score).bg, color: scoreBg(d.score).color }">{{ i + 1 }}</span>
              <div class="q-main">
                <div class="q-dim">{{ d.dimension || d.question_id || `第 ${i + 1} 题` }}</div>
                <div v-if="d.notes" class="q-note">{{ d.notes }}</div>
                <div class="q-tags" style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
                  <span v-if="d.score >= 4" class="badge badge-green">概念清晰</span>
                  <span v-else-if="d.score >= 3" class="badge badge-brand">基本达标</span>
                  <span v-else-if="d.score >= 2" class="badge badge-amber">有待加强</span>
                  <span v-else-if="typeof d.score === 'number'" class="badge badge-red">需要补强</span>
                </div>
              </div>
              <span class="q-sc" :style="{ color: scoreColor(d.score) }">{{ scoreLabel(d.score) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- sidebar -->
      <aside class="stack" style="gap:22px;">
        <!-- Overclaim 验证 -->
        <div class="scard">
          <h4>
            <span class="scard-icon" style="background:#FFFBEB;color:var(--amber-600);">
              <svg viewBox="0 0 24 24" fill="none" width="15" height="15"><path d="M12 3l9 16H3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            </span>
            Overclaim 验证结论
          </h4>
          <div class="report-verdict">
            <div class="rv-title">
              <svg viewBox="0 0 24 24" fill="none" width="16" height="16" style="vertical-align:-3px;margin-right:6px;"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/><path d="M12 8v5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
              {{ hasOverclaim ? '"精通"声明 — 部分属实' : '声明与表现基本一致' }}
            </div>
            <div class="rv-body">
              {{ hasOverclaim
                ? '题目间得分差异明显，说明部分技能点尚未达到所声称水位。建议在简历中如实描述掌握程度，避免面试时被深挖暴露。'
                : '本场表现与简历自述基本匹配，未检测到明显 Overclaim 风险。' }}
            </div>
          </div>
        </div>

        <!-- 核心强项 -->
        <div class="scard">
          <h4>
            <span class="scard-icon" style="background:var(--green-50);color:var(--green-700);">
              <svg viewBox="0 0 24 24" fill="none" width="15" height="15"><path d="M7 11l3-7 1 5h6l-2 8H8z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
            </span>
            核心强项
          </h4>
          <ul class="pt-list" v-if="strengths.length">
            <li v-for="(d, i) in strengths" :key="i">
              <svg viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="var(--green-600)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
              {{ d.question_id || `第 ${i + 1} 题` }} · 得分 {{ d.score }}/5{{ d.notes ? '，' + d.notes.slice(0, 40) : '' }}
            </li>
          </ul>
          <p v-else class="hint-text" style="margin:0;">暂无突出强项（得分 ≥ 4）。</p>
        </div>

        <!-- 待提升 -->
        <div class="scard">
          <h4>
            <span class="scard-icon" style="background:var(--red-50);color:var(--red-700);">
              <svg viewBox="0 0 24 24" fill="none" width="15" height="15"><path d="M12 8v5M12 16v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/></svg>
            </span>
            待提升
          </h4>
          <ul class="pt-list" v-if="weaknesses.length">
            <li v-for="(d, i) in weaknesses" :key="i">
              <svg viewBox="0 0 24 24" fill="none"><path d="M6 12h12" :stroke="d.score < 2 ? 'var(--red-600)' : 'var(--amber-600)'" stroke-width="2.4" stroke-linecap="round"/></svg>
              <span><b :style="{ color: d.score < 2 ? 'var(--red-700)' : 'var(--amber-600)' }">{{ d.question_id || `第 ${i + 1} 题` }}</b> — 得分 {{ d.score }}/5，需重点复习</span>
            </li>
          </ul>
          <p v-else class="hint-text" style="margin:0;">未发现明显短板（得分 < 3）。</p>
        </div>

        <!-- 改进建议 -->
        <div class="scard">
          <h4>
            <span class="scard-icon" style="background:var(--brand-50);color:var(--brand-700);">
              <svg viewBox="0 0 24 24" fill="none" width="15" height="15"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
            </span>
            改进建议
          </h4>
          <p v-if="summary" class="rv-body" style="margin:0 0 12px;">{{ summary }}</p>
          <ul class="imp-list" v-if="suggestions.length">
            <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
          </ul>
          <ul class="imp-list" v-else>
            <li>针对低分题目，找出知识盲区，系统学习后重新挑战同类题。</li>
            <li>关注薄弱标签标记的弱点，结合实际项目加深理解。</li>
            <li>下次模拟聚焦弱项专项，验证补强效果后再投递。</li>
          </ul>
          <div v-if="weaknessTags.length" class="wt-chips">
            <span v-for="t in weaknessTags" :key="t" class="badge badge-amber">{{ t }}</span>
          </div>
        </div>

        <!-- 与JD匹配明细 -->
        <div class="scard">
          <h4>与 JD 匹配明细</h4>
          <div class="match-bd">
            <div v-for="(d, i) in details.slice(0, 5)" :key="i" class="mb-row">
              <div class="mb-top">
                <span class="mb-name">{{ d.dimension || d.question_id || `考察项 ${i + 1}` }}</span>
                <span class="mb-status">{{ d.score >= 4 ? '达标' : d.score >= 3 ? '基本达标' : '未达标' }}</span>
              </div>
              <div class="mb-track">
                <div :style="{ width: Math.round((d.score || 0) / 5 * 100) + '%', height: '100%', background: barColor(d.score), borderRadius: '5px' }"></div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- footer CTA -->
    <footer class="foot between" style="margin-top:30px;">
      <span>本场面试全程落 trace（append-only JSONL）· 可逐轮重放，回看"为什么问了这道题"</span>
      <button class="btn btn-ghost btn-sm" @click="emit('restart')">返回岗位广场</button>
    </footer>

    <TracePanel :session-id="sessionId" :visible="traceOpen" @close="traceOpen = false" />
  </main>
</template>

<style scoped>
.wt-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
</style>
