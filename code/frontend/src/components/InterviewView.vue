<script setup>
import { useInterview } from '../composables/useInterview.js';
import { renderRich } from '../composables/useMarkdown.js';

const props = defineProps({
  session: { type: Object, required: true },
});
const emit = defineEmits(['finished']);

const {
  messages, answer, busy, error, phase,
  timerText, aiMessages, progressItems,
  threadRef, submit, nextQuestion, finishAll, handleKeydown,
  ask,
} = useInterview(props.session, emit);
</script>

<template>
  <div class="interview-app">
    <!-- top info bar -->
    <div class="ibar">
      <div class="brand">
        <span class="glyph" style="width:26px;height:26px;border-radius:7px;">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 2.5l2.2 6.1 6.3.3-4.9 4 1.7 6.1L12 19.4 6.7 23l1.7-6.1-4.9-4 6.3-.3z" fill="#fff"/>
          </svg>
        </span>
      </div>
      <div class="vr" style="height:26px;"></div>
      <div class="i-job">
        模拟面试 · <b>{{ session.role }}</b> · {{ session.topic }}
      </div>
      <div class="grow"></div>
      <div class="qcount">
        <span class="dot" style="background:var(--ember-500);"></span>
        第 {{ aiMessages.length }} / {{ session.num_questions || '?' }} 题
      </div>
      <div class="vr" style="height:22px;"></div>
      <div class="i-timer">
        <svg viewBox="0 0 24 24" fill="none" width="15" height="15">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>
          <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        {{ timerText }}
      </div>
      <button class="btn btn-ghost btn-sm" :disabled="busy" @click="finishAll">结束面试</button>
    </div>

    <div class="i-body">
      <!-- left progress rail -->
      <aside class="rail">
        <div class="rail-sec">
          <div class="rail-h">面试进度</div>
          <div class="qprog">
            <div
              v-for="item in progressItems"
              :key="item.index"
              class="qprog-item"
              :class="{ cur: item.status === 'cur' }"
            >
              <span class="qp-dot" :class="item.status">
                <svg v-if="item.status === 'done'" viewBox="0 0 24 24" fill="none" width="11" height="11">
                  <path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <template v-else>{{ item.index }}</template>
              </span>
              <span class="qp-name">{{ item.title }}</span>
              <span v-if="item.score !== null" class="qp-score">{{ item.score }}</span>
              <span v-else-if="item.status === 'cur'" class="badge badge-ember" style="height:18px;padding:0 7px;font-size:10px;flex:none;">进行中</span>
            </div>
          </div>
        </div>
        <div class="mini-profile">
          <div class="rail-h">候选人画像</div>
          <div class="mp-row">
            <span class="avatar avatar-user" style="width:34px;height:34px;font-size:13px;">我</span>
            <div>
              <div class="mp-name">{{ session.role }} 候选人</div>
              <div class="mp-meta">{{ session.topic }}</div>
            </div>
          </div>
          <div class="mp-tags" v-if="session.profile">
            <span class="badge badge-ink" style="font-size:11px;white-space:normal;height:auto;padding:4px 8px;line-height:1.4;max-width:220px;">
              {{ session.profile.length > 80 ? session.profile.slice(0, 80) + '…' : session.profile }}
            </span>
          </div>
        </div>
      </aside>

      <!-- center: thread + composer -->
      <div class="thread-wrap">
        <div class="dimbar">
          <span class="dlabel">考察方向</span>
          <span class="dval">{{ session.topic }}</span>
          <span class="badge badge-violet">{{ session.role }}</span>
          <div class="grow"></div>
          <span class="badge badge-ink mono">Examiner 出题 · Grader 评分</span>
        </div>

        <div class="thread" ref="threadRef">
          <div v-if="error" class="error-inline">{{ error }}</div>
          <div v-if="phase === 'error'" style="text-align:center;margin-top:12px;">
            <button class="btn btn-ghost btn-sm" @click="ask">重试</button>
          </div>

          <template v-for="(msg, idx) in messages" :key="msg.id">
            <div
              v-if="msg.role === 'ai'"
              class="msg ai"
              :class="{ cur: !msg.grade && idx === messages.length - 1 }"
            >
              <span class="avatar avatar-ai">AI</span>
              <div class="bub">
                <div class="qmeta">
                  <span class="badge badge-brand">Q{{ msg.qIndex + 1 }}</span>
                  <span v-if="msg.grade" class="badge badge-green">
                    <svg viewBox="0 0 24 24" fill="none" width="11" height="11">
                      <path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    得分 {{ msg.grade.score }} / 5
                  </span>
                  <span v-else-if="!msg.grade && idx === messages.length - 1 && !busy" class="badge badge-ember">作答中</span>
                </div>
                <div class="md" v-html="renderRich(msg.content)"></div>
                <div v-if="msg.grade" class="rubric">
                  <span class="rl">AI 反馈</span>
                  <div v-if="msg.grade.feedback" class="fb-text md" v-html="renderRich(msg.grade.feedback)"></div>
                  <div v-if="(msg.grade.weakness_tags || []).length" class="fb-tags">
                    <span v-for="tag in msg.grade.weakness_tags" :key="tag" class="fb-tag">{{ tag }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="msg user">
              <span class="avatar avatar-user">我</span>
              <div class="bub md" v-html="renderRich(msg.content)"></div>
            </div>
          </template>

          <div v-if="busy" class="msg ai">
            <span class="avatar avatar-ai">AI</span>
            <div class="bub" style="color:var(--ink-400);"><span class="thinking-dots">思考中</span></div>
          </div>

          <div v-if="phase === 'done'" class="done-banner">
            <div>
              <div style="font-size:15px;font-weight:700;color:var(--brand-700);">题目已全部作答完毕</div>
              <div style="font-size:13px;color:var(--ink-500);margin-top:3px;">点击右侧生成本场结构化评分报告</div>
            </div>
            <button class="btn btn-primary" :disabled="busy" @click="finishAll">
              {{ busy ? '生成中…' : '生成评分报告' }}
              <svg viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>

        <div class="composer" v-if="phase === 'asked'">
          <div class="comp-box">
            <textarea v-model="answer" class="comp-textarea" placeholder="输入你的回答…（可以先讲思路，再补细节）" rows="3" @keydown="handleKeydown"></textarea>
            <div class="comp-foot">
              <div class="comp-hint"><kbd>Enter</kbd> 提交 &nbsp;·&nbsp; <kbd>Shift</kbd>+<kbd>Enter</kbd> 换行 &nbsp;·&nbsp; 支持 Markdown</div>
              <button class="btn btn-primary btn-sm" :disabled="busy || !answer.trim()" @click="submit">{{ busy ? '评分中…' : '提交回答 →' }}</button>
            </div>
          </div>
        </div>

        <div v-else-if="phase === 'graded'" class="next-bar">
          <span class="muted" style="font-size:13px;">已记录并评分，继续下一题或直接结束</span>
          <div style="display:flex;gap:10px;">
            <button class="btn btn-ghost btn-sm" :disabled="busy" @click="finishAll">结束并出报告</button>
            <button class="btn btn-primary btn-sm" :disabled="busy" @click="nextQuestion">{{ busy ? '处理中…' : '下一题 →' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* AI 反馈正文：整行块级排版，自然换行，不再用固定高度的 chip 导致与标签重叠 */
.bub .rubric .fb-text {
  width: 100%;
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--ink-600, #4b5563);
  white-space: pre-wrap;
  word-break: break-word;
}
/* 富文本（Markdown + 数学）容器：v-html 子节点用 :deep 才能命中 */
.md { line-height: 1.7; word-break: break-word; white-space: normal; }
.md :deep(p) { margin: 0 0 8px; }
.md :deep(p:last-child) { margin-bottom: 0; }
.md :deep(ul), .md :deep(ol) { margin: 6px 0; padding-left: 22px; }
.md :deep(li) { margin: 3px 0; }
.md :deep(li > p) { margin: 0; }
.md :deep(strong) { font-weight: 700; }
.md :deep(em) { font-style: italic; }
.md :deep(h1), .md :deep(h2), .md :deep(h3), .md :deep(h4) {
  font-size: 1.05em; font-weight: 700; margin: 12px 0 6px; line-height: 1.4;
}
.md :deep(code) {
  font-family: var(--font-mono, monospace);
  background: rgba(15, 23, 42, 0.06);
  padding: 1.5px 6px; border-radius: 5px; font-size: 0.88em;
}
.md :deep(pre) {
  background: #0f172a; color: #e2e8f0;
  padding: 13px 15px; border-radius: 10px; overflow-x: auto; margin: 9px 0;
  font-size: 12.5px; line-height: 1.55;
}
.md :deep(pre code) { background: none; padding: 0; color: inherit; }
.md :deep(blockquote) {
  border-left: 3px solid var(--ink-200, #e2e8f0);
  padding-left: 12px; margin: 8px 0; color: var(--ink-500, #64748b);
}
.md :deep(a) { color: var(--brand-600, #4f46e5); text-decoration: underline; }
.md :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 0.92em; }
.md :deep(th), .md :deep(td) { border: 1px solid var(--ink-200, #e2e8f0); padding: 5px 10px; }
.md :deep(.katex-display) { margin: 10px 0; overflow-x: auto; overflow-y: hidden; }
/* 反馈区用富文本渲染后，去掉原 pre-wrap（否则标签间换行会变成多余空行） */
.bub .rubric .fb-text.md { white-space: normal; }
/* 用户气泡是深色（品牌色）背景，富文本元素需提亮以保证可读性 */
.msg.user .bub.md :deep(code) { background: rgba(255, 255, 255, 0.2); color: #fff; }
.msg.user .bub.md :deep(pre) { background: rgba(0, 0, 0, 0.3); }
.msg.user .bub.md :deep(a) { color: #fff; }
.msg.user .bub.md :deep(blockquote) { border-left-color: rgba(255, 255, 255, 0.45); color: rgba(255, 255, 255, 0.88); }
.msg.user .bub.md :deep(th), .msg.user .bub.md :deep(td) { border-color: rgba(255, 255, 255, 0.32); }
.bub .rubric .fb-tags {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.bub .rubric .fb-tag {
  display: inline-flex;
  align-items: center;
  height: auto;
  padding: 4px 10px;
  border-radius: var(--r-sm, 8px);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.3;
  color: var(--amber-600, #d97706);
  background: var(--amber-50, #fffbeb);
  border: 1px solid var(--amber-100, #fef3c7);
}
</style>
