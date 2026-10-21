import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { askQuestion, submitAnswer, finishSession } from '../api.js';

export function useInterview(session, emit) {
  const messages = ref([]);
  const answer = ref('');
  const busy = ref(false);
  const error = ref('');
  const phase = ref('idle'); // idle | asked | graded | done | error
  const chainJustClosed = ref(false); // 上一次提交刚闭合一条追问链 (next-bar 文案用)

  const elapsed = ref(0);
  let timerInterval = null;

  const timerText = computed(() => {
    const m = Math.floor(elapsed.value / 60).toString().padStart(2, '0');
    const s = (elapsed.value % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  });

  // 主题消息 (追问单独带 is_follow_up 标记, 不占"第 X / N 题"计数)
  const aiMessages = computed(() => messages.value.filter(m => m.role === 'ai' && !m.is_follow_up));

  // 每道主题挂了多少条追问 (按 qIndex 归组), 供进度栏小标记
  const fuCountByIndex = computed(() => {
    const c = {};
    for (const m of messages.value) {
      if (m.role === 'ai' && m.is_follow_up) c[m.qIndex] = (c[m.qIndex] || 0) + 1;
    }
    return c;
  });

  // 当前待回答的是否追问 (最后一条 AI 消息未评分且标了追问)
  const answeringFollowUp = computed(() => {
    const ai = messages.value.filter(m => m.role === 'ai');
    const last = ai[ai.length - 1];
    return !!(last && !last.grade && last.is_follow_up);
  });

  const progressItems = computed(() => {
    const total = session.num_questions || Math.max(aiMessages.value.length, 1);
    const items = aiMessages.value.map((m, i) => ({
      index: i + 1,
      title: m.content.length > 20 ? m.content.slice(0, 20) + '…' : m.content,
      status: m.grade ? 'done' : (i === aiMessages.value.length - 1 ? 'cur' : 'done'),
      score: m.grade ? m.grade.score : null,
      fuCount: fuCountByIndex.value[i] || 0,
    }));
    const remaining = Math.max(0, total - items.length);
    for (let i = 0; i < remaining; i++) {
      items.push({ index: items.length + 1, title: '待出题', status: 'todo', score: null, fuCount: 0 });
    }
    return items;
  });

  const currentQuestion = computed(() => {
    const ai = aiMessages.value;
    return ai.length ? ai[ai.length - 1] : null;
  });

  const threadRef = ref(null);
  function scrollToBottom() {
    nextTick(() => {
      if (threadRef.value) threadRef.value.scrollTop = threadRef.value.scrollHeight;
    });
  }

  async function ask() {
    busy.value = true;
    error.value = '';
    try {
      const res = await askQuestion(session.session_id);
      if (res.done) {
        phase.value = 'done';
      } else {
        const qIndex = aiMessages.value.length;
        messages.value.push({
          role: 'ai',
          content: res.question,
          question_id: res.question_id,
          grade: null,
          id: `ai-${Date.now()}-${Math.random()}`,
          qIndex,
        });
        phase.value = 'asked';
        answer.value = '';
        chainJustClosed.value = false;
      }
      scrollToBottom();
    } catch (e) {
      error.value = e.message || String(e);
      phase.value = 'error';
    } finally {
      busy.value = false;
    }
  }

  async function submit() {
    if (!answer.value.trim() || busy.value) return;
    const ans = answer.value.trim();
    // 先把用户回答乐观插入并立即显示, 再请求 AI 评分 (顺序: 回答 → 思考中 → 评分)
    const userMsg = { role: 'user', content: ans, id: `user-${Date.now()}-${Math.random()}` };
    messages.value.push(userMsg);
    answer.value = '';
    busy.value = true;
    error.value = '';
    scrollToBottom();
    try {
      const res = await submitAnswer(session.session_id, ans);
      // 本次评分落在最后一条未评分的 AI 消息上 (主题或追问)
      const lastUngraded = [...messages.value].reverse().find(m => m.role === 'ai' && !m.grade);
      if (lastUngraded) lastUngraded.grade = res;
      if (res.follow_up_question) {
        // 追问来了: 新消息归在同一主题编号下, 继续作答 (不出"下一题"栏)
        const qIndex = lastUngraded ? lastUngraded.qIndex : aiMessages.value.length - 1;
        messages.value.push({
          role: 'ai',
          content: res.follow_up_question,
          is_follow_up: true,
          follow_up_of: res.follow_up_of || null,
          qIndex,
          question_id: null,
          grade: null,
          id: `ai-${Date.now()}-${Math.random()}`,
        });
        phase.value = 'asked';
        answer.value = '';
        chainJustClosed.value = false;
      } else {
        phase.value = 'graded';
        // 本次被评的是追问且无后续追问 → 刚闭合一条追问链
        chainJustClosed.value = !!(res.is_follow_up || (lastUngraded && lastUngraded.is_follow_up));
      }
      scrollToBottom();
    } catch (e) {
      error.value = e.message || String(e);
      // 评分失败: 回滚乐观插入的回答并还原输入框, 便于重试
      const idx = messages.value.indexOf(userMsg);
      if (idx !== -1) messages.value.splice(idx, 1);
      answer.value = ans;
    } finally {
      busy.value = false;
    }
  }

  async function nextQuestion() {
    await ask();
  }

  async function finishAll() {
    busy.value = true;
    error.value = '';
    try {
      const rep = await finishSession(session.session_id);
      emit('finished', { ...rep, role: session.role, topic: session.topic });
    } catch (e) {
      error.value = e.message || String(e);
    } finally {
      busy.value = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (phase.value === 'asked' && !busy.value) submit();
    }
  }

  onMounted(() => {
    timerInterval = setInterval(() => elapsed.value++, 1000);
    ask();
  });

  onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
  });

  return {
    messages, answer, busy, error, phase,
    elapsed, timerText,
    aiMessages, progressItems, currentQuestion,
    answeringFollowUp, chainJustClosed,
    threadRef, scrollToBottom,
    ask, submit, nextQuestion, finishAll, handleKeydown,
  };
}
