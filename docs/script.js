// script.js – ExpatScore.de (Production v3.2 — Unified)
'use strict';

/* ============================================================
   1. COOKIE CONSENT
   ============================================================ */
function openModal(id)  { var m = document.getElementById('modal-' + id); if (m) m.classList.add('open'); document.body.style.overflow = 'hidden'; }
function closeModal(id) { var m = document.getElementById('modal-' + id); if (m) m.classList.remove('open'); document.body.style.overflow = ''; }
function hideBanner()   { var b = document.getElementById('cookie-banner'); if (b) b.classList.remove('visible'); }

function acceptCookies() {
  localStorage.setItem('cookieConsent', 'all');
  hideBanner(); closeModal('cookie-settings');
  updateToggles({ analytics: true, affiliate: true });
}

function declineCookies() {
  localStorage.setItem('cookieConsent', 'necessary');
  hideBanner(); closeModal('cookie-settings');
  updateToggles({ analytics: false, affiliate: false });
}

function saveGranularCookies() {
  var a = document.getElementById('toggle-analytics');
  var f = document.getElementById('toggle-affiliate');
  var prefs = { necessary: true, analytics: a ? a.checked : false, affiliate: f ? f.checked : false };
  localStorage.setItem('cookieConsent', JSON.stringify(prefs));
  hideBanner(); closeModal('cookie-settings');
}

function updateToggles(prefs) {
  var a = document.getElementById('toggle-analytics');
  var f = document.getElementById('toggle-affiliate');
  if (a) a.checked = !!prefs.analytics;
  if (f) f.checked = !!prefs.affiliate;
}

/* ============================================================
   2. AFFILIATE CLICK TRACKING
   ============================================================ */
function trackClick(partner) {
  var stored = localStorage.getItem('cookieConsent');
  if (!stored) return;
  var allowed = false;
  if (stored === 'all') { allowed = true; }
  else {
    try { var p = JSON.parse(stored); allowed = !!p.affiliate; } catch(e) {}
  }
  if (!allowed) return;
  try {
    if (typeof gtag !== 'undefined') gtag('event', 'affiliate_click', { event_category: 'affiliate', event_label: partner });
    if (typeof dataLayer !== 'undefined') dataLayer.push({ event: 'affiliate_click', partner: partner });
  } catch(e) {}
}

/* ============================================================
   3. INIT ON DOM READY
   ============================================================ */
document.addEventListener('DOMContentLoaded', function() {
  // Cookie banner: show if no consent stored
  var consent = localStorage.getItem('cookieConsent');
  if (!consent) {
    setTimeout(function() { var b = document.getElementById('cookie-banner'); if (b) b.classList.add('visible'); }, 1200);
  } else {
    hideBanner();
    // Restore toggle states
    if (consent === 'all') {
      updateToggles({ analytics: true, affiliate: true });
    } else if (consent === 'necessary') {
      updateToggles({ analytics: false, affiliate: false });
    } else {
      try { updateToggles(JSON.parse(consent)); } catch(e) {}
    }
  }

  // Mobile nav toggle
  var nt = document.getElementById('navToggle'), nl = document.getElementById('navLinks');
  if (nt && nl) nt.addEventListener('click', function() { nl.classList.toggle('open'); });

  // Sticky header
  var header = document.querySelector('.global-header');
  if (header) {
    window.addEventListener('scroll', function() {
      header.classList.toggle('sticky', window.scrollY > 50);
    });
  }

  // Progress bar
  window.addEventListener('scroll', function() {
    var el = document.getElementById('progressBar'); if (!el) return;
    var h = document.body.scrollHeight - window.innerHeight;
    if (h > 0) el.style.width = Math.min(window.scrollY / h * 100, 100) + '%';
  });

  // Current date
  var dateEl = document.getElementById('current-date');
  if (dateEl) {
    var now = new Date();
    var months = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
    dateEl.textContent = months[now.getMonth()] + ' ' + now.getFullYear();
  }

  // Modal backdrop close
  document.querySelectorAll('.modal-overlay').forEach(function(overlay) {
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { overlay.classList.remove('open'); document.body.style.overflow = ''; }
    });
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.open').forEach(function(m) { m.classList.remove('open'); });
      document.body.style.overflow = '';
    }
  });

  // Reveal animations
  if ('IntersectionObserver' in window) {
    var obs = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) { entry.target.classList.add('visible'); obs.unobserve(entry.target); }
      });
    }, { threshold: 0.10 });
    document.querySelectorAll('.reveal, .trap-card, .step-card').forEach(function(el) { obs.observe(el); });
  } else {
    document.querySelectorAll('.reveal, .trap-card, .step-card').forEach(function(el) { el.classList.add('visible'); });
  }
});
