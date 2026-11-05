/**
 * ui.js — User Interface Helpers: Toasts, Modals, PIN Prompts, and Sidebar Toggle
 */

const ui = {
  /**
   * Display floating toast notification
   * @param {string} message
   * @param {"success"|"error"|"warning"|"info"} type
   */
  toast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    const icons = {
      success: "✓",
      error: "✕",
      warning: "⚠",
      info: "ℹ"
    };

    toast.innerHTML = `
      <span style="font-weight: bold; font-size: 1.1rem;">${icons[type] || "•"}</span>
      <div style="flex: 1;">${auth.escapeHTML(message)}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  /**
   * Prompts user for their 4-digit transaction PIN inside a clean modal
   * @param {Object} options { title, description }
   * @param {Function} onConfirm Callback receiving the 4-digit PIN string
   */
  promptPin(options = {}, onConfirm) {
    const existing = document.getElementById("pin-modal-backdrop");
    if (existing) existing.remove();

    const title = options.title || "Transaction PIN Required";
    const desc = options.description || "Enter your 4-digit security PIN to authorize this action.";

    const backdrop = document.createElement("div");
    backdrop.id = "pin-modal-backdrop";
    backdrop.className = "modal-backdrop active";

    backdrop.innerHTML = `
      <div class="modal-card">
        <div class="modal-header">
          <h3>${auth.escapeHTML(title)}</h3>
          <button class="modal-close-btn" id="pin-modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <p style="font-size: 0.9rem; color: #64748b; margin-bottom: 16px;">${auth.escapeHTML(desc)}</p>
          <div class="form-group">
            <label class="form-label">4-Digit Security PIN</label>
            <input type="password" id="modal-pin-input" class="form-control" maxlength="4" placeholder="••••" 
                   style="text-align: center; font-size: 1.5rem; letter-spacing: 0.5em;" autofocus />
            <div id="pin-modal-error" style="color: #ef4444; font-size: 0.8rem; margin-top: 6px; display: none;"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline" id="pin-modal-cancel">Cancel</button>
          <button type="button" class="btn btn-primary" id="pin-modal-submit">Confirm & Proceed</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);

    const input = document.getElementById("modal-pin-input");
    const errorEl = document.getElementById("pin-modal-error");
    const closeBtn = document.getElementById("pin-modal-close");
    const cancelBtn = document.getElementById("pin-modal-cancel");
    const submitBtn = document.getElementById("pin-modal-submit");

    const cleanup = () => backdrop.remove();

    closeBtn.onclick = cleanup;
    cancelBtn.onclick = cleanup;

    const handleSubmit = () => {
      const pin = input.value.trim();
      if (!/^\d{4}$/.test(pin)) {
        errorEl.textContent = "PIN must be exactly 4 digits.";
        errorEl.style.display = "block";
        input.focus();
        return;
      }
      cleanup();
      if (typeof onConfirm === "function") {
        onConfirm(pin);
      }
    };

    submitBtn.onclick = handleSubmit;
    input.onkeydown = (e) => {
      if (e.key === "Enter") handleSubmit();
      if (e.key === "Escape") cleanup();
    };
    input.focus();
  },

  /**
   * Generic Confirmation Modal Dialog
   */
  confirm(options = {}, onConfirm) {
    const existing = document.getElementById("confirm-modal-backdrop");
    if (existing) existing.remove();

    const title = options.title || "Confirm Action";
    const msg = options.message || "Are you sure you want to proceed?";
    const confirmBtnText = options.confirmText || "Confirm";
    const isDanger = options.danger || false;

    const backdrop = document.createElement("div");
    backdrop.id = "confirm-modal-backdrop";
    backdrop.className = "modal-backdrop active";

    backdrop.innerHTML = `
      <div class="modal-card">
        <div class="modal-header" style="${isDanger ? 'background: #dc2626;' : ''}">
          <h3 style="color: #ffffff;">${auth.escapeHTML(title)}</h3>
          <button class="modal-close-btn" id="confirm-modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <p style="font-size: 0.95rem; color: #334155;">${auth.escapeHTML(msg)}</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline" id="confirm-modal-cancel">Cancel</button>
          <button type="button" class="btn ${isDanger ? 'btn-danger' : 'btn-primary'}" id="confirm-modal-ok">${auth.escapeHTML(confirmBtnText)}</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);

    const cleanup = () => backdrop.remove();
    document.getElementById("confirm-modal-close").onclick = cleanup;
    document.getElementById("confirm-modal-cancel").onclick = cleanup;
    document.getElementById("confirm-modal-ok").onclick = () => {
      cleanup();
      if (typeof onConfirm === "function") onConfirm();
    };
  },

  /**
   * Automatically initializes dynamic Show/Hide buttons for all password & PIN fields.
   * Button remains hidden until the user begins typing in the box.
   */
  initPasswordToggles() {
    document.querySelectorAll("input[type='password'], input[data-password-toggle='true']").forEach(input => {
      if (input.dataset.pwToggleInit) return;
      input.dataset.pwToggleInit = "true";

      // Wrap input in .password-wrapper if not already wrapped
      let wrapper = input.closest(".password-wrapper");
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.className = "password-wrapper";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
      }

      // Check if button already exists in wrapper
      let btn = wrapper.querySelector(".password-toggle-btn");
      if (!btn) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "password-toggle-btn";
        btn.tabIndex = -1;
        btn.setAttribute("aria-label", "Show password");
        btn.innerHTML = "👁️ Show";
        wrapper.appendChild(btn);
      }

      // Dynamic appearance: only display when text is typed in the box
      const updateVisibility = () => {
        if (input.value && input.value.length > 0) {
          btn.style.display = "inline-flex";
        } else {
          btn.style.display = "none";
          input.type = "password";
          btn.innerHTML = "👁️ Show";
          btn.setAttribute("aria-label", "Show password");
        }
      };

      input.addEventListener("input", updateVisibility);
      updateVisibility();

      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        btn.innerHTML = isPassword ? "🙈 Hide" : "👁️ Show";
        btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
        input.focus();
      });
    });
  },

  /**
   * Initialize layout behaviors (Sidebar hamburger for mobile, user pill)
   */
  initLayout() {
    const hamburger = document.querySelector(".hamburger-btn");
    const sidebar = document.querySelector(".sidebar");
    if (hamburger && sidebar) {
      hamburger.onclick = () => {
        sidebar.classList.toggle("mobile-open");
      };
    }

    // Set user info if on an authenticated page
    const user = auth.getUser();
    const userBadgeName = document.getElementById("topbar-username");
    const userAvatar = document.getElementById("topbar-avatar");
    if (user && userBadgeName) {
      userBadgeName.textContent = user.name || "Customer";
      if (userAvatar) {
        userAvatar.textContent = (user.name || "C").charAt(0).toUpperCase();
      }
    }

    // Initialize all password toggles
    this.initPasswordToggles();
  }
};

document.addEventListener("DOMContentLoaded", () => {
  ui.initLayout();
});

