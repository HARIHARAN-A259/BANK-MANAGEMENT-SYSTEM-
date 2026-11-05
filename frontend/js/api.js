/**
 * api.js — Centralized HTTP Client for Cashio Security Frontend
 * Handles Bearer token injection, response parsing, error alerts, and PDF downloads.
 */

// Supports both:
// 1. Hosted via FastAPI on http://127.0.0.1:8000 (relative paths)
// 2. Direct file opening or separate dev server (http://127.0.0.1:8000)
const API_BASE = (window.location.protocol === "file:") 
  ? "http://127.0.0.1:8000" 
  : "";

const api = {
  /**
   * Core request method
   */
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    // Retrieve JWT from sessionStorage
    const token = sessionStorage.getItem("cashio_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Set JSON content-type if body is provided and not FormData
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle session expiry / unauthorized
      if (response.status === 401) {
        // Do not redirect if already on login or register
        const isAuthPage = window.location.pathname.includes("login.html") || 
                           window.location.pathname.includes("register.html") ||
                           window.location.pathname.includes("admin-login.html");
        if (!isAuthPage) {
          sessionStorage.removeItem("cashio_token");
          sessionStorage.removeItem("cashio_user");
          window.location.href = "login.html?expired=1";
          return null;
        }
      }

      // Check if response is a downloadable file (PDF / octet-stream)
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/pdf") || contentType.includes("octet-stream")) {
        if (!response.ok) {
          throw new Error("Failed to download document");
        }
        return await response.blob();
      }

      // Parse JSON response
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.detail || data.message || `Request failed with status ${response.status}`;
        const err = new Error(errorMsg);
        err.status = response.status;
        err.data = data;
        throw err;
      }

      return data;
    } catch (err) {
      // Re-throw so caller can display specific field errors or toasts
      throw err;
    }
  },

  // HTTP Helper shortcuts
  get(endpoint) {
    return this.request(endpoint, { method: "GET" });
  },

  post(endpoint, body) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  put(endpoint, body) {
    return this.request(endpoint, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  delete(endpoint, body) {
    return this.request(endpoint, {
      method: "DELETE",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  /**
   * Download a blob as a file in the user's browser
   */
  downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  },

  /**
   * Currency formatter (Integer Paise -> Formatted Rupee String)
   */
  formatPaise(paise) {
    if (typeof paise !== "number") return "₹0.00";
    const rupees = paise / 100;
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(rupees);
  },

  /**
   * Parse rupee input float to integer paise without float-rounding errors
   */
  rupeesToPaise(rupeesFloat) {
    return Math.round(Number(rupeesFloat) * 100);
  }
};

