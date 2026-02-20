/**
 * VideoHub - Toasts, flash messages, smooth behavior
 */

(function () {
  'use strict';

  // Show toast notification
  function toast(message, type) {
    type = type || 'info';
    var container = document.getElementById('toast-container');
    if (!container) return;
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    el.setAttribute('role', 'alert');
    el.textContent = message;
    container.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transform = 'translateX(20px)';
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 300);
    }, 4000);
  }

  // Read flash messages from server-rendered data and show toasts
  function readFlash() {
    var flashes = document.querySelectorAll('[data-flash]');
    flashes.forEach(function (node) {
      var msg = node.getAttribute('data-flash');
      var type = node.getAttribute('data-flash-type') || 'info';
      if (msg) toast(msg, type);
      node.remove();
    });
  }

  // Optional: page transition fade
  document.addEventListener('DOMContentLoaded', function () {
    readFlash();
    document.body.classList.add('loaded');
  });

  // Expose toast for use in templates if needed
  window.VideoHub = window.VideoHub || {};
  window.VideoHub.toast = toast;
})();
