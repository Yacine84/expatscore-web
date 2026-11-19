/* ============================================================
   ExpatScore.de — script.js
   SCHUFA Score Simulator 2026 + Blocked Account Calculator
   Vanilla JS (ES6+) — No external dependencies
   ============================================================ */

'use strict';

/* ============================================================
   QUESTION DATA
   ============================================================ */
var QUESTIONS = [
  {
    id: 'duration',
    text: 'How long have you been living in Germany?',
    hint: 'Length of residency is one of the most important SCHUFA factors. The longer you\'ve lived here, the more data SCHUFA has on you — even if that data is all positive.',
    options: [
      { label: 'I just arrived (under 3 months)',      sub: 'No SCHUFA data exists yet',             badge: null,      score: 0,   key: 'new' },
      { label: '3 to 12 months',                        sub: 'Early stage — building history',        badge: 'building',score: 60,  key: 'mid' },
      { label: '1 to 3 years',                          sub: 'Established — solid data trail',        badge: null,      score: 130, key: 'est' },
      { label: 'More than 3 years',                     sub: 'Long-term — strong history potential',  badge: 'best',    score: 200, key: 'long' }
    ]
  },
  {
    id: 'employment',
    text: 'What is your current employment status in Germany?',
    hint: 'Employment stability signals financial reliability. Banks and SCHUFA both weight this heavily — a permanent contract is the gold standard.',
    options: [
      { label: 'Full-time employed (permanent contract)', sub: 'Strongest employment signal',          badge: 'best',  score: 120, key: 'employed' },
      { label: 'Self-employed or freelancer',             sub: 'Variable income — manageable',         badge: null,    score: 75,  key: 'freelance' },
      { label: 'Student (enrolled at university)',        sub: 'Valid residency purpose',              badge: null,    score: 55,  key: 'student' },
      { label: 'Currently job-seeking',                  sub: 'Temporary — does not block accounts',  badge: null,    score: 25,  key: 'seeking' }
    ]
  },
  {
    id: 'anmeldung',
    text: 'Are you officially registered at a German address? (Anmeldung)',
    hint: 'Anmeldung is your official address registration at your local Bürgeramt. It is legally required within 2 weeks of moving in, and virtually all German banks require it to open an account.',
    options: [
      { label: 'Yes — fully registered (Angemeldet)',      sub: 'Required by all major German banks',   badge: 'best',  score: 80,  key: 'yes' },
      { label: 'In progress — I have an appointment',      sub: 'Some banks accept this temporarily',   badge: null,    score: 30,  key: 'process' },
      { label: 'Not yet — I haven\'t registered',          sub: 'You need this urgently',               badge: 'risk',  score: 0,   key: 'no' }
    ]
  },
  {
    id: 'accounts',
    text: 'Do you currently have any German bank accounts?',
    hint: 'Having an active German bank account is the single fastest way to build SCHUFA history. Even a free N26 or Vivid account counts — every month it\'s open is a month of positive history.',
    options: [
      { label: 'No German bank accounts at all',            sub: 'SCHUFA has zero banking data on you', badge: null,   score: 0,   key: 'none' },
      { label: 'One account, opened recently (< 1 year)',   sub: 'Just starting to build history',      badge: null,   score: 60,  key: 'one_new' },
      { label: 'One account, over 12 months old',           sub: 'Solid banking history building',      badge: null,   score: 100, key: 'one_old' },
      { label: 'Two or more German accounts',               sub: 'Strong banking footprint',            badge: 'best', score: 130, key: 'multi' }
    ]
  },
  {
    id: 'payments',
    text: 'Have you ever missed a payment in Germany?',
    hint: 'Missed payments — rent, utilities, phone contracts, streaming subscriptions — are the #1 cause of SCHUFA damage. Even one unresolved missed payment can reduce your score significantly for up to 3 years.',
    options: [
      { label: 'Never — all payments on time',              sub: 'Ideal payment behaviour',             badge: 'best',  score: 120, key: 'perfect' },
      { label: 'Once or twice — but I paid eventually',     sub: 'Minor impact if resolved quickly',    badge: null,    score: 40,  key: 'minor' },
      { label: 'Yes — and it is still unresolved',          sub: 'Significant negative impact',         badge: 'risk',  score: -80, key: 'bad' },
      { label: 'Not applicable — I\'m too new here',        sub: 'No payment history yet',              badge: null,    score: 50,  key: 'na' }
    ]
  },
  {
    id: 'credit',
    text: 'What is your credit history in Germany?',
    hint: 'Responsibly managed credit — a credit card paid off monthly, or an installment loan — actively improves your SCHUFA score over time. No credit at all is neutral, not positive.',
    options: [
      { label: 'No credit at all — completely new',         sub: 'Neutral starting point',             badge: null,    score: 30,  key: 'none' },
      { label: 'Credit card — always paid on time',         sub: 'Excellent positive signal',          badge: 'best',  score: 110, key: 'cc_good' },
      { label: 'Instalment loan — always paid on time',     sub: 'Strong positive signal',             badge: 'best',  score: 120, key: 'loan_good' },
      { label: 'Have credit — but some late payments',      sub: 'Negative impact on score',           badge: 'risk',  score: -20, key: 'late' }
    ]
  }
];

/* ============================================================
   BANK DATABASE
   ============================================================ */
var BANKS = {
  n26: {
    name: 'N26 Standard',
    tagline: 'Germany\'s most expat-friendly digital bank',
    url: 'https://n26.com/r/expatscore', /* Replace with real affiliate link */
    cta: 'Open N26 free',
    ctaStyle: 'teal-cta',
    fee: 'Free forever',
    time: '8 min setup',
    schufa: 'No SCHUFA check',
    features: ['No SCHUFA required', 'VideoIdent — fully online', 'English app interface', 'Free Mastercard', 'Instant account number'],
    why: 'The go-to first account for expats. Opens fully online with just your passport and a 5-minute video call — no German address required to apply.'
  },
  vivid: {
    name: 'Vivid Money',
    tagline: 'Multi-currency account for international professionals',
    url: '#vivid-affiliate',
    cta: 'Open Vivid free',
    ctaStyle: '',
    fee: 'Free plan available',
    time: '10 min setup',
    schufa: 'No SCHUFA check',
    features: ['No SCHUFA check', 'Multi-currency pockets', 'Cashback on purchases', 'English support', 'EU + non-EU accepted'],
    why: 'Excellent as a second account for multi-currency management, cashback, and salary deposits from international employers.'
  },
  bunq: {
    name: 'Bunq',
    tagline: 'International-first bank built for people who move',
    url: '#bunq-affiliate',
    cta: 'Try Bunq free',
    ctaStyle: '',
    fee: '3 months free trial',
    time: '5 min setup',
    schufa: 'No SCHUFA required',
    features: ['No SCHUFA check', '100% online opening', 'No Anmeldung needed to apply', 'Dutch bank — EU deposit protection', 'Multi-language app'],
    why: 'Dutch bank with a 3-month free trial. Ideal for those not yet registered in Germany — no Anmeldung required to open the account.'
  },
  dkb: {
    name: 'DKB — Deutsche Kreditbank',
    tagline: 'Germany\'s most trusted online bank for settled expats',
    url: '#dkb-affiliate',
    cta: 'Apply for DKB',
    ctaStyle: 'teal-cta',
    fee: 'Free with conditions',
    time: '3–5 day approval',
    schufa: 'Soft SCHUFA check',
    features: ['Free with €700+/mo income', 'VISA card accepted worldwide', 'Excellent customer service', 'German IBAN instantly', 'PostIdent or VideoIdent'],
    why: 'The expat community\'s favourite bank for a reason. Accepts newcomers with basic history and provides the most reliable full-service German banking experience.'
  },
  c24: {
    name: 'C24 Bank',
    tagline: 'New generation German bank — more lenient than traditional options',
    url: '#c24-affiliate',
    cta: 'Open C24 account',
    ctaStyle: '',
    fee: 'Free basic account',
    time: 'Same-day approval',
    schufa: 'Basic SCHUFA check',
    features: ['Lenient SCHUFA requirements', 'Fully digital onboarding', 'English interface available', 'German IBAN issued instantly', 'Free Visa debit card'],
    why: 'Launched 2023 — C24 has the most flexible SCHUFA requirements of any regulated German bank. Strong choice for those with 3–12 months of history.'
  },
  ing: {
    name: 'ING Germany',
    tagline: 'Top-rated free German current account — best for established expats',
    url: '#ing-affiliate',
    cta: 'Apply for ING',
    ctaStyle: 'teal-cta',
    fee: 'Free forever',
    time: '3–7 day approval',
    schufa: 'Full SCHUFA check',
    features: ['No monthly fee ever', 'Highest German customer satisfaction', '€1,500/mo income requirement', 'Instant credit card upgrade path', 'Full German banking suite'],
    why: 'The gold standard. Germany\'s highest-rated bank by customer satisfaction — unlocked once you\'ve built solid SCHUFA history. Worth the wait.'
  },
  comdirect: {
    name: 'Comdirect',
    tagline: 'Full-service bank for expats building long-term wealth in Germany',
    url: '#comdirect-affiliate',
    cta: 'Open Comdirect',
    ctaStyle: '',
    fee: 'Free with activity',
    time: '5–7 day approval',
    schufa: 'Full SCHUFA check',
    features: ['Free with 2 transactions/month', 'Savings and ETF integration', 'SCHUFA-building account type', 'Visa and Mastercard', 'Strong mobile banking app'],
    why: 'The ideal companion account for savings and ETF investing. Comdirect pairs perfectly with ING for expats building long-term financial life in Germany.'
  },
  commerzbank: {
    name: 'Commerzbank',
    tagline: 'Germany\'s second-largest bank — full premium service',
    url: '#commerzbank-affiliate',
    cta: 'Open Commerzbank',
    ctaStyle: 'teal-cta',
    fee: '€9.90/mo (or free)',
    time: '2–5 day approval',
    schufa: 'Full SCHUFA check',
    features: ['Nationwide branch network', 'Premium credit card options', 'Excellent mortgage access', 'Business account available', 'Full banking suite'],
    why: 'For expats with excellent SCHUFA who want a traditional German bank with branches, face-to-face service, and access to mortgages and premium credit.'
  }
};

/* ============================================================
   STATE
   ============================================================ */
var currentStep = 0;
var answers = {};
var selectedOptionIndex = -1;
var scoreResult = null;

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
  // ── Wire up buttons (fix: event listeners were never attached) ──────────
  const acceptBtn   = document.querySelector('.cookie-accept');
  const declineBtn  = document.querySelector('.cookie-decline');
  const settingsBtn = document.querySelector('.cookie-settings-btn');

  // Helper: attach both 'click' and 'touchend' for cross-browser/iOS support
  function addTapListener(el, handler) {
    if (!el) return;
    el.addEventListener('click', handler);
    // touchend fires before click and avoids the iOS 300ms delay entirely
    el.addEventListener('touchend', function(e) {
      e.preventDefault(); // prevent the ghost click that follows
      handler(e);
    }, { passive: false });
  }

  addTapListener(acceptBtn,   acceptCookies);
  addTapListener(declineBtn,  declineCookies);
  addTapListener(settingsBtn, () => openModal('cookie-settings'));

  // Also wire up the modal save button
  const saveBtn = document.querySelector('.cookie-save-btn');
  addTapListener(saveBtn, saveGranularCookies);

  // Also wire up the modal close button
  const closeBtn = document.querySelector('#modal-cookie-settings .modal-close');
  addTapListener(closeBtn, () => closeModal('cookie-settings'));

  // Also wire up footer cookie settings link
  const settingsLink = document.getElementById('cookieSettingsLink');
  if (settingsLink) {
    addTapListener(settingsLink, (e) => { e.preventDefault(); openModal('cookie-settings'); });
  }

  // ── Show the banner if consent not yet recorded ──────────────────────────
  if (localStorage.getItem('cookieConsent')) return;
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    setTimeout(() => banner.classList.add('visible'), 1200);
  }
}

function acceptCookies() {
  localStorage.setItem('cookieConsent', 'all');
  hideCookieBanner();
  document.body.style.overflow = 'auto';
}

function declineCookies() {
  localStorage.setItem('cookieConsent', 'necessary');
  hideCookieBanner();
  document.body.style.overflow = 'auto';
}

function saveGranularCookies() {
  const analytics = document.getElementById('toggle-analytics')?.checked;
  const affiliate = document.getElementById('toggle-affiliate')?.checked;
  localStorage.setItem('cookieConsent', JSON.stringify({ analytics, affiliate }));
  hideCookieBanner();
  closeModal('cookie-settings');
  document.body.style.overflow = 'auto';
}

function hideCookieBanner() {
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.remove('visible');
    banner.style.display = 'none';
    banner.style.pointerEvents = 'none';
  }
  document.body.style.overflow = 'auto';
}

function openModal(id) {
  const modal = document.getElementById(`modal-${id}`);
  if (modal) {
    modal.classList.add('open');   // fix: CSS uses .modal-overlay.open not .visible
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(id) {
  const modal = document.getElementById(`modal-${id}`);
  if (modal) {
    modal.classList.remove('open'); // fix: match CSS class
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
  if (sl) sl.textContent = `Step ${step + 1} of ${QUESTIONS.length}`;
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
  btn.textContent = currentStep === QUESTIONS.length - 1 ? 'Calculate my SCHUFA score ★' : 'Continue →';
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
  if (n >= 776) return { level: 'Excellent',  color: '#00c4a7', desc: 'Your SCHUFA profile is in the highest class — Excellent, the class held by around 62% of people in Germany. German banks will actively compete for your business. You qualify for credit, mortgages, and premium accounts without issue.', pills: ['Held by ~62% of people', 'All accounts available', 'Mortgage-eligible'] };
  if (n >= 709) return { level: 'Good',       color: '#3ecf8e', desc: 'Strong SCHUFA profile — the Good class. You qualify for virtually all German bank accounts, most credit cards, and many personal loans. Keep your current behaviour to reach Excellent.', pills: ['Most loans accessible', 'Credit cards available', 'Keep building'] };
  if (n >= 642) return { level: 'Acceptable', color: '#c9a84c', desc: 'You are in the Acceptable class — a solid foundation with room to grow. You can open most accounts and some credit products. A longer banking history and zero missed payments will push you into the Good class.', pills: ['Standard accounts open', 'Some credit accessible', 'Growth phase'] };
  if (n >= 100) return { level: 'Sufficient', color: '#e8724a', desc: 'Your SCHUFA sits in the Sufficient class — the widest class, and where most newcomers start. Banks see elevated risk, so credit products are limited for now, and several banks operate without SCHUFA checks at all. Open one today: consistent on-time payments are what move you up.', pills: ['Elevated risk class', 'No-SCHUFA banks first', 'Build history now'] };
  return                { level: 'No SCHUFA Data', color: '#f26d6d', desc: 'You have no SCHUFA history yet — which is completely normal. SCHUFA doesn\'t exist in most countries outside Germany. Several banks specifically welcome newcomers without any credit check at all.', pills: ['No record — yet', 'Perfect starting point', 'Multiple banks for you'] };
}

function getBankRecs(n, factors) {
  const dur = factors.duration?.key || '';
  const acc = factors.accounts?.key || '';

  if (n < 300 || dur === 'new' || acc === 'none') {
    return [
      { ...BANKS.n26, rank: 1, why: 'No SCHUFA check required. Opens fully online with VideoIdent in 8 minutes — just your passport needed. Every month it\'s open builds your SCHUFA history.' },
      { ...BANKS.vivid, rank: 2, why: 'No credit check, multi-currency pockets, and cashback. Ideal as a day-to-day account while you build SCHUFA through N26.' },
      { ...BANKS.bunq, rank: 3, why: '3-month free trial and no Anmeldung required to apply. Great backup option if your Anmeldung is still processing.' }
    ];
  }
  if (n < 560) {
    return [
      { ...BANKS.n26, rank: 1, why: 'Still your safest approval. N26 guarantees approval and gives you a reliable base to build from — even with limited history.' },
      { ...BANKS.c24, rank: 2, why: 'New German bank with the most lenient SCHUFA requirements in its class. Ideal bridge bank for those with 3–18 months of German history.' },
      { ...BANKS.dkb, rank: 3, why: 'Worth applying now. DKB accepts most newcomers with basic history and gives you a full-service German banking relationship from day one.' }
    ];
  }
  if (n < 750) {
    return [
      { ...BANKS.dkb, rank: 1, why: 'Your profile now qualifies you for DKB — the expat community\'s favourite for reliability, free VISA, and excellent customer service.' },
      { ...BANKS.c24, rank: 2, why: 'Complementary to DKB — instant cashback and a Visa debit in one account. A strong second card for everyday spending.' },
      { ...BANKS.ing, rank: 3, why: 'Apply now — you may qualify. Germany\'s highest-rated bank by customer satisfaction. If approved, this becomes your long-term primary account.' }
    ];
  }
  return [
    { ...BANKS.ing, rank: 1, why: 'Your score unlocks Germany\'s best-rated free bank. ING is the destination account for established expats — best conditions, no fees, highest satisfaction.' },
    { ...BANKS.comdirect, rank: 2, why: 'The ideal wealth-building companion. Comdirect\'s ETF and savings features are unmatched among free German accounts — pair it with ING.' },
    { ...BANKS.commerzbank, rank: 3, why: 'You now qualify for premium Commerzbank products. Consider this if you need a branch network, business account, or are planning a mortgage.' }
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
    steps.push('<strong>Complete your Anmeldung immediately.</strong> Visit your local Bürgeramt within 2 weeks of moving in. This is legally required and unlocks all German financial services. Bring: passport, rental contract, and Wohnungsgeberbestätigung from your landlord.');
  }
  if (acc === 'none') {
    steps.push('<strong>Open a no-SCHUFA bank account this week.</strong> N26 or Vivid open within 24 hours, no credit check. Having any German bank account starts building SCHUFA history immediately — every month you wait is a wasted month of potential positive history.');
  }
  if (pmts === 'bad') {
    steps.push('<strong>Resolve outstanding payments urgently.</strong> Unresolved SCHUFA entries stay on record for 3 years. Contact the creditor directly — many will agree to remove the entry in exchange for full payment. This is called a <em>Löschungsvereinbarung</em>. Act within 30 days for the best outcome.');
  }
  if (dur === 'new' || dur === 'mid') {
    steps.push('<strong>Use a credit card responsibly for 6 months.</strong> After opening your first account, apply for a secured credit card. Make 2–3 small purchases per month and pay the full balance monthly. This single action improves SCHUFA scores faster than anything else for newcomers.');
  }
  if (n < 560) {
    steps.push('<strong>Get your free official SCHUFA report.</strong> Once per year, SCHUFA must provide your full credit report for free by law. Visit <em>meineSCHUFA.de → Datenkopie (kostenlos)</em>. Verify there are no errors — even small inaccuracies can significantly damage your score.');
  }
  steps.push('<strong>Read our complete SCHUFA Guide for Expats.</strong> Our in-depth guide covers every factor, how to dispute entries, the fastest improvement strategies, and what to do when a bank says no. Updated for 2026.');
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
var FACTOR_LABELS = {
  duration:   { label: 'Time in Germany',    icon: '📅' },
  employment: { label: 'Employment status',  icon: '💼' },
  anmeldung:  { label: 'Anmeldung status',   icon: '🏛️' },
  accounts:   { label: 'Banking history',    icon: '🏦' },
  payments:   { label: 'Payment behaviour',  icon: '✅' },
  credit:     { label: 'Credit history',     icon: '💳' }
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

    const rankLabel = i === 0 ? '🥇 #1 Recommendation' : i === 1 ? '🥈 #2 Option' : '🥉 #3 Option';
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
    <div class="next-steps-title">Your personalised action plan</div>
    ${stepsHTML}
    <a href="schufa-guide.html" class="cta-btn cta-teal" style="margin-top:1.25rem;display:inline-block;">
      Read the complete SCHUFA Guide for Expats →
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
  if (recoTitle) recoTitle.textContent = `Recommended for your profile — ${profile.level}`;
  if (recoSub) recoSub.textContent = `Based on your score of ~${scoreResult.normalised}/1000, we selected the best banks for your situation.`;
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
    features: ['BaFin-regulated', 'Fast opening (~3 days)', 'No minimum balance', 'Online portal in English']
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
    features: ['Can be combined with health insurance', 'Student discounts', 'Multi-service package', 'SEPA instant payout']
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
        ${isBest ? '<div class="blocked-best-badge">💰 Cheapest option</div>' : ''}
        <div class="blocked-provider-name" style="color:${p.color}">${p.name}</div>
        <div class="blocked-breakdown">
          <div class="blocked-line"><span>Setup fee</span><span>€${p.setup.toFixed(2)}</span></div>
          <div class="blocked-line"><span>Monthly fees (${duration} mo.)</span><span>€${p.monthly.toFixed(2)}</span></div>
          ${parseFloat(p.transfers) > 0 ? `<div class="blocked-line"><span>Payout fees</span><span>€${p.transfers.toFixed(2)}</span></div>` : ''}
          <div class="blocked-line blocked-line-interest"><span>Zinsgutschrift (~)</span><span>−€${p.interest}</span></div>
          <div class="blocked-line blocked-total"><span><strong>Nettokosten gesamt</strong></span><span><strong>€${p.net}</strong></span></div>
        </div>
        <ul class="blocked-features">
          ${p.features.map(f => `<li>✓ ${f}</li>`).join('')}
        </ul>
        <a href="${p.url}" class="cta-btn${isBest ? ' cta-teal' : ''}" target="_blank" rel="noopener sponsored">
          ${p.name} Open account →
        </a>
      </div>
    `;
  }).join('');

  // Update summary
  const summaryEl = document.getElementById('blocked-summary');
  if (summaryEl) {
    const saving = Math.abs(parseFloat(results.fintiba?.net || 0) - parseFloat(results.expatrio?.net || 0)).toFixed(2);
    summaryEl.textContent = `For ${duration} months with €${amount.toLocaleString('de-DE')} blocked. You save ~€${saving} with the best choice.`;
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
      document.querySelectorAll('.modal-overlay.open').forEach(modal => {  // fix: was .visible
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