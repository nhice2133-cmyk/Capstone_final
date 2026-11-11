/**
 * SMART ENTRY — Dashboard JS
 * Minimal global utilities used across admin pages.
 */

// Auto-dismiss flash messages after 5 seconds
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach(el => {
    setTimeout(() => el.remove(), 5000);
  });
});
