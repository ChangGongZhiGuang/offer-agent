// 通过 vite proxy /api -> http://127.0.0.1:8000, 同源避免 CORS。
const BASE = '/api';

// 登录凭证在 localStorage 中的键名
const TOKEN_KEY = 'if_token';
const USER_KEY = 'if_user';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}
export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch (_) {
    return null;
  }
}
export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  // 有 token 则统一注入 Authorization: Bearer (覆盖 create-session / finish / history)
  const token = getToken();
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(BASE + path, { ...options, headers });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) {
      /* 后端可能未返回 JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

// ── 认证 ────────────────────────────────────────────
export async function register(username, password) {
  const resp = await request('/auth/register', {
    method: 'POST', body: JSON.stringify({ username, password }),
  });
  setAuth(resp.token, resp.user);
  return resp.user;
}

export async function login(username, password) {
  const resp = await request('/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  });
  setAuth(resp.token, resp.user);
  return resp.user;
}

export function logout() {
  // 后端吊销失败不阻断前端登出 (token 仍会本地清除)
  return request('/auth/logout', { method: 'POST' }).catch(() => {});
}

export function getMe() {
  return request('/auth/me');
}

// ── 历史记录 ────────────────────────────────────────
export function listHistory() {
  return request('/history');
}

export function getHistoryDetail(sessionId) {
  return request(`/history/${encodeURIComponent(sessionId)}`);
}

export function deleteHistory(sessionId) {
  return request(`/history/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
}

export function startSession({ role, topic, profile, num_questions, jd_keywords, profile_struct }) {
  return request('/sessions', {
    method: 'POST',
    body: JSON.stringify({ role, topic, profile, num_questions, jd_keywords, profile_struct }),
  });
}

// 上传简历文件 (PDF/Word/txt)，后端解析+分析成结构化画像。
// 用 FormData，故不能走 request() 的 JSON 头。
export async function uploadResume(file, role, jd) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('role', role || '');
  fd.append('jd', jd || '');
  const res = await fetch(BASE + '/resume', { method: 'POST', body: fd });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) {
      /* 后端可能未返回 JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

// ── 我的简历 (登录用户维护的简历正文) ──────────────
export function getMyResume() {
  return request('/profile/me');
}

export function saveMyResume(text, filename) {
  return request('/profile/me', {
    method: 'PUT', body: JSON.stringify({ text, filename: filename || '' }),
  });
}

export function deleteMyResume() {
  return request('/profile/me', { method: 'DELETE' });
}

// 从已存正文按当前岗位/JD 现生成结构化画像 (JSON, 非 multipart)
export function analyzeResumeText(text, role, jd) {
  return request('/resume/analyze', {
    method: 'POST', body: JSON.stringify({ text, role: role || '', jd: jd || '' }),
  });
}

export function askQuestion(sessionId) {
  return request(`/sessions/${sessionId}/ask`, { method: 'POST' });
}

export function submitAnswer(sessionId, answer) {
  return request(`/sessions/${sessionId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  });
}

export function finishSession(sessionId) {
  return request(`/sessions/${sessionId}/finish`, { method: 'POST' });
}

export function getStatus(sessionId) {
  return request(`/sessions/${sessionId}`);
}

// ── admin: 题目 ───────────────────────────────────────────────
const DIFF_TO_BACKEND = { easy: 'easy', mid: 'medium', hard: 'hard' };
const DIFF_FROM_BACKEND = { easy: 'easy', medium: 'mid', hard: 'hard' };

export function listQuestions(role = '') {
  const qs = role ? `?role=${encodeURIComponent(role)}` : '';
  return request(`/admin/questions${qs}`).then(list =>
    list.map(q => ({ ...q, diff: DIFF_FROM_BACKEND[q.difficulty] || q.difficulty }))
  );
}

export function createQuestion({ id, stem, role, topic, answer, difficulty, fu }) {
  return request('/admin/questions', {
    method: 'POST',
    body: JSON.stringify({
      id, stem, role, topic, answer, fu,
      difficulty: DIFF_TO_BACKEND[difficulty] || difficulty,
    }),
  });
}

export function updateQuestion(id, { stem, role, topic, answer, difficulty, fu }) {
  return request(`/admin/questions/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify({
      id, stem, role, topic, answer, fu,
      difficulty: DIFF_TO_BACKEND[difficulty] || difficulty,
    }),
  }).then(q => ({ ...q, diff: DIFF_FROM_BACKEND[q.difficulty] || q.difficulty }));
}

export function deleteQuestion(id) {
  return request(`/admin/questions/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ── admin: 岗位 ───────────────────────────────────────────────
export function listPositions() {
  return request('/admin/positions');
}

export function createPosition({ name, color }) {
  return request('/admin/positions', {
    method: 'POST',
    body: JSON.stringify({ name, color }),
  });
}

export function deletePosition(id) {
  return request(`/admin/positions/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ── 岗位广场: 招聘卡片 (浏览公开; 增删改需管理员) ──────────────
export function getJobs() {
  return request('/jobs');
}

export function createJob(payload) {
  return request('/jobs', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateJob(id, payload) {
  return request(`/jobs/${encodeURIComponent(id)}`, {
    method: 'PUT', body: JSON.stringify(payload),
  });
}

export function deleteJob(id) {
  return request(`/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ── 用户 / 角色管理 (仅超级管理员 root) ────────────────────────
export function listUsers() {
  return request('/admin/users');
}

export function setUserRole(id, role) {
  return request(`/admin/users/${encodeURIComponent(id)}/role`, {
    method: 'PUT', body: JSON.stringify({ role }),
  });
}

// ── Trace 重放 ────────────────────────────────────────────────
export function getSessionTrace(sessionId) {
  return request(`/sessions/${encodeURIComponent(sessionId)}/trace`);
}
