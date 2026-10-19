<script setup>
import { ref, watch } from 'vue';
import { getSessionTrace } from '../api.js';

const props = defineProps({
  sessionId: { type: String, default: '' },
  visible: { type: Boolean, default: false },
});
const emit = defineEmits(['close']);

const events = ref([]);
const loading = ref(false);
const error = ref('');

watch(() => [props.visible, props.sessionId], async ([vis, sid]) => {
  if (!vis || !sid) return;
  loading.value = true;
  error.value = '';
  try {
    events.value = await getSessionTrace(sid);
  } catch (e) {
    error.value = e.message || String(e);
    events.value = [];
  } finally {
    loading.value = false;
  }
}, { immediate: true });

// 时间戳格式化: Unix float → HH:mm:ss
function fmtTime(ts) {
  if (!ts) return '--:--:--';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// 事件摘要文本
function eventSummary(ev) {
  if (ev.type === 'transition') {
    const p = ev.payload;
    let text = `${p.from || '?'} → ${p.to || '?'}`;
    if (p.gate) text += `  (${p.gate})`;
    return text;
  }
  if (ev.type === 'compact') {
    const p = ev.payload;
    const layers = (p.layers || []).join(', ');
    return `压缩 [${layers}]  ${p.before || '?'}→${p.after || '?'} tokens`;
  }
  return JSON.stringify(ev.payload);
}

function typeColor(type) {
  if (type === 'transition') return 'var(--brand-500, #6366F1)';
  if (type === 'compact') return 'var(--amber-500, #F59E0B)';
  return 'var(--ink-400, #94A3B8)';
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="trace-overlay" @click.self="emit('close')">
      <div class="trace-panel">
        <div class="trace-head">
          <h3>Trace 重放 · 逐轮决策</h3>
          <button class="trace-close" @click="emit('close')">&times;</button>
        </div>

        <div v-if="loading" class="trace-loading">加载中…</div>
        <div v-else-if="error" class="trace-error">{{ error }}</div>
        <div v-else-if="!events.length" class="trace-empty">
          暂无 trace 事件（可能会话文件已被清理）。
        </div>

        <div v-else class="trace-body">
          <div class="trace-meta">
            共 {{ events.length }} 条事件 · 会话 {{ sessionId.slice(0, 8) }}…
          </div>
          <ol class="trace-timeline">
            <li v-for="(ev, i) in events" :key="i" class="trace-node">
              <span class="tn-dot" :style="{ background: typeColor(ev.type) }"></span>
              <div class="tn-content">
                <div class="tn-top">
                  <span class="tn-badge" :style="{ color: typeColor(ev.type), borderColor: typeColor(ev.type) }">
                    {{ ev.type }}
                  </span>
                  <span class="tn-time">{{ fmtTime(ev.ts) }}</span>
                  <span class="tn-seq">#{{ i + 1 }}</span>
                </div>
                <div class="tn-summary">{{ eventSummary(ev) }}</div>
              </div>
            </li>
          </ol>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.trace-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(15, 23, 42, .45);
  display: flex; justify-content: flex-end;
  animation: fadeIn .2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.trace-panel {
  width: 420px; max-width: 90vw; height: 100vh;
  background: #fff; box-shadow: -8px 0 40px rgba(15, 23, 42, .18);
  display: flex; flex-direction: column;
  animation: slideIn .25s ease;
}
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.trace-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--ink-100, #F1F5F9);
}
.trace-head h3 { margin: 0; font-size: 16px; color: var(--ink-800, #1E293B); }
.trace-close {
  width: 32px; height: 32px; border: none; background: none;
  font-size: 24px; color: var(--ink-400, #94A3B8); cursor: pointer; border-radius: 8px;
}
.trace-close:hover { background: var(--ink-50, #F8FAFC); color: var(--ink-700); }
.trace-loading, .trace-empty { padding: 40px 22px; text-align: center; color: var(--ink-400); font-size: 13px; }
.trace-error { padding: 16px 22px; color: var(--red-600, #DC2626); font-size: 13px; }
.trace-body { flex: 1; overflow-y: auto; padding: 16px 22px; }
.trace-meta { font-size: 12px; color: var(--ink-400); margin-bottom: 14px; }
.trace-timeline {
  list-style: none; margin: 0; padding: 0;
  position: relative;
}
.trace-timeline::before {
  content: ''; position: absolute; left: 7px; top: 8px; bottom: 8px;
  width: 2px; background: var(--ink-100, #F1F5F9);
}
.trace-node {
  display: flex; gap: 12px; padding: 10px 0; position: relative;
}
.tn-dot {
  width: 16px; height: 16px; border-radius: 50%; flex: none;
  margin-top: 4px; position: relative; z-index: 1;
  border: 2px solid #fff; box-shadow: 0 0 0 2px var(--ink-100, #F1F5F9);
}
.tn-content { flex: 1; min-width: 0; }
.tn-top { display: flex; align-items: center; gap: 8px; }
.tn-badge {
  font-size: 11px; font-weight: 700; padding: 1px 7px;
  border: 1px solid; border-radius: 4px; text-transform: uppercase;
}
.tn-time { font-size: 11px; color: var(--ink-400); font-family: var(--mono, monospace); }
.tn-seq { margin-left: auto; font-size: 11px; color: var(--ink-300, #CBD5E1); }
.tn-summary {
  margin-top: 4px; font-size: 13px; color: var(--ink-700, #334155);
  line-height: 1.5; word-break: break-all;
}
</style>
