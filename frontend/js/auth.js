/**
 * auth.js — Authentication and Session Manager for Cashio Security
 */

const auth = {
  TOKEN_KEY: "cashio_token",
  USER_KEY: "cashio_user",
  ADMIN_TOKEN_KEY: "cashio_admin_token",

  saveUserSession(token, user) {
    sessionStorage.setItem(this.TOKEN_KEY, token);
    sessionStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  saveAdminSession(token) {
    sessionStorage.setItem(this.ADMIN_TOKEN_KEY, token);
  },

  getToken() {
    return sessionStorage.getItem(this.TOKEN_KEY);
  },

  getAdminToken() {
    return sessionStorage.getItem(this.ADMIN_TOKEN_KEY);
  },

  getUser() {
    const raw = sessionStorage.getItem(this.USER_KEY);
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  isAdminAuthenticated() {
    return !!this.getAdminToken();
  },

  /**
   * Guard for customer pages: redirects to login if unauthenticated
   */
  requireAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = "login.html";
    }
  },

  /**
   * Guard for admin portal: redirects to admin-login if unauthenticated
   */
  requireAdmin() {
    if (!this.isAdminAuthenticated()) {
      window.location.href = "admin-login.html";
    }
  },

  /**
   * Logout customer
   */
  async logout() {
    try {
      await api.post("/auth/logout", {});
    } catch (e) {
      // Continue client logout even if backend call fails
    } finally {
      sessionStorage.removeItem(this.TOKEN_KEY);
      sessionStorage.removeItem(this.USER_KEY);
      window.location.href = "login.html?logged_out=1";
    }
  },

  /**
   * Logout admin
   */
  logoutAdmin() {
    sessionStorage.removeItem(this.ADMIN_TOKEN_KEY);
    window.location.href = "admin-login.html";
  },

  /**
   * XSS Defense: sanitize untrusted user text before innerHTML rendering
   */
  escapeHTML(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
};

