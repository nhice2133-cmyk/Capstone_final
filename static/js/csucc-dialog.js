/**
 * SMART ENTRY — CSUCC Athenaeum Custom Confirmation & Alert Dialog Engine
 * Eliminates generic browser `alert()` and `confirm()` dialogs in favor of
 * institutional, theme-aligned dark green and gold modal cards.
 */

(function () {
  "use strict";

  let activeResolve = null;

  function ensureDialogDOM() {
    let overlay = document.getElementById("csuccDialogOverlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "csuccDialogOverlay";
      overlay.className = "csucc-dialog-overlay hidden";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.innerHTML = `
        <div class="csucc-dialog-card" id="csuccDialogCard">
          <div class="csucc-dialog-icon-wrap danger" id="csuccDialogIconWrap">
            <span id="csuccDialogIcon">⚠️</span>
          </div>
          <h3 class="csucc-dialog-title" id="csuccDialogTitle">Confirm Action</h3>
          <p class="csucc-dialog-message" id="csuccDialogMessage">Are you sure you want to proceed?</p>
          <div class="csucc-dialog-actions" id="csuccDialogActions">
            <button type="button" class="btn csucc-dialog-btn-cancel" id="csuccDialogCancelBtn">Cancel</button>
            <button type="button" class="btn btn-danger" id="csuccDialogConfirmBtn">Confirm</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      // Event listeners
      document.getElementById("csuccDialogCancelBtn").addEventListener("click", () => closeDialog(false));
      document.getElementById("csuccDialogConfirmBtn").addEventListener("click", () => closeDialog(true));
      
      // Close on backdrop click
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
          closeDialog(false);
        }
      });

      // Keyboard shortcuts (Escape = cancel, Enter = confirm)
      document.addEventListener("keydown", (e) => {
        if (!overlay.classList.contains("hidden")) {
          if (e.key === "Escape") {
            e.preventDefault();
            closeDialog(false);
          } else if (e.key === "Enter") {
            e.preventDefault();
            closeDialog(true);
          }
        }
      });
    }
    return overlay;
  }

  function closeDialog(result) {
    const overlay = document.getElementById("csuccDialogOverlay");
    if (overlay) {
      overlay.classList.add("hidden");
    }
    if (activeResolve) {
      const res = activeResolve;
      activeResolve = null;
      res(result);
    }
  }

  /**
   * Display a custom CSUCC confirmation modal.
   *
   * @param {Object} options
   * @param {string} options.title - Dialog heading
   * @param {string} options.message - Confirmation text
   * @param {string} [options.type='danger'] - 'danger' | 'warning' | 'info' | 'success'
   * @param {string} [options.confirmText='Confirm'] - Primary button label
   * @param {string} [options.cancelText='Cancel'] - Secondary button label
   * @param {Function} [options.onConfirm] - Callback executed on confirm
   * @param {Function} [options.onCancel] - Callback executed on cancel
   * @returns {Promise<boolean>}
   */
  window.csuccConfirm = function (options = {}) {
    ensureDialogDOM();

    const title = options.title || "Confirm Action";
    const message = options.message || "Are you sure you want to proceed?";
    const type = options.type || "danger";
    const confirmText = options.confirmText || "Confirm";
    const cancelText = options.cancelText || "Cancel";

    const titleEl = document.getElementById("csuccDialogTitle");
    const msgEl = document.getElementById("csuccDialogMessage");
    const iconWrap = document.getElementById("csuccDialogIconWrap");
    const iconEl = document.getElementById("csuccDialogIcon");
    const cancelBtn = document.getElementById("csuccDialogCancelBtn");
    const confirmBtn = document.getElementById("csuccDialogConfirmBtn");
    const overlay = document.getElementById("csuccDialogOverlay");

    titleEl.textContent = title;
    msgEl.textContent = message;

    // Icon & colors according to type
    iconWrap.className = `csucc-dialog-icon-wrap ${type}`;
    if (type === "danger") {
      iconEl.textContent = "🗑️";
      confirmBtn.className = "btn btn-danger";
    } else if (type === "warning") {
      iconEl.textContent = "⚠️";
      confirmBtn.className = "btn btn-warning";
    } else if (type === "success") {
      iconEl.textContent = "✅";
      confirmBtn.className = "btn btn-success";
    } else {
      iconEl.textContent = "ℹ️";
      confirmBtn.className = "btn btn-primary";
    }

    confirmBtn.textContent = confirmText;
    cancelBtn.textContent = cancelText;
    cancelBtn.style.display = "inline-block";

    overlay.classList.remove("hidden");
    confirmBtn.focus();

    return new Promise((resolve) => {
      activeResolve = (confirmed) => {
        if (confirmed && typeof options.onConfirm === "function") {
          options.onConfirm();
        } else if (!confirmed && typeof options.onCancel === "function") {
          options.onCancel();
        }
        resolve(confirmed);
      };
    });
  };

  /**
   * Display a custom CSUCC alert modal with a single dismiss button.
   *
   * @param {Object|string} optionsOrMessage
   * @param {string} [title='Notice']
   * @param {string} [type='info']
   * @returns {Promise<void>}
   */
  window.csuccAlert = function (optionsOrMessage, title = "Notice", type = "info") {
    ensureDialogDOM();

    let message = "";
    let buttonText = "OK";
    let alertType = type;
    let alertTitle = title;
    let onOk = null;

    if (typeof optionsOrMessage === "object" && optionsOrMessage !== null) {
      message = optionsOrMessage.message || "";
      alertTitle = optionsOrMessage.title || "Notice";
      alertType = optionsOrMessage.type || "info";
      buttonText = optionsOrMessage.buttonText || "OK";
      onOk = optionsOrMessage.onOk || null;
    } else {
      message = String(optionsOrMessage || "");
    }

    const titleEl = document.getElementById("csuccDialogTitle");
    const msgEl = document.getElementById("csuccDialogMessage");
    const iconWrap = document.getElementById("csuccDialogIconWrap");
    const iconEl = document.getElementById("csuccDialogIcon");
    const cancelBtn = document.getElementById("csuccDialogCancelBtn");
    const confirmBtn = document.getElementById("csuccDialogConfirmBtn");
    const overlay = document.getElementById("csuccDialogOverlay");

    titleEl.textContent = alertTitle;
    msgEl.textContent = message;

    iconWrap.className = `csucc-dialog-icon-wrap ${alertType}`;
    if (alertType === "danger" || alertType === "error") {
      iconEl.textContent = "⚠️";
      confirmBtn.className = "btn btn-danger";
    } else if (alertType === "warning") {
      iconEl.textContent = "⚠️";
      confirmBtn.className = "btn btn-warning";
    } else if (alertType === "success") {
      iconEl.textContent = "✅";
      confirmBtn.className = "btn btn-success";
    } else {
      iconEl.textContent = "🔔";
      confirmBtn.className = "btn btn-primary";
    }

    confirmBtn.textContent = buttonText;
    cancelBtn.style.display = "none";

    overlay.classList.remove("hidden");
    confirmBtn.focus();

    return new Promise((resolve) => {
      activeResolve = () => {
        if (typeof onOk === "function") onOk();
        resolve();
      };
    });
  };

  /**
   * Helper function for inline onsubmit:
   * onsubmit="return csuccConfirmSubmit(this, event, 'Are you sure?', 'Delete Alert', 'danger', 'Delete');"
   */
  window.csuccConfirmSubmit = function (form, event, message, title = "Confirm Action", type = "danger", btnText = "Confirm") {
    if (form && form.dataset.csuccConfirmed === "true") {
      return true;
    }
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    window.csuccConfirm({
      title: title,
      message: message,
      type: type,
      confirmText: btnText,
      onConfirm: () => {
        form.dataset.csuccConfirmed = "true";
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      }
    });
    return false;
  };

  // Intercept all forms with data-confirm automatically
  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (form && form.hasAttribute("data-confirm") && form.dataset.csuccConfirmed !== "true") {
      e.preventDefault();
      e.stopPropagation();

      const message = form.getAttribute("data-confirm");
      const title = form.getAttribute("data-confirm-title") || "Confirm Action";
      const type = form.getAttribute("data-confirm-type") || "danger";
      const btnText = form.getAttribute("data-confirm-btn") || "Confirm";

      window.csuccConfirm({
        title: title,
        message: message,
        type: type,
        confirmText: btnText,
        onConfirm: () => {
          form.dataset.csuccConfirmed = "true";
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
          } else {
            form.submit();
          }
        }
      });
      return false;
    }
  }, true);

  // Modern override for window.alert to automatically use the CSUCC modal
  const _originalAlert = window.alert;
  window.alert = function (message) {
    return window.csuccAlert({
      title: "Notice",
      message: String(message),
      type: "info",
      buttonText: "OK"
    });
  };

  // Prevent any native browser confirm popup ("localhost:5000 says")
  window.confirm = function (message) {
    console.warn("Native confirm() call intercepted by CSUCC Dialog Engine:", message);
    return false;
  };

})();

