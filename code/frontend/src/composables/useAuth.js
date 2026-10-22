import { ref, computed } from 'vue';
import {
  login as apiLogin, register as apiRegister, logout as apiLogout,
  changePassword as apiChangePassword, deactivate as apiDeactivate,
  getMe, getStoredUser, clearAuth, getToken,
} from '../api.js';

// 模块级单例: 全应用共享同一份登录状态
const token = ref(getToken());
const user = ref(getStoredUser());
const ready = ref(false);   // 是否已完成首屏 /auth/me 校验
const busy = ref(false);
const error = ref('');

const isAuthenticated = computed(() => !!token.value && !!user.value);

// 角色门槛: admin/root 可管理岗位与题库; 仅 root 可设/撤管理员
const isAdmin = computed(() => ['admin', 'root'].includes(user.value?.role));
const isRoot = computed(() => user.value?.role === 'root');

export function useAuth() {
  async function _afterAuth(u) {
    user.value = u;
    token.value = getToken();
    error.value = '';
    return u;
  }

  async function login(username, password) {
    busy.value = true;
    error.value = '';
    try {
      const u = await apiLogin(username, password);
      return await _afterAuth(u);
    } catch (e) {
      error.value = e.message || String(e);
      throw e;
    } finally {
      busy.value = false;
    }
  }

  async function register(username, password) {
    busy.value = true;
    error.value = '';
    try {
      const u = await apiRegister(username, password);
      return await _afterAuth(u);
    } catch (e) {
      error.value = e.message || String(e);
      throw e;
    } finally {
      busy.value = false;
    }
  }

  async function logout() {
    await apiLogout();
    clearAuth();
    token.value = '';
    user.value = null;
  }

  // 服务端在改密/注销成功后已吊销全部 token, 本地同步清登录态 → 回登录页
  function _dropSession() {
    clearAuth();
    token.value = '';
    user.value = null;
  }

  async function changePassword(oldPwd, newPwd) {
    busy.value = true;
    error.value = '';
    try {
      await apiChangePassword(oldPwd, newPwd);
      _dropSession();
    } catch (e) {
      error.value = e.message || String(e);
      throw e;
    } finally {
      busy.value = false;
    }
  }

  async function deactivateAccount(password) {
    busy.value = true;
    error.value = '';
    try {
      await apiDeactivate(password);
      _dropSession();
    } catch (e) {
      error.value = e.message || String(e);
      throw e;
    } finally {
      busy.value = false;
    }
  }

  // 首屏校验 token 有效性: 失效则清除本地登录态
  async function refreshMe() {
    if (!token.value) { ready.value = true; return; }
    try {
      const me = await getMe();
      user.value = me;
    } catch (_) {
      clearAuth();
      token.value = '';
      user.value = null;
    } finally {
      ready.value = true;
    }
  }

  return {
    token, user, ready, busy, error, isAuthenticated, isAdmin, isRoot,
    login, register, logout, changePassword, deactivateAccount, refreshMe,
  };
}
