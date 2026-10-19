<script setup>
import { ref, computed, onMounted } from 'vue';
import { startSession, uploadResume, getMyResume, analyzeResumeText, getToken } from '../api.js';

const props = defineProps({
  job: { type: Object, default: null },
});
const emit = defineEmits(['started']);

const role = ref(props.job?.role || '资深后端工程师');
const topic = ref(props.job?.skills?.[0] || 'redis');
const profile = ref('');
const numQuestions = ref(5);
const submitting = ref(false);
const error = ref('');

// 简历上传与解析
const resumeFile = ref(null);
const resumeName = ref('');
const parsedProfile = ref(null);   // 后端返回的结构化画像 CandidateProfile
const parsing = ref(false);
const parseError = ref('');
const resumeNotice = ref('');   // 从「我的简历」自动载入的提示条

// JD 关键技能（传给后端做检索/方法论匹配）
const jdKeywords = computed(() => (props.job?.skills || jobSkills.value));

function onPickFile(e) {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  resumeFile.value = f;
  resumeName.value = f.name;
  parsedProfile.value = null;
  parseError.value = '';
}

async function parseResume() {
  // 有选新文件 → 走文件上传解析; 否则若文本框已有正文 → 从文本按当前 JD 现生成画像
  if (!resumeFile.value && !profile.value.trim()) {
    parseError.value = '请先选择简历文件，或填写/载入简历正文';
    return;
  }
  parsing.value = true;
  parseError.value = '';
  try {
    if (resumeFile.value) {
      const res = await uploadResume(resumeFile.value, role.value.trim(), jdKeywords.value.join(' '));
      parsedProfile.value = res.profile;
      // 把原文回填到文本框，便于用户微调/留档
      if (res.resume_text && !profile.value.trim()) profile.value = res.resume_text;
    } else {
      const res = await analyzeResumeText(profile.value.trim(), role.value.trim(), jdKeywords.value.join(' '));
      parsedProfile.value = res.profile;
    }
  } catch (e) {
    parseError.value = e.message || String(e);
  } finally {
    parsing.value = false;
  }
}

function fmtDate(s) {
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 16);
}

// 登录态下自动回填「我的简历」正文 (仅当文本框为空且未选新文件)
// 结构化画像不缓存, 仍需用户点「解析简历」按当前岗位现生成
onMounted(async () => {
  if (!getToken() || profile.value.trim()) return;
  try {
    const r = await getMyResume();
    if (r.exists && r.text) {
      profile.value = r.text;
      resumeNotice.value = `已从「我的简历」载入正文（${r.filename || '未命名'} · ${fmtDate(r.updated_at)}），点「解析简历」按当前岗位生成结构化画像`;
    }
  } catch (e) {
    /* 静默: 未登录/无存储不影响手动填写 */
  }
});

const jobTitle = computed(() => props.job?.title || '资深后端工程师');
const jobCompany = computed(() => props.job?.company || '云启科技 · 基础架构组 · D轮');
const jobSkills = computed(() => props.job?.skills || ['Redis', '高并发', '分布式', 'MySQL', 'Go']);
const jobSalary = computed(() => props.job?.salary || '');
const jobCity = computed(() => props.job?.city || '');
const jobExp = computed(() => props.job?.exp || '');
const jobMatch = computed(() => props.job?.match || 0);
const jobRequirements = computed(() => props.job?.requirements || []);
// 能力缺口：取后半段 requirements（难度/深度要求）
const abilityGaps = computed(() => {
  const r = jobRequirements.value;
  return r.length >= 3 ? r.slice(2, 4) : r.slice(0, 2);
});
// 画像"待验证"项：取前 3 条 requirement 缩短后展示
const toVerify = computed(() => {
  const r = jobRequirements.value;
  if (!r.length) return ['"精通"的真实边界', '系统设计深度', '实战落地经验'];
  return r.slice(0, 3).map(s => s.length > 16 ? s.slice(0, 16) + '…' : s);
});
// Overclaim 风险来自第一个"必须·精通"技能
const overclaimSkill = computed(() => jdReqs.value[0]?.text || jobSkills.value[0] || '');

// JD requirements derived from job skills
const jdReqs = computed(() => {
  const skills = jobSkills.value;
  return skills.map((s, i) => ({
    key: `R${i + 1}`,
    text: s,
    level: i < 2 ? { text: '必须 · 精通', bg: 'var(--red-100)', color: 'var(--red-700)' }
         : i < 4 ? { text: '重要 · 熟练', bg: 'var(--amber-100)', color: 'var(--amber-600)' }
         : { text: '加分', bg: 'var(--ink-100)', color: 'var(--ink-500)' },
  }));
});

async function start() {
  if (!role.value.trim() || !topic.value.trim()) {
    error.value = '岗位 / 主题不能为空';
    return;
  }
  submitting.value = true;
  error.value = '';
  try {
    const res = await startSession({
      role: role.value.trim(),
      topic: topic.value.trim(),
      profile: profile.value.trim(),
      num_questions: Number(numQuestions.value) || 5,
      jd_keywords: jdKeywords.value,
      profile_struct: parsedProfile.value,
    });
    emit('started', {
      ...res,
      role: role.value.trim(),
      topic: topic.value.trim(),
      profile: profile.value.trim(),
      num_questions: Number(numQuestions.value) || 5,
      profile_struct: parsedProfile.value,
    });
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="shell page">
    <!-- breadcrumb -->
    <div class="crumb">
      <a>岗位广场</a><span>/</span>
      <span>{{ jobTitle }}</span><span>/</span>
      <span class="c-now">投递准备</span>
    </div>

    <div class="head-row">
      <div>
        <h1 class="ptitle">解析 JD × 简历，找出该考什么</h1>
        <p class="psub">Assembler 解析两份文档，提取技能交叉点与能力缺口，构建初始候选人画像 → 写入 semantic memory。</p>
      </div>
      <span class="badge badge-green" style="height:30px;padding:0 14px;">
        <svg viewBox="0 0 24 24" fill="none" width="13" height="13">
          <path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        解析完成 · 1.8s
      </span>
    </div>

    <!-- stepper -->
    <div class="stepwrap">
      <div class="stepper">
        <div class="step"><span class="step-num now">0</span><span class="step-label now">投递准备</span></div>
        <div class="step-line"></div>
        <div class="step"><span class="step-num todo">1</span><span class="step-label todo">面试规划</span></div>
        <div class="step-line"></div>
        <div class="step"><span class="step-num todo">2</span><span class="step-label todo">多轮面试</span></div>
        <div class="step-line"></div>
        <div class="step"><span class="step-num todo">3</span><span class="step-label todo">评分报告</span></div>
      </div>
    </div>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <!-- two panels -->
    <div class="cols">
      <!-- JD Panel -->
      <div class="panel">
        <div class="panel-head">
          <span class="ic" style="background:var(--brand-50);color:var(--brand-600);">
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <path d="M7 3h7l5 5v13H7z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
              <path d="M14 3v5h5M9 13h6M9 17h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </span>
          <div class="grow">
            <h3>岗位 JD · 技能要求</h3>
            <div class="ph-sub">从职位描述中抽取 · {{ jdReqs.length }} 项</div>
          </div>
          <span class="tag-mono">lookup_jd()</span>
        </div>
        <div class="panel-body">
          <!-- JD file display -->
          <div class="src-doc">
            <span class="fic doc">
              <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
                <path d="M7 3h7l5 5v13H7z" stroke="currentColor" stroke-width="1.8"/>
              </svg>
            </span>
            <div class="grow">
              <div class="src-name">{{ jobTitle }}_JD.txt</div>
              <div class="src-meta">
                {{ jobCompany }}
                <template v-if="jobSalary"> · {{ jobSalary }}</template>
                <template v-if="jobCity"> · {{ jobCity }}</template>
                <template v-if="jobExp"> · {{ jobExp }}</template>
              </div>
            </div>
            <span class="badge badge-brand">已选</span>
          </div>
          <!-- 实际招聘要求列表 -->
          <div v-if="jobRequirements.length" class="jd-reqs-list">
            <div v-for="(req, i) in jobRequirements" :key="i" class="jd-req-item">
              <span class="jd-req-dot"></span>{{ req }}
            </div>
          </div>
          <!-- requirements list -->
          <div class="req-list">
            <div v-for="req in jdReqs" :key="req.key" class="req">
              <span class="rk">{{ req.key }}</span>
              <span class="rt">{{ req.text }}</span>
              <span class="level" :style="{ background: req.level.bg, color: req.level.color }">
                {{ req.level.text }}
              </span>
            </div>
          </div>
          <!-- role/topic inputs -->
          <div class="field" style="margin-top:16px;">
            <label>岗位方向</label>
            <input v-model="role" class="forge-input" placeholder="如 后端 / 算法 / 前端" />
          </div>
          <div class="field">
            <label>考察主题</label>
            <input v-model="topic" class="forge-input" placeholder="如 redis / mysql / 高并发" />
          </div>
          <div class="field">
            <label>题目数量</label>
            <input v-model.number="numQuestions" type="number" min="1" max="20" class="forge-input" style="max-width:110px;" />
          </div>
        </div>
      </div>

      <!-- Resume Panel -->
      <div class="panel">
        <div class="panel-head">
          <span class="ic" style="background:var(--ember-50);color:var(--ember-600);">
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <circle cx="12" cy="8" r="3.4" stroke="currentColor" stroke-width="1.8"/>
              <path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </span>
          <div class="grow">
            <h3>候选人简历 · 项目与技术栈</h3>
            <div class="ph-sub">填写简历画像，AI 会据此追问</div>
          </div>
          <span class="tag-mono">parse_resume()</span>
        </div>
        <div class="panel-body">
          <!-- resume file upload -->
          <div class="src-doc">
            <span class="fic pdf">
              <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
                <path d="M7 3h7l5 5v13H7z" stroke="currentColor" stroke-width="1.8"/>
              </svg>
            </span>
            <div class="grow">
              <div class="src-name">{{ resumeName || '上传简历 (PDF / Word / txt)' }}</div>
              <div class="src-meta">{{ resumeName ? '点击「解析简历」抽取结构化画像' : '也可直接用下方正文/已存简历点「解析简历」' }}</div>
            </div>
            <label class="btn btn-ghost" style="cursor:pointer;">
              选择文件
              <input type="file" accept=".pdf,.docx,.txt,.md" style="display:none;" @change="onPickFile" />
            </label>
            <button class="btn btn-primary" :disabled="parsing || (!resumeFile && !profile.trim())" @click="parseResume">
              {{ parsing ? '解析中...' : '解析简历' }}
            </button>
          </div>
          <div v-if="resumeNotice" class="resume-notice">{{ resumeNotice }}</div>
          <div v-if="parseError" class="error-bar" style="margin:10px 0;">{{ parseError }}</div>

          <!-- parsed profile preview -->
          <div v-if="parsedProfile" class="parsed-profile">
            <div class="pp-row" v-if="parsedProfile.skills?.length">
              <span class="pp-label">技能栈</span>
              <span class="pp-chips">
                <span v-for="s in parsedProfile.skills" :key="s" class="chip chip-brand">{{ s }}</span>
              </span>
            </div>
            <div class="pp-row" v-if="parsedProfile.projects?.length">
              <span class="pp-label">项目</span>
              <span class="pp-chips">
                <span v-for="(p, i) in parsedProfile.projects" :key="i" class="chip">{{ p.name }}</span>
              </span>
            </div>
            <div class="pp-row pp-row-col" v-if="parsedProfile.weak_spots?.length">
              <span class="pp-label">待深挖</span>
              <ul class="pp-list pp-list-amber">
                <li v-for="(w, i) in parsedProfile.weak_spots" :key="i">{{ w }}</li>
              </ul>
            </div>
            <div class="pp-row pp-row-col" v-if="parsedProfile.topic_plan?.length">
              <span class="pp-label">建议主题</span>
              <ul class="pp-list pp-list-green">
                <li v-for="(t, i) in parsedProfile.topic_plan" :key="i">{{ t }}</li>
              </ul>
            </div>
          </div>

          <!-- profile textarea (原文留档 / 可微调) -->
          <div class="field">
            <label>简历画像（项目 + 技术栈 + 薄弱点）</label>
            <textarea
              v-model="profile"
              rows="8"
              class="forge-input"
              placeholder="例：3 年 Java 后端，秒杀系统缓存层（Redis 集群），自述精通 Redis；订单服务微服务拆分（Kafka）；MySQL 慢查询治理（P99 降 60%）。分布式系统设计较弱，未接触 CAP。"
            ></textarea>
          </div>
          <div class="setup-tip">
            <svg viewBox="0 0 24 24" fill="none" width="14" height="14" style="flex:none;margin-top:2px;">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
              <path d="M12 8v4M12 15v1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            AI 会比对 JD 要求与你的画像，生成针对性追问——含"精通"等声明会被重点验证。
          </div>
        </div>
      </div>
    </div>

    <!-- analysis conclusion -->
    <div class="concl-head">
      <h2>解析结论 · 该考什么</h2>
      <span class="badge badge-ink mono">JD ∩ 简历 → 考点</span>
    </div>
    <div class="col-3">
      <div class="ccard cc-green">
        <div class="cc-top"><span class="cc-n">{{ Math.min(jdReqs.length, 4) }}</span><span class="cc-t">交叉考点</span></div>
        <ul>
          <li v-for="req in jdReqs.slice(0, 4)" :key="req.key">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="var(--green-600)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {{ req.text }} — JD 重点项
          </li>
        </ul>
      </div>
      <div class="ccard cc-amber">
        <div class="cc-top">
          <span class="cc-n">{{ abilityGaps.length }}</span>
          <span class="cc-t">待深入考察</span>
        </div>
        <ul>
          <li v-for="(gap, i) in abilityGaps" :key="i">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 8v5M12 16.5v.5" stroke="var(--amber-600)" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="var(--amber-600)" stroke-width="1.8"/></svg>
            {{ gap }}
          </li>
        </ul>
        <div style="margin-top:12px;font-size:12px;color:var(--amber-600);">→ 规划时安排基础题探底</div>
      </div>
      <div class="ccard cc-red">
        <div class="cc-top"><span class="cc-n">1</span><span class="cc-t">Overclaim 风险</span></div>
        <ul>
          <li>
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 3l9 16H3z" stroke="var(--red-600)" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 9v4M12 16v.5" stroke="var(--red-600)" stroke-width="2" stroke-linecap="round"/></svg>
            简历自述「<b>{{ overclaimSkill }}</b>」——需安排深挖题验证是否属实
          </li>
        </ul>
        <div style="margin-top:12px;font-size:12px;color:var(--red-700);">→ 标记红旗，VERIFY 门重点关注</div>
      </div>
    </div>

    <!-- memory writeback card -->
    <div class="memcard">
      <span class="mc-tag">
        <svg viewBox="0 0 24 24" fill="none" width="13" height="13"><path d="M12 3v18M5 8l7-5 7 5M5 16l7 5 7-5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
        写入 semantic memory · 候选人画像
      </span>
      <h3>候选人初始画像 · {{ role }}</h3>
      <div class="mc-grid">
        <div class="mc-col">
          <div class="mc-h">声称的强项</div>
          <div class="mc-item"><span class="md" style="background:#34D399;"></span>{{ topic }}（核心考点）</div>
          <div v-for="s in jobSkills.slice(1, 3)" :key="s" class="mc-item">
            <span class="md" style="background:#34D399;"></span>{{ s }}
          </div>
        </div>
        <div class="mc-col">
          <div class="mc-h">待验证 / 不确定</div>
          <div v-for="(item, i) in toVerify" :key="i" class="mc-item">
            <span class="md" style="background:var(--amber-500);"></span>{{ item }}
          </div>
        </div>
        <div class="mc-col">
          <div class="mc-h">画像元数据</div>
          <div class="mc-item"><span class="md" style="background:var(--brand-300);"></span>目标岗位：{{ jobTitle }}</div>
          <div class="mc-item"><span class="md" style="background:var(--brand-300);"></span>题数：{{ numQuestions }} 题</div>
          <div class="mc-item"><span class="md" style="background:var(--brand-300);"></span>难度基线：中 → 中高</div>
        </div>
      </div>
    </div>

    <!-- CTA -->
    <div class="cta-bar">
      <div>
        <div style="font-size:15px;font-weight:700;color:var(--ink-900);">画像就绪，可以规划面试了</div>
        <div style="font-size:13px;color:var(--ink-500);margin-top:3px;">
          下一步：AI 将规划 {{ numQuestions }} 道题，逐一追问并评分
        </div>
      </div>
      <button class="btn btn-primary btn-lg" :disabled="submitting" @click="start">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        {{ submitting ? '正在创建...' : '进入面试规划' }}
      </button>
    </div>
  </main>
</template>

<style scoped>
/* 从「我的简历」自动载入的提示条 */
.resume-notice {
  margin: 10px 0;
  padding: 9px 12px;
  border-radius: 9px;
  font-size: 12.5px;
  line-height: 1.5;
  background: var(--brand-50, #EEF2FF);
  color: var(--brand-700, #4338CA);
  border: 1px solid var(--brand-100, #E0E7FF);
}
/* 岗位实际招聘要求列表 */
.jd-reqs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 12px 0 4px;
  padding: 12px 14px;
  background: var(--ink-50, #f9fafb);
  border-radius: var(--r-sm, 8px);
  border: 1px solid var(--ink-100, #f3f4f6);
}
.jd-req-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--ink-600, #4b5563);
}
.jd-req-dot {
  flex: none;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brand-400, #818cf8);
  margin-top: 5px;
}
.parsed-profile {
  margin: 14px 0 4px;
  padding: 14px 16px;
  border: 1px solid var(--brand-100, #e0e7ff);
  border-radius: 12px;
  background: var(--brand-50, #f5f7ff);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pp-row { display: flex; align-items: flex-start; gap: 10px; }
/* 长文本行（待深挖/建议主题）竖排，标签单独一行 */
.pp-row-col { flex-direction: column; gap: 6px; }
.pp-label {
  flex: none;
  width: 64px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-500, #6b7280);
  padding-top: 3px;
}
.pp-row-col .pp-label { width: auto; padding-top: 0; }
.pp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip-brand { background: var(--brand-100, #e0e7ff); color: var(--brand-700, #4338ca); }
.chip-amber { background: var(--amber-100, #fef3c7); color: var(--amber-600, #d97706); }
.chip-green { background: var(--green-50, #ecfdf5); color: var(--green-700, #047857); }
/* 待深挖 / 建议主题 列表 — 允许自然换行，行距清晰 */
.pp-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 5px;
  max-height: 180px;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--ink-200, #e5e7eb) transparent;
}
.pp-list::-webkit-scrollbar { width: 4px; }
.pp-list::-webkit-scrollbar-track { background: transparent; }
.pp-list::-webkit-scrollbar-thumb { background: var(--ink-200, #e5e7eb); border-radius: 4px; }
.pp-list li {
  position: relative;
  padding-left: 14px;
  font-size: 12.5px;
  line-height: 1.6;
  word-break: break-word;
  white-space: normal;
}
.pp-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
}
.pp-list-amber li { color: var(--amber-700, #b45309); }
.pp-list-amber li::before { background: var(--amber-400, #fbbf24); }
.pp-list-green li { color: var(--green-700, #047857); }
.pp-list-green li::before { background: var(--green-500, #10b981); }
</style>
