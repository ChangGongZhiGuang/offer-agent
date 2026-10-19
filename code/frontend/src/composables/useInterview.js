import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { askQuestion, submitAnswer, finishSession } from '../api.js';

export function useInterview(session, emit) {
  const messages = ref([]);
  const answer = ref('');
  const busy = ref(false);
  const error = ref('');
  const phase = ref('idle'); // idle | asked | graded | done | error

  const elapsed = ref(0);
  let timerInterval = null;

  const timerText = computed(() => {
    const m = Math.floor(elapsed.value / 60).toString().padStart(2, '0');
    const s = (elapsed.value % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  });

  const aiMessages = computed(() => messages.value.filter(m => m.role === 'ai'));

  const progressItems = computed(() => {
    const total = session.num_questions || Math.max(aiMessages.value.length, 1);
    const items = aiMessages.value.map((m, i) => ({
      index: i + 1,
      title: m.content.length > 20 ? m.content.slice(0, 20) + '…' : m.content,
      status: m.grade ? 'done' : (i === aiMessages.value.length - 1 ? 'cur' : 'done'),
      score: m.grade ? m.grade.score : null,
    }));
    const remaining = Math.max(0, total - items.length);
    for (let i = 0; i < remaining; i++) {
      items.push({ index: items.length + 1, title: '待出题', status: 'todo', score: null });
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
      const lastAi = [...messages.value].reverse().find(m => m.role === 'ai');
      if (lastAi) lastAi.grade = res;
      phase.value = 'graded';
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
    threadRef, scrollToBottom,
    ask, submit, nextQuestion, finishAll, handleKeydown,
  };
}
