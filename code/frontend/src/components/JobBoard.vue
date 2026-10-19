<script setup>
import { ref, computed, onMounted } from 'vue';
import { getJobs, createJob, updateJob, deleteJob } from '../api.js';
import { useAuth } from '../composables/useAuth.js';

const emit = defineEmits(['select-job']);

const activeFilter = ref('全部');
const filters = ['全部', '后端', '前端', '算法', '系统设计'];

// 搜索 / 城市 / 薪资 筛选状态（纯前端）
const searchText = ref('');
const selectedCity = ref('全部');
const selectedSalary = ref('不限');

// 薪资档位：label + 下限/上限 (单位 K, 按岗位 salaryMin 匹配)
const salaryBuckets = [
  { label: '不限', min: 0, max: Infinity },
  { label: '20K 以下', min: 0, max: 20 },
  { label: '20-40K', min: 20, max: 40 },
  { label: '40-60K', min: 40, max: 60 },
  { label: '60K 以上', min: 60, max: Infinity },
];

/* ── 旧: 岗位硬编码数组 (已迁到后端 /jobs, 保留作对照) ──
const jobs = [
  // ───────── 后端 ─────────
  {
    id: 1, featured: true, category: '后端',
    logo: '云', logoGrad: 'linear-gradient(145deg,#4F46E5,#312E81)',
    title: '资深后端工程师', company: '云启科技 · 基础架构组 · D轮',
    salary: '30-55K · 16薪', salaryMin: 30, city: '上海', exp: '3-5 年',
    skills: ['Redis', '高并发', '分布式', 'MySQL', 'Go'], match: 92,
    tags: [{ text: '简历高度匹配', cls: 'badge-ember', icon: true }, { text: '急招', cls: 'badge-red' }],
    requirements: [
      '5 年以上后端开发，主导过高并发系统设计',
      '精通 Redis 集群、缓存一致性与分布式锁',
      '深入理解 MySQL 索引/事务/分库分表',
      '有秒杀、订单等高 QPS 场景实战经验',
      '熟悉 Go 或 Java，了解微服务治理',
    ],
  },
  {
    id: 2, category: '后端',
    logo: '数', logoGrad: 'linear-gradient(145deg,#0EA5E9,#0369A1)',
    title: '后端开发工程师', company: '数珩数据 · B轮',
    salary: '25-45K', salaryMin: 25, city: '北京', exp: '3-5 年',
    skills: ['Java', 'Spring', 'Kafka', '微服务'], match: 78,
    requirements: [
      '熟练 Java + Spring Boot/Cloud 微服务开发',
      '掌握 Kafka 消息队列与异步解耦',
      '理解服务注册发现、配置中心、链路追踪',
      '有大数据量 ETL 或数据平台经验加分',
    ],
  },
  {
    id: 3, category: '后端',
    logo: '极', logoGrad: 'linear-gradient(145deg,#F97316,#C2410C)',
    title: '后端工程师 · Go 方向', company: '极光出行 · 上市公司',
    salary: '26-46K', salaryMin: 26, city: '成都', exp: '2-4 年',
    skills: ['Go', 'gRPC', 'PostgreSQL', 'K8s'], match: 81,
    requirements: [
      '熟练 Go，理解 goroutine/channel 并发模型',
      '有 gRPC 微服务与 Protobuf 经验',
      '掌握 PostgreSQL，了解索引与查询优化',
      '熟悉 Kubernetes 容器编排与 CI/CD',
    ],
  },
  {
    id: 7, category: '后端',
    logo: '蜂', logoGrad: 'linear-gradient(145deg,#D97706,#92400E)',
    title: 'Java 高级工程师 · 交易', company: '蜂享科技 · 已上市',
    salary: '35-60K', salaryMin: 35, city: '深圳', exp: '5 年+',
    skills: ['Java', '分布式事务', '高可用', 'RocketMQ'], match: 74,
    requirements: [
      '5 年以上交易/支付系统后端经验',
      '掌握分布式事务（TCC/Saga/本地消息表）',
      '理解幂等、对账、资金安全设计',
      '熟悉 RocketMQ/Kafka 与最终一致性',
    ],
  },
  {
    id: 8, category: '后端',
    logo: '鲸', logoGrad: 'linear-gradient(145deg,#0891B2,#155E75)',
    title: '初级后端工程师 · 校招', company: '鲸跃网络 · A轮',
    salary: '12-18K', salaryMin: 12, city: '杭州', exp: '应届/1 年',
    skills: ['Java', 'MySQL', 'Spring', 'Linux'], match: 70,
    requirements: [
      '计算机相关专业，扎实的数据结构与算法基础',
      '了解 Java 与 Spring 基础，写过完整 CRUD 项目',
      '熟悉 MySQL 基本使用与简单优化',
      '有较强学习能力与工程规范意识',
    ],
  },
  // ───────── 前端 ─────────
  {
    id: 5, category: '前端',
    logo: '织', logoGrad: 'linear-gradient(145deg,#059669,#047857)',
    title: '高级前端工程师', company: '织云 · 远程友好',
    salary: '28-50K', salaryMin: 28, city: '远程', exp: '3-5 年',
    skills: ['React', 'TypeScript', '性能优化'], match: 59,
    requirements: [
      '精通 React + TypeScript，理解 Hooks 与状态管理',
      '有大型 SPA 性能优化经验（首屏/懒加载/缓存）',
      '熟悉构建工具链 Vite/Webpack',
      '关注工程化、组件库与可维护性',
    ],
  },
  {
    id: 9, category: '前端',
    logo: '澜', logoGrad: 'linear-gradient(145deg,#10B981,#065F46)',
    title: 'Vue 前端工程师', company: '澜图科技 · B轮',
    salary: '20-38K', salaryMin: 20, city: '上海', exp: '2-4 年',
    skills: ['Vue 3', 'Pinia', 'Vite', '可视化'], match: 66,
    requirements: [
      '熟练 Vue 3 组合式 API 与 Pinia 状态管理',
      '理解响应式原理与组件通信',
      '有数据可视化（ECharts/D3）经验加分',
      '注重交互细节与还原度',
    ],
  },
  {
    id: 10, category: '前端',
    logo: '匠', logoGrad: 'linear-gradient(145deg,#6366F1,#4338CA)',
    title: '资深前端 · 中后台', company: '匠云 SaaS · C轮',
    salary: '32-55K', salaryMin: 32, city: '北京', exp: '5 年+',
    skills: ['React', '微前端', '低代码', 'Node'], match: 61,
    requirements: [
      '主导过中后台/低代码平台前端架构',
      '理解微前端（qiankun/Module Federation）',
      '有 Node.js BFF 层开发经验',
      '能从 0 搭建组件库与脚手架',
    ],
  },
  {
    id: 11, category: '前端',
    logo: '虹', logoGrad: 'linear-gradient(145deg,#EC4899,#9D174D)',
    title: '前端工程师 · C 端', company: '虹宇互娱 · 已上市',
    salary: '18-32K', salaryMin: 18, city: '广州', exp: '2-4 年',
    skills: ['小程序', 'H5', '性能', '动效'], match: 57,
    requirements: [
      '熟悉微信小程序与 H5 跨端开发',
      '有 C 端高流量页面性能优化经验',
      '掌握 CSS 动效与交互实现',
      '关注首屏与弱网体验',
    ],
  },
  // ───────── 算法 ─────────
  {
    id: 4, category: '算法',
    logo: '玄', logoGrad: 'linear-gradient(145deg,#7C3AED,#5B21B6)',
    title: '算法工程师 · 推荐', company: '玄策 AI · C轮',
    salary: '40-70K', salaryMin: 40, city: '杭州', exp: '硕士优先',
    skills: ['推荐系统', 'PyTorch', '召回排序'], match: 64,
    requirements: [
      '硕士优先，扎实的机器学习理论基础',
      '有推荐系统召回/排序模型落地经验',
      '熟练 PyTorch/TensorFlow',
      '理解特征工程与 A/B 实验',
    ],
  },
  {
    id: 12, category: '算法',
    logo: '深', logoGrad: 'linear-gradient(145deg,#8B5CF6,#5B21B6)',
    title: 'NLP 算法工程师 · 大模型', company: '深澜智能 · D轮',
    salary: '45-80K', salaryMin: 45, city: '北京', exp: '3-5 年',
    skills: ['LLM', 'Transformer', 'RAG', '微调'], match: 52,
    requirements: [
      '熟悉 Transformer 与主流大模型架构',
      '有 LLM 微调/对齐或 RAG 落地经验',
      '掌握 PyTorch 与分布式训练',
      '关注推理优化与效果评测',
    ],
  },
  {
    id: 13, category: '算法',
    logo: '视', logoGrad: 'linear-gradient(145deg,#2563EB,#1E3A8A)',
    title: '计算机视觉工程师', company: '视界科技 · B轮',
    salary: '35-60K', salaryMin: 35, city: '深圳', exp: '3-5 年',
    skills: ['CV', '目标检测', 'CUDA', '部署'], match: 48,
    requirements: [
      '熟悉目标检测/分割主流模型',
      '有模型工程化部署经验（TensorRT/ONNX）',
      '了解 CUDA 与推理加速',
      '有边缘设备落地经验加分',
    ],
  },
  // ───────── 系统设计 ─────────
  {
    id: 6, category: '系统设计',
    logo: '磐', logoGrad: 'linear-gradient(145deg,#334155,#0F172A)',
    title: '系统架构师', company: '磐石云 · 上市公司',
    salary: '50-80K', salaryMin: 50, city: '深圳', exp: '7 年+',
    skills: ['分布式', '高可用', '容量规划'], match: 55,
    requirements: [
      '7 年以上，主导过大型分布式系统架构',
      '精通高可用、容灾、容量规划',
      '深入理解 CAP、一致性协议、限流熔断',
      '有跨团队技术决策与落地经验',
    ],
  },
  {
    id: 14, category: '系统设计',
    logo: '枢', logoGrad: 'linear-gradient(145deg,#475569,#1E293B)',
    title: '中间件研发专家', company: '枢纽科技 · D轮',
    salary: '45-75K', salaryMin: 45, city: '上海', exp: '5 年+',
    skills: ['消息队列', '存储引擎', 'Java', '源码'], match: 50,
    requirements: [
      '有消息队列/存储/RPC 等中间件研发经验',
      '能阅读并改造开源中间件源码',
      '理解高性能网络编程与零拷贝',
      '具备稳定性与性能调优能力',
    ],
  },
  {
    id: 15, category: '系统设计',
    logo: '穹', logoGrad: 'linear-gradient(145deg,#1E40AF,#172554)',
    title: '后端架构师 · 高并发', company: '穹顶出行 · 已上市',
    salary: '40-68K', salaryMin: 40, city: '北京', exp: '6 年+',
    skills: ['高并发', '分布式事务', '缓存', '稳定性'], match: 53,
    requirements: [
      '主导过千万级 DAU 系统的架构演进',
      '精通缓存体系、分布式事务与幂等设计',
      '有大促/秒杀稳定性保障经验',
      '能制定容量、降级、预案策略',
    ],
  },
];
── 旧硬编码数组结束 */

// ── 岗位数据: 现从后端 /jobs 拉取; 装饰元素 (logo/配色) 前端按规则现生成 ──
const jobs = ref([]);
const loading = ref(true);
const loadError = ref('');

const GRAD_BY_CATEGORY = {
  '后端': 'linear-gradient(145deg,#4F46E5,#312E81)',
  '前端': 'linear-gradient(145deg,#059669,#047857)',
  '算法': 'linear-gradient(145deg,#7C3AED,#5B21B6)',
  '系统设计': 'linear-gradient(145deg,#334155,#0F172A)',
};
const FALLBACK_GRADS = [
  'linear-gradient(145deg,#0EA5E9,#0369A1)',
  'linear-gradient(145deg,#F97316,#C2410C)',
  'linear-gradient(145deg,#EC4899,#9D174D)',
];
function hashStr(s) {
  let h = 0;
  for (const ch of String(s || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}
function decorate(j) {
  return {
    ...j,
    logo: (j.company || j.title || '?').trim().charAt(0),
    logoGrad: GRAD_BY_CATEGORY[j.category]
      || FALLBACK_GRADS[hashStr(j.id) % FALLBACK_GRADS.length],
  };
}

async function loadJobs() {
  loading.value = true;
  loadError.value = '';
  try {
    const list = await getJobs();
    jobs.value = list.map(decorate);
  } catch (e) {
    loadError.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

// ── 管理员: 岗位增删改 (仅 admin/root 可见入口) ──
const { isAdmin } = useAuth();
const CATEGORIES = ['后端', '前端', '算法', '系统设计'];
const modalOpen = ref(false);
const editingId = ref('');     // '' 表示新增
const saving = ref(false);
const formError = ref('');
function emptyForm() {
  return { category: '后端', title: '', company: '', salary: '', salary_min: '', city: '', exp: '', skills: '', requirements: '' };
}
const form = ref(emptyForm());

function openCreate() {
  editingId.value = '';
  form.value = emptyForm();
  formError.value = '';
  modalOpen.value = true;
}
function openEdit(job) {
  editingId.value = job.id;
  form.value = {
    category: job.category || '后端',
    title: job.title || '',
    company: job.company || '',
    salary: job.salary || '',
    salary_min: String(job.salary_min ?? ''),
    city: job.city || '',
    exp: job.exp || '',
    skills: (job.skills || []).join(', '),
    requirements: (job.requirements || []).join('\n'),
  };
  formError.value = '';
  modalOpen.value = true;
}
function closeModal() { modalOpen.value = false; }

async function submitForm() {
  if (!form.value.title.trim()) { formError.value = '岗位标题不能为空'; return; }
  saving.value = true;
  formError.value = '';
  const payload = {
    category: form.value.category,
    title: form.value.title.trim(),
    company: form.value.company.trim(),
    salary: form.value.salary.trim(),
    salary_min: Number(form.value.salary_min) || 0,
    city: form.value.city.trim(),
    exp: form.value.exp.trim(),
    skills: form.value.skills.split(',').map(s => s.trim()).filter(Boolean),
    requirements: form.value.requirements.split('\n').map(s => s.trim()).filter(Boolean),
  };
  try {
    if (editingId.value) await updateJob(editingId.value, payload);
    else await createJob(payload);
    modalOpen.value = false;
    await loadJobs();
  } catch (e) {
    formError.value = e.message || String(e);
  } finally {
    saving.value = false;
  }
}

async function removeJob(job) {
  if (!window.confirm(`确定删除岗位「${job.title}」吗？`)) return;
  loadError.value = '';
  try {
    await deleteJob(job.id);
    await loadJobs();
  } catch (e) {
    loadError.value = e.message || String(e);
  }
}

// 城市选项：'全部' + 数据里出现过的城市去重
const cities = computed(() => ['全部', ...new Set(jobs.value.map(j => j.city).filter(Boolean))]);

function salaryHit(job) {
  const b = salaryBuckets.find(x => x.label === selectedSalary.value) || salaryBuckets[0];
  const smin = job.salary_min ?? 0;
  return smin >= b.min && smin < b.max;
}

function searchHit(job) {
  const q = searchText.value.trim().toLowerCase();
  if (!q) return true;
  const hay = (job.title + ' ' + job.company + ' ' + (job.skills || []).join(' ')).toLowerCase();
  return hay.includes(q);
}

const CATEGORY_ORDER = { '后端': 0, '前端': 1, '算法': 2, '系统设计': 3 };
const filteredJobs = computed(() =>
  jobs.value
    .filter(j => activeFilter.value === '全部' || j.category === activeFilter.value)
    .filter(j => selectedCity.value === '全部' || j.city === selectedCity.value)
    .filter(salaryHit)
    .filter(searchHit)
    .sort((a, b) => (CATEGORY_ORDER[a.category] ?? 9) - (CATEGORY_ORDER[b.category] ?? 9))
);

function applyJob(job) {
  // 把完整 job 对象透传，SetupView 据此动态渲染 JD 面板、结论区与画像
  emit('select-job', { ...job, role: job.title });
}

onMounted(loadJobs);
</script>

<template>
  <!-- ============ HERO ============ -->
  <header class="hero">
    <div class="shell hero-grid">
      <div>
        <span class="eyebrow">AI 模拟面试官 · 读简历 · 对着 JD 出题</span>
        <h1 style="margin-top:14px;">
          挑一个岗位，<br>来一场<span class="accent">真刀真枪</span>的模拟面试
        </h1>
        <p class="lede">
          不是刷题库。它会读你的简历、对着这份 JD 出题，顺着你的回答一路深挖追问——像真面试官一样，结束后给出每个维度的结构化评分。
        </p>
        <div class="hero-cta">
          <button v-if="jobs.length" class="btn btn-primary btn-lg" @click="applyJob(jobs[0])">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            投递简历，开始面试
          </button>
          <a href="#board" class="btn btn-ghost btn-lg">浏览全部岗位</a>
        </div>
        <div class="trust">
          <div><div class="t-num">5</div><div class="t-lab">岗位方法论 Skills</div></div>
          <div class="vr" style="height:34px;"></div>
          <div><div class="t-num">6 维</div><div class="t-lab">结构化评分</div></div>
          <div class="vr" style="height:34px;"></div>
          <div><div class="t-num">全程</div><div class="t-lab">trace 可重放</div></div>
        </div>
      </div>

      <!-- Flowcard -->
      <div class="flowcard">
        <div class="fc-head">
          <span class="ph"></span>它是怎么运作的
        </div>
        <div style="margin-top:10px;">
          <div class="fstep">
            <span class="fn" style="background:var(--brand-50);color:var(--brand-700);">0</span>
            <div>
              <div class="ft">解析 JD × 简历</div>
              <div class="fd">提取技能交叉点与缺口，构建候选人画像</div>
            </div>
          </div>
          <div class="fstep">
            <span class="fn" style="background:var(--brand-50);color:var(--brand-700);">1</span>
            <div>
              <div class="ft">规划面试结构</div>
              <div class="fd">加载岗位 Skill，定下考几道、每道考什么</div>
            </div>
          </div>
          <div class="fstep">
            <span class="fn" style="background:var(--ember-100);color:var(--ember-700);">2</span>
            <div>
              <div class="ft">多轮出题 · 追问</div>
              <div class="fd">答得好加难度，答得卡给提示，顺着回答深挖</div>
            </div>
          </div>
          <div class="fstep">
            <span class="fn" style="background:var(--green-100);color:var(--green-700);">3</span>
            <div>
              <div class="ft">结构化评分报告</div>
              <div class="fd">每维度得分 + 强弱点 + 与 JD 匹配度</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>

  <!-- ============ BOARD ============ -->
  <main class="shell" id="board" style="padding-bottom:20px;">
    <div class="filters">
      <div class="seg">
        <button
          v-for="f in filters"
          :key="f"
          :class="{ on: activeFilter === f }"
          @click="activeFilter = f"
        >{{ f }}</button>
      </div>
      <div class="search-bar">
        <svg viewBox="0 0 24 24" fill="none">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
          <path d="M20 20l-3-3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <input v-model="searchText" placeholder="搜索岗位、公司或技术栈，如 Redis、分布式…">
      </div>
      <select v-model="selectedCity" class="filter-select">
        <option v-for="c in cities" :key="c" :value="c">{{ c === '全部' ? '城市 · 全部' : c }}</option>
      </select>
      <select v-model="selectedSalary" class="filter-select">
        <option v-for="b in salaryBuckets" :key="b.label" :value="b.label">{{ b.label === '不限' ? '薪资 · 不限' : b.label }}</option>
      </select>
    </div>

    <div class="board-head">
      <h2>
        {{ activeFilter === '全部' ? '为你推荐 · 全部方向' : `${activeFilter}方向` }}
        <span class="muted" style="font-size:14px;font-weight:500;"> {{ filteredJobs.length }} 个岗位</span>
      </h2>
      <button v-if="isAdmin" class="btn btn-primary btn-sm" @click="openCreate">＋ 新增岗位</button>
      <span v-else class="muted" style="font-size:13px;">岗位由管理员维护</span>
    </div>

    <div v-if="loadError" class="board-notice error">加载岗位失败：{{ loadError }}</div>

    <div v-if="loading" class="empty-board">加载岗位中…</div>

    <div v-else-if="!filteredJobs.length" class="empty-board">
      没有符合条件的岗位，试试切换分类或清空筛选条件。
    </div>

    <div class="job-grid">
      <article
        v-for="job in filteredJobs"
        :key="job.id"
        class="job"
      >
        <!-- 管理员: 悬浮增删改工具条 -->
        <div v-if="isAdmin" class="job-admin-tools">
          <button class="jat-btn" title="编辑" @click="openEdit(job)">
            <svg viewBox="0 0 24 24" fill="none" width="14" height="14"><path d="M4 20h4L18 10l-4-4L4 16v4z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
          <button class="jat-btn danger" title="删除" @click="removeJob(job)">
            <svg viewBox="0 0 24 24" fill="none" width="14" height="14"><path d="M5 7h14M9 7V5h6v2M8 7l1 12h6l1-12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </div>

        <!-- 悬浮显示招聘要求 -->
        <div class="job-reqs">
          <div class="jr-title">招聘要求 · {{ job.title }}</div>
          <ul>
            <li v-for="(r, i) in job.requirements" :key="i">{{ r }}</li>
          </ul>
          <div class="jr-skills">
            <span v-for="s in job.skills" :key="s" class="tag-skill">{{ s }}</span>
          </div>
        </div>

        <div class="job-top">
          <div class="job-logo" :style="{ background: job.logoGrad }">{{ job.logo }}</div>
          <div class="grow">
            <div class="job-title">{{ job.title }}</div>
            <div class="job-co">{{ job.company }}</div>
          </div>
        </div>

        <div class="job-meta">
          <span class="job-salary">{{ job.salary }}</span>
          <span class="sep">·</span>
          <span class="muted">{{ job.city }}</span>
          <span class="sep">·</span>
          <span class="muted">{{ job.exp }}</span>
        </div>

        <div class="job-skills">
          <span v-for="s in job.skills" :key="s" class="tag-skill">{{ s }}</span>
        </div>

        <div class="job-foot">
          <span class="muted" style="font-size:12px;">{{ job.category }}</span>
          <button
            class="applybtn ghost"
            @click="applyJob(job)"
          >
            投递并面试
            <svg viewBox="0 0 24 24" fill="none" width="15" height="15">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </article>
    </div>
  </main>

  <!-- ============ 岗位编辑弹窗 (仅管理员) ============ -->
  <div v-if="modalOpen" class="jb-overlay" @click.self="closeModal">
    <div class="jb-modal">
      <div class="jb-modal-head">
        <h3>{{ editingId ? '编辑岗位' : '新增岗位' }}</h3>
        <button class="jb-close" @click="closeModal">×</button>
      </div>
      <div class="jb-body">
        <div class="jb-row">
          <label class="jb-field">
            <span>分类</span>
            <select v-model="form.category">
              <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label class="jb-field jb-grow">
            <span>岗位标题 *</span>
            <input v-model="form.title" placeholder="如：资深后端工程师" />
          </label>
        </div>
        <label class="jb-field">
          <span>公司</span>
          <input v-model="form.company" placeholder="如：云启科技 · 基础架构组 · D轮" />
        </label>
        <div class="jb-row">
          <label class="jb-field jb-grow">
            <span>薪资文本</span>
            <input v-model="form.salary" placeholder="如：30-55K · 16薪" />
          </label>
          <label class="jb-field">
            <span>薪资下限(K)</span>
            <input v-model="form.salary_min" type="number" min="0" placeholder="30" />
          </label>
        </div>
        <div class="jb-row">
          <label class="jb-field jb-grow">
            <span>城市</span>
            <input v-model="form.city" placeholder="如：上海 / 远程" />
          </label>
          <label class="jb-field jb-grow">
            <span>经验</span>
            <input v-model="form.exp" placeholder="如：3-5 年" />
          </label>
        </div>
        <label class="jb-field">
          <span>技能（逗号分隔）</span>
          <input v-model="form.skills" placeholder="Redis, 高并发, MySQL" />
        </label>
        <label class="jb-field">
          <span>招聘要求（每行一条）</span>
          <textarea v-model="form.requirements" rows="5" placeholder="每行一条要求…"></textarea>
        </label>
        <div v-if="formError" class="jb-form-error">{{ formError }}</div>
      </div>
      <div class="jb-modal-foot">
        <button class="btn btn-ghost btn-sm" @click="closeModal">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="saving" @click="submitForm">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>

  <footer class="shell foot">
    <div class="between">
      <div class="row" style="gap:8px;color:var(--ink-500);">
        <span class="brand" style="font-size:15px;color:var(--ink-700);">
          <span class="glyph" style="width:24px;height:24px;border-radius:7px;">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 2.5l2.2 6.1 6.3.3-4.9 4 1.7 6.1L12 19.4 6.7 23l1.7-6.1-4.9-4 6.3-.3z" fill="#fff"/>
            </svg>
          </span>
          OfferAgent
        </span>
      </div>
      <span>Agent = Model + Harness </span>
    </div>
  </footer>
</template>

<style scoped>
/* 城市 / 薪资 下拉 */
.filter-select {
  height: 36px;
  padding: 0 12px;
  border-radius: var(--r-sm, 8px);
  border: 1px solid var(--ink-200, #e5e7eb);
  background: var(--paper, #fff);
  color: var(--ink-700, #374151);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
}
.filter-select:focus { outline: none; border-color: var(--brand-300, #a5b4fc); }

/* 空状态 */
.empty-board {
  padding: 48px 20px;
  text-align: center;
  color: var(--ink-400, #9ca3af);
  font-size: 14px;
  border: 1px dashed var(--ink-200, #e5e7eb);
  border-radius: var(--r-lg, 14px);
}

/* 允许悬浮要求面板溢出卡片；同时把 featured 顶部色条重新圆角 */
.job { overflow: visible; }
/* hover 时整张卡片(含其 transform 形成的层叠上下文)抬到同行/下一行卡片之上,
   否则 DOM 中靠后的卡片会盖住向下弹出的要求面板 */
.job:hover { z-index: 50; }
.job.feat::before {
  border-top-left-radius: var(--r-lg, 14px);
  border-top-right-radius: var(--r-lg, 14px);
}

/* 悬浮显示的招聘要求面板（纯展示, 不拦截点击） */
.job-reqs {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 8px);
  z-index: 40;
  background: var(--paper, #fff);
  border: 1px solid var(--ink-200, #e5e7eb);
  border-radius: var(--r-lg, 14px);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.16);
  padding: 16px 18px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-6px);
  transition: opacity 0.16s ease, transform 0.16s ease, visibility 0.16s;
  pointer-events: none;
}
.job:hover .job-reqs {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.jr-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-800, #1f2937);
  margin-bottom: 10px;
}
.job-reqs ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.job-reqs li {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-600, #4b5563);
}
.jr-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--ink-200, #e5e7eb);
}

/* 加载失败提示 */
.board-notice { padding: 10px 14px; margin-bottom: 14px; border-radius: 10px; font-size: 13px; }
.board-notice.error { background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C); }

/* 管理员悬浮在卡片右上角的编辑/删除工具 */
.job-admin-tools {
  position: absolute; top: 10px; right: 10px; z-index: 45;
  display: flex; gap: 6px; opacity: 0; transition: opacity 0.14s ease;
}
.job:hover .job-admin-tools { opacity: 1; }
.jat-btn {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--ink-200); border-radius: 8px; background: #fff;
  color: var(--ink-600, #475569); cursor: pointer;
}
.jat-btn:hover { border-color: var(--brand-300, #A5B4FC); color: var(--brand-600, #4F46E5); }
.jat-btn.danger:hover { border-color: var(--red-300, #FCA5A5); color: var(--red-600, #DC2626); }

/* 岗位编辑弹窗 */
.jb-overlay {
  position: fixed; inset: 0; z-index: 60; background: rgba(15, 23, 42, .45);
  display: flex; align-items: flex-start; justify-content: center; padding: 40px 16px; overflow: auto;
}
.jb-modal {
  width: 100%; max-width: 560px; background: #fff; border-radius: 16px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, .28); display: flex; flex-direction: column;
}
.jb-modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--ink-200, #e5e7eb);
}
.jb-modal-head h3 { margin: 0; font-size: 17px; }
.jb-close { border: none; background: none; font-size: 24px; line-height: 1; cursor: pointer; color: var(--ink-400, #9ca3af); }
.jb-body { padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; }
.jb-row { display: flex; gap: 12px; }
.jb-field { display: flex; flex-direction: column; gap: 6px; flex: 0 0 auto; }
.jb-field.jb-grow { flex: 1 1 auto; }
.jb-field > span { font-size: 12px; color: var(--ink-500, #64748b); font-weight: 600; }
.jb-field input, .jb-field select, .jb-field textarea {
  padding: 8px 10px; border: 1px solid var(--ink-200, #e5e7eb); border-radius: 8px;
  font-size: 13px; font-family: inherit; color: var(--ink-700, #334155); background: #fff; width: 100%; box-sizing: border-box;
}
.jb-field textarea { resize: vertical; }
.jb-field input:focus, .jb-field select:focus, .jb-field textarea:focus {
  outline: none; border-color: var(--brand-400, #818cf8); box-shadow: 0 0 0 3px var(--brand-50, #EEF2FF);
}
.jb-form-error { padding: 8px 12px; border-radius: 8px; background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C); font-size: 12.5px; }
.jb-modal-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--ink-200, #e5e7eb); }
</style>
