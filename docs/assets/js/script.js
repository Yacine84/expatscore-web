// script.js – ExpatScore.de (Production Ready)

'use strict';

// ----------------------------------------------------------------------
// 1. COOKIE CONSENT MANAGEMENT
// ----------------------------------------------------------------------
function acceptCookies() {
  const prefs = { necessary: true, analytics: true, affiliate: true };
  localStorage.setItem('cookieConsent', JSON.stringify(prefs));
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.add('hidden');
    banner.style.display = 'none';
  }
  updateToggleSwitches(prefs);
}

function declineCookies() {
  const prefs = { necessary: true, analytics: false, affiliate: false };
  localStorage.setItem('cookieConsent', JSON.stringify(prefs));
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.add('hidden');
    banner.style.display = 'none';
  }
  updateToggleSwitches(prefs);
}

function saveGranularCookies() {
  const analytics = document.getElementById('toggle-analytics');
  const affiliate = document.getElementById('toggle-affiliate');
  const prefs = {
    necessary: true,
    analytics: analytics ? analytics.checked : false,
    affiliate: affiliate ? affiliate.checked : false
  };
  localStorage.setItem('cookieConsent', JSON.stringify(prefs));
  closeModal('cookie-settings');
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.add('hidden');
    banner.style.display = 'none';
  }
}

function updateToggleSwitches(prefs) {
  const ta = document.getElementById('toggle-analytics');
  const tf = document.getElementById('toggle-affiliate');
  if (ta) ta.checked = !!prefs.analytics;
  if (tf) tf.checked = !!prefs.affiliate;
}

// ----------------------------------------------------------------------
// 2. MODAL SYSTEM
// ----------------------------------------------------------------------
function openModal(name) {
  const el = document.getElementById('modal-' + name);
  if (el) {
    el.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(name) {
  const el = document.getElementById('modal-' + name);
  if (el) {
    el.classList.remove('active');
    document.body.style.overflow = '';
  }
}

// ----------------------------------------------------------------------
// 3. AFFILIATE CLICK TRACKING
// ----------------------------------------------------------------------
function trackClick(partner) {
  const stored = localStorage.getItem('cookieConsent');
  if (stored) {
    try {
      const prefs = JSON.parse(stored);
      if (!prefs.affiliate) return;
    } catch(e) { return; }
  } else {
    return;
  }

  try {
    if (typeof gtag !== 'undefined') {
      gtag('event', 'affiliate_click', { event_category: 'affiliate', event_label: partner });
    }
    if (typeof dataLayer !== 'undefined') {
      dataLayer.push({ event: 'affiliate_click', partner: partner });
    }
  } catch(e) {}
}

// ----------------------------------------------------------------------
// 4. INITIALISATIONS (DOMContentLoaded)
// ----------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', function() {
  // Cookie banner initialisation
  const storedConsent = localStorage.getItem('cookieConsent');
  if (storedConsent) {
    const banner = document.getElementById('cookie-banner');
    if (banner) banner.classList.add('hidden');
    try {
      const prefs = JSON.parse(storedConsent);
      updateToggleSwitches(prefs);
    } catch(e) {}
  }

  // Set current month/year in #current-date
  const dateEl = document.getElementById('current-date');
  if (dateEl) {
    const now = new Date();
    const months = ['Januar','Februar','März','April','Mai','Juni',
                    'Juli','August','September','Oktober','November','Dezember'];
    dateEl.textContent = months[now.getMonth()] + ' ' + now.getFullYear();
  }

  // Sticky header on scroll
  const header = document.querySelector('.global-header');
  if (header) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 50) {
        header.classList.add('sticky');
      } else {
        header.classList.remove('sticky');
      }
    });
  }

  // Affiliate links: force target="_blank" and noopener
  const affiliateLinks = document.querySelectorAll('.cta-blue, .cta-green, .cta-gold, .card-cta');
  affiliateLinks.forEach(function(link) {
    link.setAttribute('target', '_blank');
    link.setAttribute('rel', 'noopener noreferrer');
  });

  // Modal event listeners
  document.querySelectorAll('.modal-overlay').forEach(function(overlay) {
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(function(modal) {
        modal.classList.remove('active');
      });
      document.body.style.overflow = '';
    }
  });

  // IntersectionObserver for reveal animations
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.10 });

    document.querySelectorAll('.reveal, .trap-card, .step-card').forEach(function(el) {
      observer.observe(el);
    });
  } else {
    // Fallback for browsers without IntersectionObserver
    document.querySelectorAll('.reveal, .trap-card, .step-card').forEach(function(el) {
      el.classList.add('visible');
    });
  }
});