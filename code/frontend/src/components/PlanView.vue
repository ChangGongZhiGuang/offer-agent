<script setup>
const props = defineProps({
  session: { type: Object, required: true }, // { role, topic, num_questions, profile }
});
const emit = defineEmits(['start-interview']);

// Derive plan questions from session info
const role = props.session.role || '后端';
const topic = props.session.topic || 'redis';
const numQ = props.session.num_questions || 5;

const qcards = [
  {
    n: 1, flag: false, probe: false,
    dim: `${topic} 基础`,
    diff: '难度 · 中', diffCls: 'diff-mid',
    badge: { text: '热身 · 建基线', cls: 'badge-green' },
    src: `来源 简历重点项目 ∩ JD R1（必须·精通）`,
    followup: [
      { k: '答得好', v: `→ 加深一层：${topic} 底层原理与边界场景` },
      { k: '答得卡', v: `→ 给提示：从基础概念入手` },
    ],
  },
  {
    n: 2, flag: true, probe: false,
    dim: `${topic} 深挖 · 真实性验证`,
    diff: '难度 · 中高', diffCls: 'diff-midhi',
    badge: { text: 'Overclaim 验证', cls: 'badge-red', icon: true },
    src: `来源 简历自述"精通 ${topic}" → VERIFY 门重点关注是否属实`,
    followup: [
      { k: '答得好', v: `→ 持久化机制、主从复制延迟来源` },
      { k: '含糊', v: `→ 要求举具体例子，验证"精通"边界（红旗信号）` },
    ],
  },
  {
    n: 3, flag: false, probe: false,
    dim: '高并发 · 秒杀场景',
    diff: '难度 · 高', diffCls: 'diff-hi',
    badge: { text: '梯度爬升', cls: 'badge-violet' },
    src: '来源 JD R2（必须·精通）∩ 简历秒杀项目',
    followup: [
      { k: '答得好', v: '→ "那高并发下这个方案的瓶颈在哪？"' },
      { k: '答得卡', v: '→ 换角度："先想想读写比例？"' },
    ],
  },
  {
    n: 4, flag: false, probe: true,
    dim: '分布式一致性 · 探底',
    diff: '难度 · 中', diffCls: 'diff-mid',
    badge: { text: '缺口探底', cls: 'badge-amber' },
    src: '来源 能力缺口：JD R3 重要项，简历未直接覆盖 → 出基础题探深浅',
    followup: [
      { k: '答得好', v: '→ 加深至 CAP 取舍与实际选型' },
      { k: '答得卡', v: '→ 不强追，记入弱项，换下一题' },
    ],
  },
  {
    n: 5, flag: false, probe: false,
    dim: 'MySQL 索引与优化',
    diff: '难度 · 中', diffCls: 'diff-mid',
    badge: { text: '交叉考点', cls: 'badge-green' },
    src: '来源 JD R4 ∩ 简历「慢查询治理」项目',
    followup: null,
  },
].slice(0, numQ);
</script>

<template>
  <main class="shell page">
    <!-- breadcrumb -->
    <div class="crumb">
      <a>岗位广场</a><span>/</span>
      <a>投递准备</a><span>/</span>
      <span class="c-now">面试规划</span>
    </div>

    <div class="head-row">
      <div>
        <h1 class="ptitle">规划本场面试结构</h1>
        <p class="psub">PLAN 相位：识别岗位类型 → 懒加载 {{ role }}-interview Skill，结合 JD + 画像产出本场计划——考几道、每道考什么维度、难度怎么走。</p>
      </div>
      <span class="badge badge-violet" style="height:30px;padding:0 14px;">
        <svg viewBox="0 0 24 24" fill="none" width="13" height="13">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>
          <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        计划已产出 · {{ qcards.length }} 题
      </span>
    </div>

    <!-- stepper -->
    <div class="stepwrap">
      <div class="stepper">
        <div class="step">
          <span class="step-num done">
            <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span class="step-label done">投递准备</span>
        </div>
        <div class="step-line done"></div>
        <div class="step"><span class="step-num now">1</span><span class="step-label now">面试规划</span></div>
        <div class="step-line"></div>
        <div class="step"><span class="step-num todo">2</span><span class="step-label todo">多轮面试</span></div>
        <div class="step-line"></div>
        <div class="step"><span class="step-num todo">3</span><span class="step-label todo">评分报告</span></div>
      </div>
    </div>

    <!-- skill loaded banner -->
    <div class="skillbar">
      <span class="sk-ic">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M4 5a2 2 0 012-2h9l5 5v11a2 2 0 01-2 2H6a2 2 0 01-2-2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
          <path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
      <div class="grow">
        <div class="row" style="gap:10px;">
          <span class="sk-name">skills/{{ role }}-interview/SKILL.md</span>
          <span class="badge badge-green">已懒加载</span>
          <span class="badge badge-ink mono">pinned · 段位[1]</span>
        </div>
        <div class="sk-desc">岗位 JD 涉及 {{ topic }}、并发、分布式 → registry 据 description 匹配并注入。本场会话内稳定，享受缓存前缀命中、不参与压缩。</div>
      </div>
    </div>

    <!-- layout: plan + sidebar -->
    <div class="plan-layout">
      <!-- plan timeline -->
      <section>
        <div class="plan-head">
          <h2>本场出题计划</h2>
          <span class="badge badge-ink mono">Plan{ intent, tool_calls[], expected_outcome }</span>
        </div>

        <div
          v-for="q in qcards"
          :key="q.n"
          class="qcard"
          :class="{ flag: q.flag, probe: q.probe }"
        >
          <div class="qn">{{ q.n }}</div>
          <div class="q-body">
            <div class="q-top">
              <span class="q-dim">{{ q.dim }}</span>
              <span class="diff" :class="q.diffCls">{{ q.diff }}</span>
              <span class="badge" :class="q.badge.cls">
                <svg v-if="q.badge.icon" viewBox="0 0 24 24" fill="none" width="11" height="11">
                  <path d="M12 3l9 16H3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
                </svg>
                {{ q.badge.text }}
              </span>
            </div>
            <div class="q-src">来源 <b>{{ q.src }}</b></div>
            <div v-if="q.followup" class="q-followup">
              <div class="fl-h">追问树（来自 Skill）</div>
              <div v-for="fl in q.followup" :key="fl.k" class="fl-row">
                <span class="fl-k">{{ fl.k }}</span>{{ fl.v }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- sidebar -->
      <aside class="plan-side">
        <!-- difficulty gradient -->
        <div class="scard">
          <h4>难度梯度 <span class="tag-mono">expected</span></h4>
          <div class="grad">
            <div class="gbar" style="height:46%;background:linear-gradient(180deg,#7DD3FC,#38BDF8);"><span>Q1</span></div>
            <div class="gbar" style="height:66%;background:linear-gradient(180deg,#C4B5FD,#A78BFA);"><span>Q2</span></div>
            <div v-if="qcards.length > 2" class="gbar" style="height:92%;background:linear-gradient(180deg,#FDBA74,#FB923C);"><span>Q3</span></div>
            <div v-if="qcards.length > 3" class="gbar" style="height:46%;background:linear-gradient(180deg,#7DD3FC,#38BDF8);"><span>Q4</span></div>
            <div v-if="qcards.length > 4" class="gbar" style="height:46%;background:linear-gradient(180deg,#7DD3FC,#38BDF8);"><span>Q5</span></div>
          </div>
          <p style="font-size:12px;color:var(--ink-500);margin-top:26px;line-height:1.5;">先热身建立基线，逐步爬升至高难度，缺口维度回落到基础题探底——答得好再加难度。</p>
        </div>

        <!-- coverage -->
        <div class="scard">
          <h4>维度覆盖</h4>
          <div class="cov">
            <div class="cov-row">
              <div class="cv-top"><span class="cv-name">{{ topic }}</span><span class="mono dim">2 题</span></div>
              <div class="cv-track"><div class="cv-fill" style="width:100%;background:var(--brand-500);"></div></div>
            </div>
            <div class="cov-row">
              <div class="cv-top"><span class="cv-name">高并发</span><span class="mono dim">1 题</span></div>
              <div class="cv-track"><div class="cv-fill" style="width:60%;background:var(--ember-500);"></div></div>
            </div>
            <div class="cov-row">
              <div class="cv-top"><span class="cv-name">分布式</span><span class="mono dim">1 题 · 探底</span></div>
              <div class="cv-track"><div class="cv-fill" style="width:45%;background:var(--amber-500);"></div></div>
            </div>
            <div class="cov-row">
              <div class="cv-top"><span class="cv-name">MySQL</span><span class="mono dim">1 题</span></div>
              <div class="cv-track"><div class="cv-fill" style="width:55%;background:var(--sky-600);"></div></div>
            </div>
          </div>
        </div>

        <!-- constraints -->
        <div class="scard">
          <h4>有界性约束 <span class="tag-mono">procedural</span></h4>
          <div class="cons">
            <div class="cons-row"><span class="ck">max_turns</span><span class="cval">{{ numQ * 4 }}</span></div>
            <div class="cons-row"><span class="ck">计划题数</span><span class="cval">{{ numQ - 1 }} + 1 机动</span></div>
            <div class="cons-row"><span class="ck">max_replans</span><span class="cval">3 / 轮</span></div>
            <div class="cons-row"><span class="ck">不重复出题</span><span class="cval" style="color:var(--green-600);">VERIFY 门</span></div>
          </div>
        </div>
      </aside>
    </div>

    <!-- CTA -->
    <div class="cta-bar">
      <div>
        <div style="font-size:15px;font-weight:700;color:var(--ink-900);">计划通过 VERIFY 门校验 · 引用工具合法、未超剩余题数</div>
        <div style="font-size:13px;color:var(--ink-500);margin-top:3px;">进入 EXECUTE：委派 Examiner 子 agent 出第一道题</div>
      </div>
      <button class="btn btn-ember btn-lg" @click="emit('start-interview')">
        开始模拟面试
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>
  </main>
</template>
