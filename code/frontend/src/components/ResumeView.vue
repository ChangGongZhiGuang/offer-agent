<!-- frontend/src/components/ResumeView.vue -->
<script setup>
import { ref, onMounted } from 'vue';
import { getMyResume, saveMyResume, deleteMyResume, uploadResume } from '../api.js';

const loading = ref(true);
const saving = ref(false);
const parsing = ref(false);
const error = ref('');

// 已存简历摘要 + 正文
const exists = ref(false);
const filename = ref('');
const size = ref(0);
const updatedAt = ref('');
const text = ref('');

const editing = ref(false);     // 是否处于正文编辑态
const fileInput = ref(null);
const pickedName = ref('');     // 新选文件的名字 (保存时作为来源文件名)

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const r = await getMyResume();
    exists.value = !!r.exists;
    filename.value = r.filename || '';
    size.value = r.size || 0;
    updatedAt.value = r.updated_at || '';
    text.value = r.text || '';
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

function onPickFile(e) {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  pickedName.value = f.name;
  parseFile(f);
}

// 上传解析: 仅把正文载入编辑区预览, 不自动保存 (保守做法)
async function parseFile(f) {
  parsing.value = true;
  error.value = '';
  try {
    const res = await uploadResume(f, '', '');
    text.value = res.resume_text || '';
    editing.value = true;
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    parsing.value = false;
  }
}

async function save() {
  if (!text.value.trim()) {
    error.value = '简历正文不能为空';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    const r = await saveMyResume(text.value, pickedName.value || filename.value);
    exists.value = true;
    filename.value = r.filename || '';
    size.value = r.size || 0;
    updatedAt.value = r.updated_at || '';
    pickedName.value = '';
    editing.value = false;
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    saving.value = false;
  }
}

async function remove() {
  if (!window.confirm('确定删除已保存的简历吗？此操作不可恢复。')) return;
  error.value = '';
  try {
    await deleteMyResume();
    exists.value = false;
    filename.value = '';
    size.value = 0;
    updatedAt.value = '';
    text.value = '';
    editing.value = false;
  } catch (e) {
    error.value = e.message || String(e);
  }
}

function startEdit() { editing.value = true; }

function fmtDate(s) {
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 16);
}
function fmtSize(n) {
  if (!n) return '0 B';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

onMounted(load);
</script>

<template>
  <main class="shell page">
    <div class="crumb"><span class="c-now">我的简历</span></div>

    <div class="rs-head">
      <h2>我的简历</h2>
      <button class="btn btn-ghost btn-sm" :disabled="loading" @click="load">刷新</button>
    </div>
    <p class="rs-hint">
      上传一次即可保存简历正文, 之后在「我的投递」会自动填入, 无需重复上传。
      开始面试时仍会按当前岗位 JD 调用大模型生成针对性画像。
    </p>

    <div v-if="error" class="rs-error">{{ error }}</div>

    <div v-if="loading" class="rs-empty">加载中…</div>

    <section v-else class="rs-card">
      <!-- 已存摘要 -->
      <div v-if="exists && !editing" class="rs-meta">
        <div class="rs-meta-row">
          <span class="rs-meta-label">当前简历</span>
          <span class="rs-meta-val">{{ filename || '（未命名）' }}</span>
        </div>
        <div class="rs-meta-row">
          <span class="rs-meta-label">大小 / 更新</span>
          <span class="rs-meta-val">{{ fmtSize(size) }} · {{ fmtDate(updatedAt) }}</span>
        </div>
        <div class="rs-actions">
          <label class="btn btn-ghost btn-sm">
            重新上传覆盖
            <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" hidden @change="onPickFile" />
          </label>
          <button class="btn btn-ghost btn-sm" @click="startEdit">编辑正文</button>
          <button class="btn btn-ghost btn-sm danger" @click="remove">删除</button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!exists && !editing" class="rs-empty">
        还没有保存的简历。
        <label class="btn btn-primary btn-sm" style="margin-left:10px;">
          上传简历
          <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" hidden @change="onPickFile" />
        </label>
      </div>

      <!-- 编辑 / 预览正文 -->
      <div v-else class="rs-edit">
        <div class="rs-edit-bar">
          <span class="rs-edit-tip">
            {{ exists ? '编辑后将覆盖已存简历' : '解析预览 · 确认后保存' }}
            <template v-if="pickedName"> · 来源: {{ pickedName }}</template>
          </span>
          <label class="btn btn-ghost btn-sm">
            {{ parsing ? '解析中…' : '换一份文件' }}
            <input type="file" accept=".pdf,.doc,.docx,.txt" hidden :disabled="parsing" @change="onPickFile" />
          </label>
        </div>
        <textarea v-model="text" rows="18" class="rs-textarea" placeholder="简历正文…" />
        <div class="rs-edit-actions">
          <button v-if="exists" class="btn btn-ghost btn-sm" @click="editing = false">取消</button>
          <button class="btn btn-primary btn-sm" :disabled="saving || !text.trim()" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.rs-head { display: flex; align-items: center; gap: 12px; margin: 6px 0 8px; }
.rs-head h2 { font-size: 20px; margin: 0; }
.rs-hint { color: var(--ink-500); font-size: 13px; margin: 0 0 16px; line-height: 1.6; }
.rs-error { padding: 10px 14px; margin-bottom: 14px; border-radius: 10px; background: var(--red-50, #FEF2F2); color: var(--red-700, #B91C1C); font-size: 13px; }
.rs-card { background: #fff; border: 1px solid var(--ink-200); border-radius: 14px; padding: 20px 22px; }
.rs-empty { padding: 28px 16px; text-align: center; color: var(--ink-500); font-size: 13px; }
.rs-meta-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.rs-meta-label { width: 96px; color: var(--ink-500); font-size: 13px; }
.rs-meta-val { color: var(--ink-800, #1E293B); font-size: 14px; font-weight: 600; }
.rs-actions { display: flex; gap: 10px; margin-top: 16px; }
.rs-actions .btn.danger { color: var(--red-600, #DC2626); }
.rs-edit-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.rs-edit-tip { color: var(--ink-500); font-size: 12px; }
.rs-textarea { width: 100%; box-sizing: border-box; padding: 12px 14px; border: 1px solid var(--ink-200); border-radius: 10px; font-size: 13px; line-height: 1.6; font-family: var(--mono, monospace); color: var(--ink-700, #334155); resize: vertical; }
.rs-textarea:focus { outline: none; border-color: var(--brand-400, #818cf8); box-shadow: 0 0 0 3px var(--brand-50, #EEF2FF); }
.rs-edit-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
</style>
