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

  function initWatchPlayer() {
    var video = document.getElementById('watch-video');
    if (!video) return;

    var loading = document.getElementById('player-loading');
    var playBtn = document.getElementById('player-play');
    var backBtn = document.getElementById('player-back');
    var fwdBtn = document.getElementById('player-forward');
    var progress = document.getElementById('player-progress');
    var curTimeEl = document.getElementById('player-current');
    var durTimeEl = document.getElementById('player-duration');
    var tapLeft = document.getElementById('tap-left');
    var tapRight = document.getElementById('tap-right');
    var hoverTimeEl = document.getElementById('player-hover-time');
    var SEEK_SECONDS = 10;
    var isCoarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;

    function formatTime(totalSeconds) {
      totalSeconds = totalSeconds || 0;
      var minutes = Math.floor(totalSeconds / 60);
      var seconds = Math.floor(totalSeconds % 60);
      if (seconds < 10) seconds = '0' + seconds;
      return minutes + ':' + seconds;
    }

    function showLoading(show) {
      if (!loading) return;
      if (show) {
        loading.classList.add('active');
      } else {
        loading.classList.remove('active');
      }
    }

    function updateTime() {
      if (!video.duration) return;
      if (curTimeEl) curTimeEl.textContent = formatTime(video.currentTime);
      if (durTimeEl) durTimeEl.textContent = formatTime(video.duration);
      if (progress) {
        var percent = (video.currentTime / video.duration) * 100;
        progress.value = isFinite(percent) ? percent : 0;
      }
    }

    function updatePlayIcon() {
      if (!playBtn) return;
      playBtn.textContent = video.paused ? '▶' : '⏸';
    }

    function togglePlay() {
      if (video.paused) {
        video.play();
      } else {
        video.pause();
      }
      updatePlayIcon();
    }

    function seekRelative(delta) {
      if (!video.duration) return;
      var target = video.currentTime + delta;
      if (target < 0) target = 0;
      if (target > video.duration) target = video.duration;
      video.currentTime = target;
      updateTime();
    }

    video.addEventListener('loadedmetadata', function () {
      if (durTimeEl) durTimeEl.textContent = formatTime(video.duration);
    });

    video.addEventListener('timeupdate', function () {
      updateTime();
    });

    video.addEventListener('waiting', function () {
      showLoading(true);
    });

    video.addEventListener('playing', function () {
      showLoading(false);
      updatePlayIcon();
    });

    video.addEventListener('canplay', function () {
      showLoading(false);
    });

    if (playBtn) {
      playBtn.addEventListener('click', function () {
        togglePlay();
      });
    }

    if (backBtn) {
      backBtn.addEventListener('click', function () {
        seekRelative(-SEEK_SECONDS);
      });
    }

    if (fwdBtn) {
      fwdBtn.addEventListener('click', function () {
        seekRelative(SEEK_SECONDS);
      });
    }

    if (progress) {
      progress.addEventListener('input', function () {
        if (!video.duration) return;
        var percent = parseFloat(progress.value) || 0;
        var target = (percent / 100) * video.duration;
        if (target < 0) target = 0;
        if (target > video.duration) target = video.duration;
        video.currentTime = target;
      });
    }

    // Desktop-only hover preview on timeline
    if (progress && hoverTimeEl && !isCoarse) {
      progress.addEventListener('mousemove', function (e) {
        if (!video.duration) return;
        var rect = progress.getBoundingClientRect();
        var x = e.clientX - rect.left;
        if (x < 0) x = 0;
        if (x > rect.width) x = rect.width;
        var ratio = rect.width ? x / rect.width : 0;
        var seconds = video.duration * ratio;
        hoverTimeEl.textContent = formatTime(seconds);
        hoverTimeEl.style.left = (ratio * 100) + '%';
        hoverTimeEl.classList.add('visible');
      });

      progress.addEventListener('mouseleave', function () {
        hoverTimeEl.classList.remove('visible');
      });
    }

    // Keyboard controls (desktop)
    window.addEventListener('keydown', function (e) {
      var tag = e.target && e.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        seekRelative(SEEK_SECONDS);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        seekRelative(-SEEK_SECONDS);
      }
    });

    // Double-tap controls (mobile / touch devices)
    function setupDoubleTap(zoneEl, delta) {
      if (!zoneEl || !isCoarse) return;
      var lastTap = 0;
      zoneEl.addEventListener('click', function () {
        var now = Date.now();
        if (now - lastTap < 300) {
          // double tap
          seekRelative(delta);
          zoneEl.classList.add('active');
          setTimeout(function () {
            zoneEl.classList.remove('active');
          }, 200);
        }
        lastTap = now;
      });
    }

    setupDoubleTap(tapLeft, -SEEK_SECONDS);
    setupDoubleTap(tapRight, SEEK_SECONDS);

    // Initial state
    showLoading(true);
    updatePlayIcon();
  }

  function initThemeSwitcher() {
    var themeBtn = document.getElementById('themeSettingsBtn');
    var themeModal = document.getElementById('themeModal');
    var themeOverlay = document.getElementById('themeModalOverlay');
    var closeBtn = document.getElementById('closeThemeModal');
    var swatches = document.querySelectorAll('.theme-swatch');

    if (!themeBtn || !themeModal) return;

    var currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    
    // Highlight active swatch on load
    swatches.forEach(function(btn) {
      if (btn.getAttribute('data-set-theme') === currentTheme) {
        btn.classList.add('active');
      }
    });

    function openModal() {
      themeModal.classList.add('active');
      themeOverlay.classList.add('active');
    }

    function closeModal() {
      themeModal.classList.remove('active');
      themeOverlay.classList.remove('active');
    }

    function setTheme(themeName) {
      // Temporarily add transition class to body
      document.body.classList.add('theme-transition');
      
      document.documentElement.setAttribute('data-theme', themeName);
      localStorage.setItem('videohub_theme', themeName);

      swatches.forEach(function(btn) {
        if (btn.getAttribute('data-set-theme') === themeName) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // Remove transition class after animation completes (matches CSS 0.4s)
      setTimeout(function() {
        document.body.classList.remove('theme-transition');
      }, 400);
      
      closeModal();
    }

    themeBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    themeOverlay.addEventListener('click', closeModal);

    swatches.forEach(function(btn) {
      btn.addEventListener('click', function() {
        setTheme(this.getAttribute('data-set-theme'));
      });
    });
  }

  // Optional: page transition fade
  document.addEventListener('DOMContentLoaded', function () {
    readFlash();
    initThemeSwitcher();
    document.body.classList.add('loaded');
    if (document.body.classList.contains('page-watch')) {
      initWatchPlayer();
    }
  });

  // Expose toast for use in templates if needed
  window.VideoHub = window.VideoHub || {};
  window.VideoHub.toast = toast;
})();
