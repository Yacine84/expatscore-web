/* ============================================================
   ExpatScore.de — script.js
   SCHUFA Score Simulator 2026 + Blocked Account Calculator
   Vanilla JS (ES6+) — No external dependencies
   ============================================================ */

'use strict';

/* ============================================================
   QUESTION DATA
   ============================================================ */
const QUESTIONS = [
  {
    id: 'duration',
    text: 'Wie lange lebst du bereits in Deutschland?',
    hint: 'Die Aufenthaltsdauer ist einer der wichtigsten SCHUFA-Faktoren. Je länger du hier lebst, desto mehr Daten hat die SCHUFA über dich — auch wenn diese ausnahmslos positiv sind.',
    options: [
      { label: 'Gerade angekommen (unter 3 Monate)', sub: 'Noch keine SCHUFA-Daten vorhanden',        badge: null,      score: 0,   key: 'new'  },
      { label: '3 bis 12 Monate',                   sub: 'Frühphase — History-Aufbau beginnt',       badge: 'building',score: 60,  key: 'mid'  },
      { label: '1 bis 3 Jahre',                     sub: 'Etabliert — solide Datenspur',             badge: null,      score: 130, key: 'est'  },
      { label: 'Mehr als 3 Jahre',                  sub: 'Langfristig — starkes Historienpotenzial', badge: 'best',    score: 200, key: 'long' }
    ]
  },
  {
    id: 'employment',
    text: 'Was ist dein aktueller Beschäftigungsstatus in Deutschland?',
    hint: 'Beschäftigungsstabilität signalisiert finanzielle Zuverlässigkeit. Banken und SCHUFA gewichten dies stark — ein unbefristeter Vertrag ist der Goldstandard.',
    options: [
      { label: 'Vollzeitbeschäftigt (unbefristeter Vertrag)', sub: 'Stärkstes Beschäftigungssignal',      badge: 'best', score: 120, key: 'employed'  },
      { label: 'Selbständig oder Freiberufler',               sub: 'Variables Einkommen — handhabbar',    badge: null,   score: 75,  key: 'freelance' },
      { label: 'Student (immatrikuliert)',                    sub: 'Gültiger Aufenthaltszweck',           badge: null,   score: 55,  key: 'student'   },
      { label: 'Aktuell auf Jobsuche',                       sub: 'Vorübergehend — blockiert keine Konten', badge: null, score: 25,  key: 'seeking'   }
    ]
  },
  {
    id: 'anmeldung',
    text: 'Bist du offiziell an einer deutschen Adresse gemeldet? (Anmeldung)',
    hint: 'Die Anmeldung ist deine offizielle Adressregistrierung beim Bürgeramt. Gesetzlich innerhalb von 14 Tagen nach Einzug erforderlich — nahezu alle deutschen Banken verlangen sie.',
    options: [
      { label: 'Ja — vollständig angemeldet',          sub: 'Von allen deutschen Banken gefordert',    badge: 'best', score: 80, key: 'yes'     },
      { label: 'In Bearbeitung — Termin vorhanden',    sub: 'Manche Banken akzeptieren dies temporär', badge: null,   score: 30, key: 'process' },
      { label: 'Noch nicht registriert',               sub: 'Dringend nachholen',                      badge: 'risk', score: 0,  key: 'no'      }
    ]
  },
  {
    id: 'accounts',
    text: 'Hast du derzeit deutsche Bankkonten?',
    hint: 'Ein aktives deutsches Bankkonto ist der schnellste Weg, SCHUFA-History aufzubauen. Selbst ein kostenloser N26-Account zählt — jeder offene Monat ist ein Monat positiver Historie.',
    options: [
      { label: 'Keine deutschen Bankkonten',               sub: 'SCHUFA hat keinerlei Banking-Daten zu dir', badge: null,   score: 0,   key: 'none'    },
      { label: 'Ein Konto, kürzlich eröffnet (< 1 Jahr)', sub: 'Aufbau hat begonnen',                       badge: null,   score: 60,  key: 'one_new' },
      { label: 'Ein Konto, über 12 Monate alt',           sub: 'Solide Banking-History im Aufbau',          badge: null,   score: 100, key: 'one_old' },
      { label: 'Zwei oder mehr deutsche Konten',          sub: 'Starker Banking-Fußabdruck',                badge: 'best', score: 130, key: 'multi'   }
    ]
  },
  {
    id: 'payments',
    text: 'Hast du in Deutschland jemals eine Zahlung versäumt?',
    hint: 'Versäumte Zahlungen — Miete, Strom, Handyvertrag, Streaming-Abos — sind die häufigste Ursache für SCHUFA-Schäden. Ein ungelöster Eintrag kann deinen Score bis zu 3 Jahre erheblich belasten.',
    options: [
      { label: 'Nie — alle Zahlungen pünktlich',          sub: 'Ideales Zahlungsverhalten',              badge: 'best', score: 120, key: 'perfect' },
      { label: 'Einmal oder zweimal — aber nachgezahlt',  sub: 'Geringer Einfluss, wenn schnell geklärt', badge: null,   score: 40,  key: 'minor'   },
      { label: 'Ja — und noch ungelöst',                  sub: 'Erhebliche negative Auswirkung',          badge: 'risk', score: -80, key: 'bad'     },
      { label: 'Nicht zutreffend — zu neu hier',          sub: 'Noch keine Zahlungshistorie',             badge: null,   score: 50,  key: 'na'      }
    ]
  },
  {
    id: 'credit',
    text: 'Wie sieht deine Kreditgeschichte in Deutschland aus?',
    hint: 'Verantwortungsvoll verwalteter Kredit — eine monatlich vollständig bezahlte Kreditkarte oder ein Ratenkredit — verbessert deinen SCHUFA-Score aktiv. Kein Kredit ist neutral, nicht positiv.',
    options: [
      { label: 'Kein Kredit — komplett neu',                   sub: 'Neutraler Ausgangspunkt',          badge: null,   score: 30,  key: 'none'      },
      { label: 'Kreditkarte — immer pünktlich bezahlt',        sub: 'Exzellentes positives Signal',     badge: 'best', score: 110, key: 'cc_good'   },
      { label: 'Ratenkredit — immer pünktlich bezahlt',        sub: 'Starkes positives Signal',         badge: 'best', score: 120, key: 'loan_good' },
      { label: 'Kredit vorhanden — aber einige Verzögerungen', sub: 'Negativer Einfluss auf Score',     badge: 'risk', score: -20, key: 'late'      }
    ]
  }
];

/* ============================================================
   BANK DATABASE
   ============================================================ */
const BANKS = {
  n26: {
    name: 'N26 Standard',
    tagline: 'Deutschlands expat-freundlichste Digitalbank',
    url: 'https://n26.com/r/expatscore',
    cta: 'N26 kostenlos eröffnen',
    ctaStyle: 'teal-cta',
    fee: 'Kostenlos',
    time: '8 Min Setup',
    schufa: 'Kein SCHUFA-Check',
    features: ['Kein SCHUFA-Check', 'VideoIdent — komplett online', 'Englische App', 'Kostenlose Mastercard', 'Sofortige Kontonummer']
  },
  vivid: {
    name: 'Vivid Money',
    tagline: 'Mehrwährungs-Konto für internationale Fachkräfte',
    url: '#vivid-affiliate',
    cta: 'Vivid kostenlos eröffnen',
    ctaStyle: '',
    fee: 'Kostenloser Tarif',
    time: '10 Min Setup',
    schufa: 'Kein SCHUFA-Check',
    features: ['Kein SCHUFA-Check', 'Mehrwährungs-Pockets', 'Cashback auf Einkäufe', 'Englischer Support', 'EU + Nicht-EU akzeptiert']
  },
  bunq: {
    name: 'Bunq',
    tagline: 'International-first Bank für mobile Menschen',
    url: '#bunq-affiliate',
    cta: 'Bunq kostenlos testen',
    ctaStyle: '',
    fee: '3 Monate gratis',
    time: '5 Min Setup',
    schufa: 'Kein SCHUFA erforderlich',
    features: ['Kein SCHUFA-Check', '100% online Eröffnung', 'Keine Anmeldung für Antrag', 'EU-Einlagensicherung', 'Mehrsprachige App']
  },
  dkb: {
    name: 'DKB',
    tagline: 'Deutschlands vertrauenswürdigste Onlinebank für etablierte Expats',
    url: '#dkb-affiliate',
    cta: 'DKB beantragen',
    ctaStyle: 'teal-cta',
    fee: 'Kostenlos (Bedingungen)',
    time: '3–5 Tage',
    schufa: 'Soft SCHUFA-Prüfung',
    features: ['Kostenlos ab €700/Monat', 'VISA weltweit akzeptiert', 'Exzellenter Service', 'Deutsche IBAN sofort', 'VideoIdent oder PostIdent']
  },
  c24: {
    name: 'C24 Bank',
    tagline: 'Neue Generation — toleranter als traditionelle deutsche Banken',
    url: '#c24-affiliate',
    cta: 'C24 Konto eröffnen',
    ctaStyle: '',
    fee: 'Kostenloses Basiskonto',
    time: 'Tageszulassung',
    schufa: 'Basis SCHUFA-Prüfung',
    features: ['Tolerante SCHUFA-Anforderungen', 'Vollständig digital', 'Englische Oberfläche', 'Deutsche IBAN sofort', 'Kostenlose Visa-Debitkarte']
  },
  ing: {
    name: 'ING Deutschland',
    tagline: 'Top-bewertetes kostenloses deutsches Konto — für etablierte Expats',
    url: '#ing-affiliate',
    cta: 'ING beantragen',
    ctaStyle: 'teal-cta',
    fee: 'Kostenlos für immer',
    time: '3–7 Tage',
    schufa: 'Vollständige SCHUFA-Prüfung',
    features: ['Nie monatliche Gebühren', 'Höchste Kundenzufriedenheit', '€1.500/Monat Einkommensanf.', 'Sofortiger Kreditkarten-Upgrade', 'Vollständiges Banking-Paket']
  },
  comdirect: {
    name: 'Comdirect',
    tagline: 'Vollservice-Bank für Expats beim langfristigen Vermögensaufbau',
    url: '#comdirect-affiliate',
    cta: 'Comdirect eröffnen',
    ctaStyle: '',
    fee: 'Kostenlos mit Aktivität',
    time: '5–7 Tage',
    schufa: 'Vollständige SCHUFA-Prüfung',
    features: ['Kostenlos mit 2 Transaktionen/Mo.', 'Spar- und ETF-Integration', 'SCHUFA-aufbauend', 'Visa und Mastercard', 'Starke Mobile-App']
  },
  commerzbank: {
    name: 'Commerzbank',
    tagline: 'Zweitgrößte deutsche Bank — vollständiger Premium-Service',
    url: '#commerzbank-affiliate',
    cta: 'Commerzbank eröffnen',
    ctaStyle: 'teal-cta',
    fee: '€9,90/Mo (oder gratis)',
    time: '2–5 Tage',
    schufa: 'Vollständige SCHUFA-Prüfung',
    features: ['Bundesweites Filialnetz', 'Premium-Kreditkarten', 'Hypothekenzugang', 'Geschäftskonto verfügbar', 'Vollständiges Banking-Paket']
  }
};

/* ============================================================
   STATE
   ============================================================ */
let currentStep = 0;
let answers = {};
let selectedOptionIndex = -1;
let scoreResult = null;

/* ============================================================
   PROGRESS BAR (page scroll)
   ============================================================ */
function initProgressBar() {
  const bar = document.getElementById('progressBar');
  if (!bar) return;
  window.addEventListener('scroll', () => {
    const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    bar.style.width = scrollHeight > 0 ? `${(scrollTop / scrollHeight) * 100}%` : '0%';
  }, { passive: true });
}

/* ============================================================
   FAQ ACCORDION
   ============================================================ */
function toggleFaq(btn) {
  const answer = btn.nextElementSibling;
  const icon = btn.querySelector('.faq-icon');
  const isOpen = btn.getAttribute('aria-expanded') === 'true';

  // close all others
  document.querySelectorAll('.faq-q[aria-expanded="true"]').forEach(b => {
    if (b !== btn) {
      b.setAttribute('aria-expanded', 'false');
      b.nextElementSibling.style.maxHeight = null;
      const ic = b.querySelector('.faq-icon');
      if (ic) ic.textContent = '+';
    }
  });

  if (isOpen) {
    btn.setAttribute('aria-expanded', 'false');
    answer.style.maxHeight = null;
    if (icon) icon.textContent = '+';
  } else {
    btn.setAttribute('aria-expanded', 'true');
    answer.style.maxHeight = answer.scrollHeight + 'px';
    if (icon) icon.textContent = '−';
  }
}

/* ============================================================
   COOKIE BANNER
   ============================================================ */
function initCookieBanner() {
  if (localStorage.getItem('cookieConsent')) return;
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    setTimeout(() => banner.classList.add('visible'), 1200);
  }
}

function acceptCookies() {
  localStorage.setItem('cookieConsent', 'all');
  hideCookieBanner();
}

function declineCookies() {
  localStorage.setItem('cookieConsent', 'necessary');
  hideCookieBanner();
}

function saveGranularCookies() {
  const analytics = document.getElementById('toggle-analytics')?.checked;
  const affiliate = document.getElementById('toggle-affiliate')?.checked;
  localStorage.setItem('cookieConsent', JSON.stringify({ analytics, affiliate }));
  hideCookieBanner();
  closeModal('cookie-settings');
}

function hideCookieBanner() {
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.remove('visible');
    setTimeout(() => banner.style.display = 'none', 400);
  }
}

function openModal(id) {
  const modal = document.getElementById(`modal-${id}`);
  if (modal) {
    modal.classList.add('visible');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(id) {
  const modal = document.getElementById(`modal-${id}`);
  if (modal) {
    modal.classList.remove('visible');
    document.body.style.overflow = '';
  }
}

/* ============================================================
   NAV TOGGLE (mobile)
   ============================================================ */
function initNav() {
  const toggle = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (!toggle || !links) return;
  toggle.addEventListener('click', () => {
    links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', links.classList.contains('open'));
  });
  // close nav on link click (mobile)
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => links.classList.remove('open'));
  });
}

/* ============================================================
   SIMULATOR — STEP TRACKER
   ============================================================ */
function buildStepTracker() {
  const t = document.getElementById('stepTracker');
  if (!t) return;
  t.innerHTML = '';
  QUESTIONS.forEach((q, i) => {
    if (i > 0) {
      const c = document.createElement('div');
      c.className = 'step-connector';
      c.id = `conn-${i}`;
      t.appendChild(c);
    }
    const d = document.createElement('div');
    d.className = `step-dot${i === 0 ? ' active' : ''}`;
    d.id = `dot-${i}`;
    t.appendChild(d);
  });
}

function updateStepTracker(step) {
  QUESTIONS.forEach((q, i) => {
    const d = document.getElementById(`dot-${i}`);
    if (!d) return;
    d.className = 'step-dot';
    if (i < step) d.classList.add('done');
    else if (i === step) d.classList.add('active');
    if (i > 0) {
      const c = document.getElementById(`conn-${i}`);
      if (c) c.className = `step-connector${i <= step ? ' done' : ''}`;
    }
  });
  const sl = document.getElementById('stepLabel');
  if (sl) sl.textContent = `Schritt ${step + 1} von ${QUESTIONS.length}`;
  const f = document.getElementById('simProgressFill');
  if (f) f.style.width = `${((step + 1) / QUESTIONS.length * 100).toFixed(1)}%`;
}

/* ============================================================
   SIMULATOR — RENDER QUESTION
   ============================================================ */
function renderQuestion(step) {
  const q = QUESTIONS[step];
  currentStep = step;
  selectedOptionIndex = -1;

  const qNum = document.getElementById('qNumber');
  if (qNum) qNum.textContent = `Frage ${step + 1} / ${QUESTIONS.length}`;

  const qT = document.getElementById('qText');
  if (qT) qT.textContent = q.text;

  const qH = document.getElementById('qHint');
  if (qH) qH.textContent = q.hint;

  const list = document.getElementById('optionsList');
  if (!list) return;
  list.innerHTML = '';

  q.options.forEach((opt, i) => {
    const el = document.createElement('div');
    const isSelected = answers[q.id] === i;
    el.className = `sim-option${isSelected ? ' selected' : ''}`;
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-pressed', isSelected);

    const badgeHTML = opt.badge === 'best'
      ? '<span class="opt-badge badge-best">Best</span>'
      : opt.badge === 'building'
      ? '<span class="opt-badge badge-neutral">Building</span>'
      : opt.badge === 'risk'
      ? '<span class="opt-badge badge-risk">Achtung</span>'
      : '';

    el.innerHTML = `
      <div class="opt-radio"></div>
      <div class="opt-content">
        <div class="opt-label">${opt.label}</div>
        ${opt.sub ? `<div class="opt-sub">${opt.sub}</div>` : ''}
      </div>
      ${badgeHTML}
    `;

    el.addEventListener('click', () => selectOption(i));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectOption(i); }
    });

    if (isSelected) selectedOptionIndex = i;
    list.appendChild(el);
  });

  const bb = document.getElementById('backBtn');
  if (bb) bb.style.visibility = step > 0 ? 'visible' : 'hidden';

  updateNextBtn();
  updateStepTracker(step);
}

function selectOption(idx) {
  const q = QUESTIONS[currentStep];
  answers[q.id] = idx;
  selectedOptionIndex = idx;

  document.querySelectorAll('.sim-option').forEach((el, i) => {
    el.classList.toggle('selected', i === idx);
    el.setAttribute('aria-pressed', i === idx);
  });

  updateNextBtn();

  // Auto-advance after brief delay for smooth UX
  setTimeout(() => {
    if (currentStep < QUESTIONS.length - 1) {
      animateCardOut(() => { renderQuestion(currentStep + 1); animateCardIn(); });
    } else {
      startCalculation();
    }
  }, 380);
}

function updateNextBtn() {
  const btn = document.getElementById('nextBtn');
  if (!btn) return;
  btn.textContent = currentStep === QUESTIONS.length - 1 ? 'SCHUFA-Score berechnen ★' : 'Weiter →';
  btn.classList.toggle('enabled', selectedOptionIndex >= 0);
}

function goNext() {
  if (selectedOptionIndex < 0) {
    // Shake the card to prompt selection
    const card = document.getElementById('questionCard');
    if (card) {
      card.classList.add('shake');
      setTimeout(() => card.classList.remove('shake'), 500);
    }
    return;
  }
  if (currentStep < QUESTIONS.length - 1) {
    animateCardOut(() => { renderQuestion(currentStep + 1); animateCardIn(); });
  } else {
    startCalculation();
  }
}

function goBack() {
  if (currentStep > 0) {
    animateCardOut(() => { renderQuestion(currentStep - 1); animateCardIn(); });
  }
}

function animateCardOut(cb) {
  const card = document.getElementById('questionCard');
  if (!card) { cb(); return; }
  card.classList.add('leaving');
  setTimeout(() => { card.classList.remove('leaving'); cb(); }, 280);
}

function animateCardIn() {
  const card = document.getElementById('questionCard');
  if (!card) return;
  card.style.animation = 'none';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    card.style.animation = 'cardIn .4s cubic-bezier(.4,0,.2,1)';
  }));
}

/* ============================================================
   SIMULATOR — CALCULATION SCREEN
   ============================================================ */
function startCalculation() {
  const quizScreen = document.getElementById('quiz-screen');
  const calcScreen = document.getElementById('calcScreen');
  if (!quizScreen || !calcScreen) return;

  quizScreen.style.display = 'none';
  calcScreen.style.display = 'flex';

  const steps = ['cs1', 'cs2', 'cs3', 'cs4', 'cs5', 'cs6'];
  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active', 'done'); }
  });

  let idx = 0;
  function activateNext() {
    if (idx > 0) {
      const prev = document.getElementById(steps[idx - 1]);
      if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
    }
    if (idx < steps.length) {
      const cur = document.getElementById(steps[idx]);
      if (cur) cur.classList.add('active');
      idx++;
      setTimeout(activateNext, 420);
    } else {
      // Mark last step done
      const last = document.getElementById(steps[steps.length - 1]);
      if (last) { last.classList.remove('active'); last.classList.add('done'); }
      setTimeout(showResult, 500);
    }
  }
  activateNext();
}

/* ============================================================
   SCORING ENGINE
   ============================================================ */
function computeScore() {
  let raw = 0;
  const factors = {};
  const RAW_MIN = -150;
  const RAW_MAX = 770;

  QUESTIONS.forEach(q => {
    const idx = answers[q.id];
    if (idx === undefined) return;
    const opt = q.options[idx];
    const pts = opt.score;
    const maxPts = Math.max(...q.options.map(o => o.score));
    raw += pts;
    factors[q.id] = { pts, maxPts, key: opt.key };
  });

  const normalised = Math.max(0, Math.min(1000,
    Math.round((raw - RAW_MIN) / (RAW_MAX - RAW_MIN) * 1000)
  ));

  return { raw, normalised, factors };
}

function getScoreProfile(n) {
  if (n >= 880) return {
    level: 'Exzellent',
    color: '#50C878',
    desc: 'Dein SCHUFA-Profil ist in der Spitzenklasse. Deutsche Banken werden aktiv um dein Geschäft konkurrieren. Du qualifizierst dich für Kredit, Hypotheken und Premium-Konten.',
    pills: ['Top 5% in Deutschland', 'Alle Konten verfügbar', 'Hypotheken-berechtigt']
  };
  if (n >= 720) return {
    level: 'Sehr Gut',
    color: '#7DDFAA',
    desc: 'Starkes SCHUFA-Profil. Du qualifizierst dich für nahezu alle deutschen Bankkonten, die meisten Kreditkarten und viele Kredite.',
    pills: ['Meiste Kredite zugänglich', 'Kreditkarten verfügbar', 'Weiter ausbauen']
  };
  if (n >= 560) return {
    level: 'Gut',
    color: '#D4AF37',
    desc: 'Solides Fundament mit Wachstumspotenzial. Du kannst die meisten Konten eröffnen. Längere Banking-History und pünktliche Zahlungen bringen dich nach oben.',
    pills: ['Standardkonten offen', 'Etwas Kredit zugänglich', 'Wachstumsphase']
  };
  if (n >= 380) return {
    level: 'Aufbauphase',
    color: '#FBBF24',
    desc: 'Deine SCHUFA ist im Aufbau — normal für Expats, die vor 6–18 Monaten angekommen sind. Digitalbanken sind jetzt deine beste Option.',
    pills: ['Digitalbanken bevorzugt', 'Noch kein Kredit', '12-Monat-Wachstumsfenster']
  };
  if (n >= 180) return {
    level: 'Begrenzt',
    color: '#F97316',
    desc: 'Dein Profil zeigt begrenzte SCHUFA-Daten — typisch für Newcomer. Mehrere ausgezeichnete Banken arbeiten ohne SCHUFA-Prüfung.',
    pills: ['Zuerst No-SCHUFA-Banken', 'Jetzt History aufbauen', 'Verbesserung in 6–12 Mo.']
  };
  return {
    level: 'Keine SCHUFA',
    color: '#EF4444',
    desc: 'Du hast noch keine SCHUFA-Geschichte — völlig normal. SCHUFA gibt es in den meisten Ländern außerhalb Deutschlands nicht. Mehrere Banken heißen Newcomer ausdrücklich willkommen.',
    pills: ['Noch kein Eintrag', 'Perfekter Startpunkt', 'Mehrere Banken für dich']
  };
}

function getBankRecs(n, factors) {
  const dur = factors.duration?.key || '';
  const acc = factors.accounts?.key || '';

  if (n < 300 || dur === 'new' || acc === 'none') {
    return [
      { ...BANKS.n26, rank: 1, why: 'Kein SCHUFA-Check erforderlich. Eröffnet vollständig online mit VideoIdent in 8 Minuten — nur Reisepass benötigt. Jeder offene Monat baut deine SCHUFA-History auf.' },
      { ...BANKS.vivid, rank: 2, why: 'Kein SCHUFA-Check, Mehrwährungs-Pockets und Cashback. Ideal als Alltagskonto, während du über N26 SCHUFA aufbaust.' },
      { ...BANKS.bunq, rank: 3, why: '3 Monate kostenlos und keine Anmeldung für den Antrag erforderlich. Tolle Backup-Option, wenn deine Anmeldung noch in Bearbeitung ist.' }
    ];
  }
  if (n < 560) {
    return [
      { ...BANKS.n26, rank: 1, why: 'Immer noch die sicherste Genehmigung. N26 garantiert Zulassung und gibt dir eine verlässliche Basis.' },
      { ...BANKS.c24, rank: 2, why: 'Neue deutsche Bank mit den tolerantesten SCHUFA-Anforderungen ihrer Klasse. Ideal für Expats mit 3–18 Monaten Geschichte.' },
      { ...BANKS.dkb, rank: 3, why: 'Es lohnt sich, jetzt zu beantragen. DKB akzeptiert die meisten Newcomer mit Basishistorie.' }
    ];
  }
  if (n < 750) {
    return [
      { ...BANKS.dkb, rank: 1, why: 'Dein Profil qualifiziert dich jetzt für DKB — die Lieblingsbank der Expat-Community für Verlässlichkeit, kostenlose VISA und exzellenten Kundenservice.' },
      { ...BANKS.c24, rank: 2, why: 'Ergänzt DKB perfekt — sofortiger Cashback und Visa-Debitkarte.' },
      { ...BANKS.ing, rank: 3, why: 'Jetzt beantragen — du könntest dich qualifizieren. Deutschlands bestbewertete Bank nach Kundenzufriedenheit.' }
    ];
  }
  return [
    { ...BANKS.ing, rank: 1, why: 'Dein Score erschließt Deutschlands bestbewertete kostenlose Bank. ING ist das Ziel-Konto für etablierte Expats.' },
    { ...BANKS.comdirect, rank: 2, why: 'Der ideale Vermögensaufbau-Begleiter. Comdirets ETF- und Sparfunktionen sind unübertroffen.' },
    { ...BANKS.commerzbank, rank: 3, why: 'Du qualifizierst dich jetzt für Premium-Commerzbank-Produkte. Ideal für Filialnetz, Geschäftskonto oder Hypothek.' }
  ];
}

function getNextSteps(profile, factors) {
  const steps = [];
  const n = profile.normalised;
  const anm = factors.anmeldung?.key || '';
  const acc = factors.accounts?.key || '';
  const pmts = factors.payments?.key || '';
  const dur = factors.duration?.key || '';

  if (anm === 'no' || anm === 'process') {
    steps.push('<strong>Anmeldung sofort erledigen.</strong> Besuche dein lokales Bürgeramt innerhalb von 14 Tagen nach Einzug. Mitbringen: Reisepass, Mietvertrag, Wohnungsgeberbestätigung.');
  }
  if (acc === 'none') {
    steps.push('<strong>Diese Woche ein SCHUFA-freies Konto eröffnen.</strong> N26 oder Vivid öffnen innerhalb von 24 Stunden, kein SCHUFA-Check. Jeder Monat ohne Konto ist verschenkte positive Historie.');
  }
  if (pmts === 'bad') {
    steps.push('<strong>Offene Zahlungen dringend klären.</strong> Kontaktiere den Gläubiger — viele stimmen zu, den Eintrag gegen vollständige Zahlung zu löschen (Löschungsvereinbarung). Innerhalb von 30 Tagen handeln.');
  }
  if (dur === 'new' || dur === 'mid') {
    steps.push('<strong>Kreditkarte 6 Monate verantwortungsvoll nutzen.</strong> Nach dem ersten Konto: gesicherte Kreditkarte beantragen. 2–3 kleine Käufe pro Monat, Saldo monatlich vollständig abbezahlen.');
  }
  if (n < 560) {
    steps.push('<strong>Kostenlosen SCHUFA-Bericht anfordern.</strong> Besuche meineSCHUFA.de → Datenkopie (kostenlos). Alle Einträge auf Fehler prüfen.');
  }
  steps.push('<strong>Den vollständigen SCHUFA-Guide lesen.</strong> Unser Leitfaden deckt alle Faktoren ab — wie man Einträge anficht, die schnellsten Strategien, und was zu tun ist, wenn eine Bank ablehnt. Aktualisiert für 2026.');
  return steps;
}

/* ============================================================
   SVG GAUGE ANIMATION
   ============================================================ */
function animateGauge(normalised) {
  const CIRCUMFERENCE = 251.3; // arc length of the gauge path
  const fill = document.getElementById('gaugeFill');
  const needle = document.getElementById('gaugeNeedle');
  const gaugeNum = document.getElementById('gaugeNum');
  if (!fill || !needle || !gaugeNum) return;

  const pct = normalised / 1000; // 0–1
  const offset = CIRCUMFERENCE * (1 - pct);

  // Animate number counting up
  let start = null;
  const duration = 1800;
  function countUp(ts) {
    if (!start) start = ts;
    const elapsed = ts - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    gaugeNum.textContent = Math.round(eased * normalised);
    if (progress < 1) requestAnimationFrame(countUp);
    else gaugeNum.textContent = normalised;
  }
  requestAnimationFrame(countUp);

  // Animate stroke dash offset (CSS transition handles it)
  requestAnimationFrame(() => {
    fill.style.strokeDashoffset = offset;
  });

  // Animate needle position along the arc
  // Arc: center (100,110), radius 80, from 180° to 0° (left to right)
  const angle = Math.PI * (1 - pct); // π to 0
  const nx = 100 - 80 * Math.cos(angle);
  const ny = 110 - 80 * Math.sin(angle);

  // CSS transition handles smoothness
  setTimeout(() => {
    needle.setAttribute('cx', nx.toFixed(2));
    needle.setAttribute('cy', ny.toFixed(2));
  }, 50);
}

/* ============================================================
   FACTOR BARS
   ============================================================ */
const FACTOR_LABELS = {
  duration:   { label: 'Aufenthaltsdauer',   icon: '📅' },
  employment: { label: 'Beschäftigung',       icon: '💼' },
  anmeldung:  { label: 'Anmeldung',           icon: '🏛️' },
  accounts:   { label: 'Banking-History',     icon: '🏦' },
  payments:   { label: 'Zahlungsverhalten',   icon: '✅' },
  credit:     { label: 'Kredithistorie',      icon: '💳' }
};

function renderFactorBars(factors) {
  const container = document.getElementById('factorBars');
  if (!container) return;
  container.innerHTML = '';

  QUESTIONS.forEach(q => {
    const f = factors[q.id];
    if (!f) return;
    const meta = FACTOR_LABELS[q.id] || { label: q.id, icon: '◆' };
    const pct = f.maxPts > 0 ? Math.max(0, Math.min(100, Math.round((f.pts / f.maxPts) * 100))) : (f.pts < 0 ? 0 : 50);
    const isNegative = f.pts < 0;
    const color = isNegative ? '#EF4444' : pct >= 75 ? '#50C878' : pct >= 40 ? '#D4AF37' : '#F97316';

    const row = document.createElement('div');
    row.className = 'factor-row';
    row.innerHTML = `
      <div class="factor-meta">
        <span class="factor-icon">${meta.icon}</span>
        <span class="factor-label">${meta.label}</span>
        <span class="factor-pct" style="color:${color}">${isNegative ? '−' : ''}${Math.abs(pct)}%</span>
      </div>
      <div class="factor-track">
        <div class="factor-fill" style="width:0%; background:${color}" data-target="${pct}"></div>
      </div>
    `;
    container.appendChild(row);
  });

  // Animate bars in after a short delay
  setTimeout(() => {
    container.querySelectorAll('.factor-fill').forEach(bar => {
      bar.style.transition = 'width 1s cubic-bezier(.4,0,.2,1)';
      bar.style.width = bar.dataset.target + '%';
    });
  }, 200);
}

/* ============================================================
   BANK CARD RENDERING
   ============================================================ */
function renderBankCards(recs) {
  const container = document.getElementById('bankCards');
  if (!container) return;
  container.innerHTML = '';

  recs.forEach((bank, i) => {
    const card = document.createElement('div');
    card.className = 'bank-card';
    card.style.animationDelay = `${i * 0.12}s`;

    const rankLabel = i === 0 ? '🥇 #1 Empfehlung' : i === 1 ? '🥈 #2 Option' : '🥉 #3 Option';
    const featuresHTML = bank.features.slice(0, 4).map(f => `<li>✓ ${f}</li>`).join('');
    const ctaClass = bank.ctaStyle === 'teal-cta' ? 'cta-btn cta-teal' : 'cta-btn';

    card.innerHTML = `
      <div class="bank-card-rank">${rankLabel}</div>
      <div class="bank-card-header">
        <div>
          <div class="bank-card-name">${bank.name}</div>
          <div class="bank-card-tagline">${bank.tagline}</div>
        </div>
      </div>
      <div class="bank-card-why">${bank.why}</div>
      <div class="bank-card-meta">
        <span class="bank-meta-item">💰 ${bank.fee}</span>
        <span class="bank-meta-item">⏱ ${bank.time}</span>
        <span class="bank-meta-item schufa-tag">🔍 ${bank.schufa}</span>
      </div>
      <ul class="bank-features">${featuresHTML}</ul>
      <a href="${bank.url}" class="${ctaClass}" target="_blank" rel="noopener sponsored">${bank.cta} →</a>
    `;
    container.appendChild(card);
  });
}

/* ============================================================
   NEXT STEPS CARD
   ============================================================ */
function renderNextSteps(steps) {
  const card = document.getElementById('nextStepsCard');
  if (!card) return;
  const stepsHTML = steps.map((s, i) => `
    <div class="next-step">
      <div class="next-step-num">${i + 1}</div>
      <div class="next-step-text">${s}</div>
    </div>
  `).join('');
  card.innerHTML = `
    <div class="next-steps-title">📋 Dein persönlicher Action-Plan</div>
    ${stepsHTML}
    <a href="schufa-guide.html" class="cta-btn cta-teal" style="margin-top:1.25rem;display:inline-block;">
      Vollständigen SCHUFA-Guide lesen →
    </a>
  `;
}

/* ============================================================
   STICKY CTA BAR
   ============================================================ */
function showStickyCTA(bank) {
  const bar = document.getElementById('sticky-cta-bar');
  const nameEl = document.getElementById('stickyBankName');
  const linkEl = document.getElementById('stickyCTALink');
  if (!bar || !nameEl || !linkEl) return;
  nameEl.textContent = bank.name;
  linkEl.href = bank.url;
  bar.classList.add('visible');
}

/* ============================================================
   SHOW RESULT
   ============================================================ */
function showResult() {
  const calcScreen = document.getElementById('calcScreen');
  const resultScreen = document.getElementById('resultScreen');
  if (!calcScreen || !resultScreen) return;

  calcScreen.style.display = 'none';
  resultScreen.style.display = 'block';

  scoreResult = computeScore();
  const profile = getScoreProfile(scoreResult.normalised);
  const recs = getBankRecs(scoreResult.normalised, scoreResult.factors);
  const nextSteps = getNextSteps({ normalised: scoreResult.normalised }, scoreResult.factors);

  // Score label & description
  const levelLabel = document.getElementById('scoreLevelLabel');
  const scoreDesc = document.getElementById('scoreDesc');
  if (levelLabel) { levelLabel.textContent = profile.level; levelLabel.style.color = profile.color; }
  if (scoreDesc) scoreDesc.textContent = profile.desc;

  // Pills
  const pillsEl = document.getElementById('scorePills');
  if (pillsEl) {
    pillsEl.innerHTML = profile.pills.map(p => `<span class="score-pill">${p}</span>`).join('');
  }

  // Animate gauge
  animateGauge(scoreResult.normalised);

  // Factor bars
  renderFactorBars(scoreResult.factors);

  // Recommendations
  const recoTitle = document.getElementById('recoTitle');
  const recoSub = document.getElementById('recoSub');
  if (recoTitle) recoTitle.textContent = `Empfohlen für dein Profil — ${profile.level}`;
  if (recoSub) recoSub.textContent = `Basierend auf deinem Score von ~${scoreResult.normalised}/1000 haben wir die besten Banken für deine Situation ausgewählt.`;
  renderBankCards(recs);

  // Next steps
  renderNextSteps(nextSteps);

  // Sticky CTA
  if (recs.length > 0) showStickyCTA(recs[0]);

  // Scroll to result
  setTimeout(() => {
    resultScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);
}

/* ============================================================
   RESTART
   ============================================================ */
function restartQuiz() {
  answers = {};
  selectedOptionIndex = -1;
  currentStep = 0;
  scoreResult = null;

  const resultScreen = document.getElementById('resultScreen');
  const quizScreen = document.getElementById('quiz-screen');
  const calcScreen = document.getElementById('calcScreen');
  const stickyCTA = document.getElementById('sticky-cta-bar');

  if (resultScreen) resultScreen.style.display = 'none';
  if (calcScreen) calcScreen.style.display = 'none';
  if (quizScreen) quizScreen.style.display = 'block';
  if (stickyCTA) stickyCTA.classList.remove('visible');

  buildStepTracker();
  renderQuestion(0);

  document.getElementById('quiz-screen')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ============================================================
   BLOCKED ACCOUNT CALCULATOR
   ============================================================ */
const BLOCKED_ACCOUNT_DATA = {
  fintiba: {
    name: 'Fintiba',
    setupFee: 49,
    monthlyFee: 4.90,
    transferFeePerMonth: 1.50, // per disbursement
    interestRate: 0.01,        // 1% p.a. approx
    disbursementFee: 0,
    color: '#50C878',
    url: '#fintiba-affiliate',
    features: ['BaFin-reguliert', 'Schnelle Eröffnung (~3 Tage)', 'Kein Mindestguthaben', 'Online-Portal auf Englisch']
  },
  expatrio: {
    name: 'Expatrio',
    setupFee: 89,
    monthlyFee: 6.90,
    transferFeePerMonth: 0,
    interestRate: 0.005,
    disbursementFee: 0,
    color: '#D4AF37',
    url: '#expatrio-affiliate',
    features: ['Kombinierbar mit Krankenversicherung', 'Studentenrabatte', 'Multi-Service-Paket', 'SEPA-Sofortauszahlung']
  }
};

function initBlockedAccountCalculator() {
  const calcBtn = document.getElementById('blocked-calc-btn');
  const durationInput = document.getElementById('blocked-duration');
  const amountInput = document.getElementById('blocked-amount');

  if (!calcBtn) return;

  calcBtn.addEventListener('click', calculateBlockedAccount);

  // Real-time update on input change
  [durationInput, amountInput].forEach(el => {
    if (el) el.addEventListener('input', calculateBlockedAccount);
  });

  // Initial calculation with defaults
  calculateBlockedAccount();
}

function calculateBlockedAccount() {
  const durationEl = document.getElementById('blocked-duration');
  const amountEl = document.getElementById('blocked-amount');

  const duration = parseInt(durationEl?.value) || 12;
  const amount = parseFloat(amountEl?.value) || 11208; // German standard blocked amount 2026

  const results = {};
  for (const [key, provider] of Object.entries(BLOCKED_ACCOUNT_DATA)) {
    const setup = provider.setupFee;
    const monthly = provider.monthlyFee * duration;
    const transfers = provider.transferFeePerMonth * duration;
    const interest = amount * provider.interestRate * (duration / 12);
    const total = setup + monthly + transfers;
    const net = total - interest; // net cost after interest earned

    results[key] = {
      ...provider,
      setup,
      monthly,
      transfers,
      interest: interest.toFixed(2),
      total: total.toFixed(2),
      net: Math.max(0, net).toFixed(2)
    };
  }

  renderBlockedAccountResults(results, duration, amount);
}

function renderBlockedAccountResults(results, duration, amount) {
  const container = document.getElementById('blocked-results');
  if (!container) return;

  const providers = Object.values(results);
  const cheapest = providers.reduce((a, b) => parseFloat(a.net) < parseFloat(b.net) ? a : b);

  container.innerHTML = providers.map(p => {
    const isBest = p.name === cheapest.name;
    return `
      <div class="blocked-card${isBest ? ' blocked-card-best' : ''}">
        ${isBest ? '<div class="blocked-best-badge">💰 Günstigste Option</div>' : ''}
        <div class="blocked-provider-name" style="color:${p.color}">${p.name}</div>
        <div class="blocked-breakdown">
          <div class="blocked-line"><span>Einrichtungsgebühr</span><span>€${p.setup.toFixed(2)}</span></div>
          <div class="blocked-line"><span>Monatl. Gebühren (${duration} Mo.)</span><span>€${p.monthly.toFixed(2)}</span></div>
          ${parseFloat(p.transfers) > 0 ? `<div class="blocked-line"><span>Auszahlungsgebühren</span><span>€${p.transfers.toFixed(2)}</span></div>` : ''}
          <div class="blocked-line blocked-line-interest"><span>Zinsgutschrift (~)</span><span>−€${p.interest}</span></div>
          <div class="blocked-line blocked-total"><span><strong>Nettokosten gesamt</strong></span><span><strong>€${p.net}</strong></span></div>
        </div>
        <ul class="blocked-features">
          ${p.features.map(f => `<li>✓ ${f}</li>`).join('')}
        </ul>
        <a href="${p.url}" class="cta-btn${isBest ? ' cta-teal' : ''}" target="_blank" rel="noopener sponsored">
          ${p.name} Konto eröffnen →
        </a>
      </div>
    `;
  }).join('');

  // Update summary
  const summaryEl = document.getElementById('blocked-summary');
  if (summaryEl) {
    const saving = Math.abs(parseFloat(results.fintiba?.net || 0) - parseFloat(results.expatrio?.net || 0)).toFixed(2);
    summaryEl.textContent = `Für ${duration} Monate mit €${amount.toLocaleString('de-DE')} Blockbetrag. Ersparnis durch beste Wahl: ~€${saving}`;
  }
}

/* ============================================================
   COOKIE CONSENT SYNC (modal overlay click)
   ============================================================ */
function initModalOverlays() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) {
        const id = overlay.id.replace('modal-', '');
        closeModal(id);
      }
    });
  });

  // ESC key closes modals
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.visible').forEach(modal => {
        const id = modal.id.replace('modal-', '');
        closeModal(id);
      });
    }
  });
}

/* ============================================================
   HEADER SCROLL EFFECT
   ============================================================ */
function initHeaderScroll() {
  const header = document.querySelector('.global-header');
  if (!header) return;
  let lastY = 0;
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    if (y > 60) {
      header.classList.add('scrolled');
      header.classList.toggle('hidden', y > lastY + 5 && y > 200);
    } else {
      header.classList.remove('scrolled', 'hidden');
    }
    lastY = y;
  }, { passive: true });
}

/* ============================================================
   SMOOTH ANCHOR SCROLL
   ============================================================ */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

/* ============================================================
   INIT — called when DOM is ready
   ============================================================ */
function init() {
  buildStepTracker();
  renderQuestion(0);
  initProgressBar();
  initNav();
  initCookieBanner();
  initModalOverlays();
  initHeaderScroll();
  initSmoothScroll();
  initBlockedAccountCalculator();
}

// Expose functions needed by inline HTML handlers
window.toggleFaq = toggleFaq;
window.goNext = goNext;
window.goBack = goBack;
window.restartQuiz = restartQuiz;
window.openModal = openModal;
window.closeModal = closeModal;
window.acceptCookies = acceptCookies;
window.declineCookies = declineCookies;
window.saveGranularCookies = saveGranularCookies;

// Boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}