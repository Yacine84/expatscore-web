/* ============================================================
   SIMULATOR DATA
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
      { label: 'Full-time employed (permanent contract)', sub: 'Strongest employment signal',         badge: 'best',  score: 120, key: 'employed' },
      { label: 'Self-employed or freelancer',             sub: 'Variable income — manageable',        badge: null,    score: 75,  key: 'freelance' },
      { label: 'Student (enrolled at university)',        sub: 'Valid residency purpose',             badge: null,    score: 55,  key: 'student' },
      { label: 'Currently job-seeking',                  sub: 'Temporary — does not block accounts', badge: null,    score: 25,  key: 'seeking' }
    ]
  },
  {
    id: 'anmeldung',
    text: 'Are you officially registered at a German address? (Anmeldung)',
    hint: 'Anmeldung is your official address registration at your local Bürgeramt. It is legally required within 2 weeks of moving in, and virtually all German banks require it to open an account.',
    options: [
      { label: 'Yes — fully registered (Angemeldet)',      sub: 'Required by all major German banks',  badge: 'best',  score: 80,  key: 'yes' },
      { label: 'In progress — I have an appointment',      sub: 'Some banks accept this temporarily',  badge: null,    score: 30,  key: 'process' },
      { label: 'Not yet — I haven\'t registered',          sub: 'You need this urgently',              badge: 'risk',  score: 0,   key: 'no' }
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
    hint: 'Missed payments — rent, utilities, phone contracts, streaming subscriptions — are the #1 cause of SCHUFA damage. Even one unresolved missed payment can reduce your score significantly.',
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

var BANKS = {
  n26:         { name: 'N26 Standard',      tagline: 'Germany\'s most expat-friendly digital bank',                       url: 'https://n26.com/r/expatscore', cta: 'Open N26 free',       ctaStyle: 'teal-cta', fee: 'Free forever',          time: '8 min setup',         schufa: 'No SCHUFA check',   features: ['No SCHUFA required','VideoIdent — fully online','English app interface','Free Mastercard','Instant account number'],                          why: 'The go-to first account for expats. Opens fully online with just your passport and a 5-minute video call — no German address required to apply.' },
  vivid:       { name: 'Vivid Money',        tagline: 'Multi-currency account for international professionals',            url: '#vivid-affiliate',             cta: 'Open Vivid free',     ctaStyle: '',         fee: 'Free plan available',   time: '10 min setup',        schufa: 'No SCHUFA check',   features: ['No SCHUFA check','Multi-currency pockets','Cashback on purchases','English support','EU + non-EU accepted'],                                    why: 'Excellent as a second account for multi-currency management, cashback, and salary deposits from international employers.' },
  bunq:        { name: 'Bunq',               tagline: 'International-first bank built for people who move',               url: '#bunq-affiliate',              cta: 'Try Bunq free',       ctaStyle: '',         fee: '3 months free trial',   time: '5 min setup',         schufa: 'No SCHUFA required',features: ['No SCHUFA check','100% online opening','No Anmeldung needed to apply','Dutch bank — EU deposit protection','Multi-language app'],          why: 'Dutch bank with a 3-month free trial. Ideal for those not yet registered in Germany — no Anmeldung required to open the account.' },
  dkb:         { name: 'DKB — Deutsche Kreditbank', tagline: 'Germany\'s most trusted online bank for settled expats',   url: '#dkb-affiliate',               cta: 'Apply for DKB',       ctaStyle: 'teal-cta', fee: 'Free with conditions',  time: '3–5 day approval',    schufa: 'Soft SCHUFA check', features: ['Free with €700+/mo income','VISA card accepted worldwide','Excellent customer service','German IBAN instantly','PostIdent or VideoIdent'],    why: 'The expat community\'s favourite bank for a reason. Accepts newcomers with basic history and provides the most reliable full-service German banking experience.' },
  c24:         { name: 'C24 Bank',           tagline: 'New generation German bank — more lenient than traditional options',url: '#c24-affiliate',              cta: 'Open C24 account',    ctaStyle: '',         fee: 'Free basic account',    time: 'Same-day approval',   schufa: 'Basic SCHUFA check',features: ['Lenient SCHUFA requirements','Fully digital onboarding','English interface available','German IBAN issued instantly','Free Visa debit card'], why: 'Launched 2023 — C24 has the most flexible SCHUFA requirements of any regulated German bank. Strong choice for those with 3–12 months of history.' },
  ing:         { name: 'ING Germany',        tagline: 'Top-rated free German current account — best for established expats',url: '#ing-affiliate',             cta: 'Apply for ING',       ctaStyle: 'teal-cta', fee: 'Free forever',          time: '3–7 day approval',    schufa: 'Full SCHUFA check', features: ['No monthly fee ever','Highest German customer satisfaction','€1,500/mo income requirement','Instant credit card upgrade path','Full German banking suite'], why: 'The gold standard. Germany\'s highest-rated bank by customer satisfaction — unlocked once you\'ve built solid SCHUFA history. Worth the wait.' },
  comdirect:   { name: 'Comdirect',          tagline: 'Full-service bank for expats building long-term wealth in Germany', url: '#comdirect-affiliate',        cta: 'Open Comdirect',      ctaStyle: '',         fee: 'Free with activity',    time: '5–7 day approval',    schufa: 'Full SCHUFA check', features: ['Free with 2 transactions/month','Savings and ETF integration','SCHUFA-building account type','Visa and Mastercard','Strong mobile banking app'],    why: 'The ideal companion account for savings and ETF investing. Pairs perfectly with ING for expats building long-term financial life in Germany.' },
  commerzbank: { name: 'Commerzbank',        tagline: 'Germany\'s second-largest bank — full premium service',            url: '#commerzbank-affiliate',      cta: 'Open Commerzbank',    ctaStyle: 'teal-cta', fee: '€9.90/mo (or free)',    time: '2–5 day approval',    schufa: 'Full SCHUFA check', features: ['Nationwide branch network','Premium credit card options','Excellent mortgage access','Business account available','Full banking suite'],             why: 'For expats with excellent SCHUFA who want a traditional German bank with branches, face-to-face service, and access to mortgages and premium credit.' }
};

/* ============================================================
   SIMULATOR STATE
============================================================ */
var simStep = 0;
var simAnswers = {};
var simSelectedIdx = -1;
var simResult = null;

/* ============================================================
   SIMULATOR INIT
============================================================ */
function simInit() {
  buildStepTracker();
  renderQuestion(0);
}

function buildStepTracker() {
  var tracker = document.getElementById('stepTracker');
  if (!tracker) return;
  tracker.innerHTML = '';
  QUESTIONS.forEach(function(q, i) {
    if (i > 0) {
      var conn = document.createElement('div');
      conn.className = 'step-connector';
      conn.id = 'conn-' + i;
      tracker.appendChild(conn);
    }
    var dot = document.createElement('div');
    dot.className = 'step-dot' + (i === 0 ? ' active' : '');
    dot.id = 'dot-' + i;
    tracker.appendChild(dot);
  });
}

function updateStepTracker(step) {
  QUESTIONS.forEach(function(q, i) {
    var dot = document.getElementById('dot-' + i);
    if (!dot) return;
    dot.className = 'step-dot';
    if (i < step) dot.classList.add('done');
    else if (i === step) dot.classList.add('active');
    if (i > 0) {
      var conn = document.getElementById('conn-' + i);
      if (conn) conn.className = 'step-connector' + (i <= step ? ' done' : '');
    }
  });
  var lbl = document.getElementById('stepLabel');
  if (lbl) lbl.textContent = 'Step ' + (step + 1) + ' of ' + QUESTIONS.length;
  var fill = document.getElementById('simProgressFill');
  if (fill) fill.style.width = ((step + 1) / QUESTIONS.length * 100).toFixed(1) + '%';
}

function renderQuestion(step) {
  var q = QUESTIONS[step];
  simStep = step;
  simSelectedIdx = -1;

  var qNum = document.getElementById('qNumber');
  if (qNum) qNum.textContent = 'Question ' + (step + 1) + ' / ' + QUESTIONS.length;
  var qText = document.getElementById('qText');
  if (qText) qText.textContent = q.text;
  var qHint = document.getElementById('qHint');
  if (qHint) qHint.textContent = q.hint;

  var list = document.getElementById('optionsList');
  if (!list) return;
  list.innerHTML = '';

  q.options.forEach(function(opt, i) {
    var el = document.createElement('div');
    el.className = 'sim-option' + (simAnswers[q.id] === i ? ' selected' : '');
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');

    var badgeHtml = '';
    if (opt.badge === 'best')     badgeHtml = '<span class="opt-badge badge-best">Best</span>';
    else if (opt.badge === 'building') badgeHtml = '<span class="opt-badge badge-neutral">Building</span>';
    else if (opt.badge === 'risk')badgeHtml = '<span class="opt-badge badge-risk">Caution</span>';

    el.innerHTML =
      '<div class="opt-radio"></div>' +
      '<div class="opt-content">' +
        '<div class="opt-label">' + opt.label + '</div>' +
        (opt.sub ? '<div class="opt-sub">' + opt.sub + '</div>' : '') +
      '</div>' +
      badgeHtml;

    (function(idx) {
      el.onclick = function() { selectOption(idx); };
      el.onkeydown = function(e) { if (e.key === 'Enter' || e.key === ' ') selectOption(idx); };
    })(i);

    if (simAnswers[q.id] === i) simSelectedIdx = i;
    list.appendChild(el);
  });

  var backBtn = document.getElementById('backBtn');
  if (backBtn) backBtn.style.visibility = step > 0 ? 'visible' : 'hidden';
  updateNextBtn();
  updateStepTracker(step);
}

function selectOption(idx) {
  var q = QUESTIONS[simStep];
  simAnswers[q.id] = idx;
  simSelectedIdx = idx;
  document.querySelectorAll('#optionsList .sim-option').forEach(function(el, i) {
    el.classList.toggle('selected', i === idx);
  });
  updateNextBtn();
}

function updateNextBtn() {
  var btn = document.getElementById('nextBtn');
  if (!btn) return;
  var isLast = simStep === QUESTIONS.length - 1;
  btn.textContent = isLast ? 'Calculate my SCHUFA score \u2605' : 'Continue \u2192';
  btn.classList.toggle('enabled', simSelectedIdx >= 0);
}

function goNext() {
  if (simSelectedIdx < 0) return;
  if (simStep < QUESTIONS.length - 1) {
    animateCardOut(function() { renderQuestion(simStep + 1); animateCardIn(); });
  } else {
    startCalculation();
  }
}

function goBack() {
  if (simStep > 0) {
    animateCardOut(function() { renderQuestion(simStep - 1); animateCardIn(); });
  }
}

function animateCardOut(cb) {
  var card = document.getElementById('questionCard');
  if (!card) { cb(); return; }
  card.classList.add('leaving');
  setTimeout(function() { card.classList.remove('leaving'); cb(); }, 280);
}

function animateCardIn() {
  var card = document.getElementById('questionCard');
  if (!card) return;
  card.style.animation = 'none';
  requestAnimationFrame(function() {
    requestAnimationFrame(function() {
      card.style.animation = 'simCardIn .4s cubic-bezier(.4,0,.2,1)';
    });
  });
}

/* ============================================================
   SCORING ENGINE
============================================================ */
function computeScore() {
  var raw = 0;
  var factors = {};
  var RAW_MIN = -150, RAW_MAX = 770;

  QUESTIONS.forEach(function(q) {
    var idx = simAnswers[q.id];
    if (idx !== undefined) {
      var opt = q.options[idx];
      var pts = opt.score;
      var maxPts = Math.max.apply(null, q.options.map(function(o) { return o.score; }));
      raw += pts;
      factors[q.id] = { pts: pts, maxPts: maxPts, key: opt.key, label: q.text };
    }
  });

  var normalised = Math.max(0, Math.min(1000, Math.round((raw - RAW_MIN) / (RAW_MAX - RAW_MIN) * 1000)));
  return { raw: raw, normalised: normalised, factors: factors };
}

function getScoreProfile(n) {
  if (n >= 880) return { level: 'Excellent',      color: '#00c4a7', desc: 'Your SCHUFA profile is in the top tier. German banks will actively compete for your business. You qualify for credit, mortgages, and premium accounts without issue.',                                                                                                     pills: ['Top 5% in Germany', 'All accounts available', 'Mortgage-eligible'] };
  if (n >= 720) return { level: 'Very Good',       color: '#3ecf8e', desc: 'Strong SCHUFA profile. You qualify for virtually all German bank accounts, most credit cards, and many personal loans. Keep your current behaviour to reach Excellent.',                                                                                                         pills: ['Most loans accessible', 'Credit cards available', 'Keep building'] };
  if (n >= 560) return { level: 'Good',            color: '#c9a84c', desc: 'Solid foundation with room to grow. You can open most accounts and some credit products. A longer banking history and zero missed payments will push you higher.',                                                                                                               pills: ['Standard accounts open', 'Some credit accessible', 'Growth phase'] };
  if (n >= 380) return { level: 'Fair',            color: '#e8a945', desc: 'Your SCHUFA is in the building phase — normal for expats who arrived 6–18 months ago. Digital banks are your best option now. With consistent behaviour, your score will grow significantly in the next 12 months.',                                                             pills: ['Digital banks preferred', 'No credit products yet', '12-month growth window'] };
  if (n >= 180) return { level: 'Limited',         color: '#e8724a', desc: 'Your profile shows limited SCHUFA data — typical for newcomers. Several excellent banks operate without SCHUFA checks. Open one today; it starts counting towards your history immediately.',                                                                                     pills: ['No-SCHUFA banks first', 'Build history now', 'Improve in 6–12 months'] };
  return               { level: 'No SCHUFA Data', color: '#f26d6d', desc: 'You have no SCHUFA history yet — which is completely normal. SCHUFA doesn\'t exist in most countries outside Germany. Several banks specifically welcome newcomers without any credit check at all.',                                                                               pills: ['No record — yet', 'Perfect starting point', 'Multiple banks for you'] };
}

function getBankRecs(n, factors) {
  var dur = factors.duration ? factors.duration.key : '';
  var acc = factors.accounts ? factors.accounts.key : '';

  if (n < 300 || dur === 'new' || acc === 'none') {
    return [
      Object.assign({}, BANKS.n26,   { rank: 1, why: 'No SCHUFA check required. Opens fully online with VideoIdent in 8 minutes — just your passport needed. Every month it\'s open builds your SCHUFA history.' }),
      Object.assign({}, BANKS.vivid, { rank: 2, why: 'No credit check, multi-currency pockets, and cashback. Ideal as a day-to-day account while you build SCHUFA through N26.' }),
      Object.assign({}, BANKS.bunq,  { rank: 3, why: '3-month free trial and no Anmeldung required to apply. Great backup option if your Anmeldung is still processing.' })
    ];
  }
  if (n < 560) {
    return [
      Object.assign({}, BANKS.n26,  { rank: 1, why: 'Still your safest approval. N26 guarantees approval and gives you a reliable base to build from — even with limited history.' }),
      Object.assign({}, BANKS.c24,  { rank: 2, why: 'New German bank with the most lenient SCHUFA requirements in its class. Ideal bridge bank for those with 3–18 months of German history.' }),
      Object.assign({}, BANKS.dkb,  { rank: 3, why: 'Worth applying now. DKB accepts most newcomers with basic history and gives you a full-service German banking relationship from day one.' })
    ];
  }
  if (n < 750) {
    return [
      Object.assign({}, BANKS.dkb, { rank: 1, why: 'Your profile now qualifies you for DKB — the expat community\'s favourite for reliability, free VISA, and excellent customer service.' }),
      Object.assign({}, BANKS.c24, { rank: 2, why: 'Complementary to DKB — instant cashback and a Visa debit in one account. A strong second card for everyday spending.' }),
      Object.assign({}, BANKS.ing, { rank: 3, why: 'Apply now — you may qualify. Germany\'s highest-rated bank by customer satisfaction. If approved, this becomes your long-term primary account.' })
    ];
  }
  return [
    Object.assign({}, BANKS.ing,         { rank: 1, why: 'Your score unlocks Germany\'s best-rated free bank. ING is the destination account for established expats — best conditions, no fees, highest satisfaction.' }),
    Object.assign({}, BANKS.comdirect,   { rank: 2, why: 'The ideal wealth-building companion. Comdirect\'s ETF and savings features are unmatched among free German accounts — pair it with ING.' }),
    Object.assign({}, BANKS.commerzbank, { rank: 3, why: 'You now qualify for premium Commerzbank products. Consider this if you need a branch network, business account, or are planning a mortgage.' })
  ];
}

function getNextSteps(profile, factors) {
  var steps = [];
  var n = profile.normalised;
  var payments = factors.payments ? factors.payments.key : '';
  var dur      = factors.duration  ? factors.duration.key  : '';
  var acc      = factors.accounts  ? factors.accounts.key  : '';
  var anm      = factors.anmeldung ? factors.anmeldung.key : '';

  if (anm === 'no' || anm === 'process')
    steps.push('<strong>Complete your Anmeldung immediately.</strong> Visit your local Bürgeramt within 2 weeks of moving in. This is legally required and unlocks all German financial services. Bring: passport, rental contract, and Wohnungsgeberbestätigung from your landlord.');
  if (acc === 'none')
    steps.push('<strong>Open a no-SCHUFA bank account this week.</strong> N26 or Vivid open within 24 hours, no credit check. Having any German bank account starts building SCHUFA history immediately — every month you wait is a wasted month of potential positive history.');
  if (payments === 'bad')
    steps.push('<strong>Resolve outstanding payments urgently.</strong> Unresolved SCHUFA entries stay on record for 18 months under the new rules. Contact the creditor directly — many will agree to remove the entry in exchange for full payment (<em>Löschungsvereinbarung</em>). Act within 30 days for the best outcome.');
  if (dur === 'new' || dur === 'mid')
    steps.push('<strong>Use a credit card responsibly for 6 months.</strong> After opening your first account, apply for a secured credit card. Make 2–3 small purchases per month and pay the full balance monthly. This single action improves SCHUFA scores faster than anything else for newcomers.');
  if (n < 560)
    steps.push('<strong>Get your free official SCHUFA report.</strong> Once per year, SCHUFA must provide your full credit report for free by law. Visit <em>meineSCHUFA.de → Datenkopie (kostenlos)</em>. Verify there are no errors — even small inaccuracies can significantly damage your score.');
  steps.push('<strong>Read the complete guide on this page.</strong> Our in-depth article above covers every factor, how to dispute entries, the fastest improvement strategies, and what to do when a bank says no. Updated for the March 2026 reform.');
  return steps;
}

/* ============================================================
   CALCULATION FLOW
============================================================ */
function startCalculation() {
  var qs = document.getElementById('quiz-screen');
  var cs = document.getElementById('calcScreen');
  if (qs) qs.style.display = 'none';
  if (cs) cs.style.display = 'block';

  ['cs1','cs2','cs3','cs4','cs5','cs6'].forEach(function(id, i) {
    setTimeout(function() {
      var el = document.getElementById(id);
      if (el) el.classList.add('visible');
    }, i * 400);
  });

  setTimeout(function() {
    simResult = computeScore();
    showResult(simResult);
  }, 3200);
}

/* ============================================================
   RESULT RENDER
============================================================ */
function showResult(result) {
  var cs = document.getElementById('calcScreen');
  var rs = document.getElementById('resultScreen');
  if (cs) cs.style.display = 'none';
  if (rs) rs.style.display = 'block';

  var profile = getScoreProfile(result.normalised);
  setTimeout(function() { animateGauge(result.normalised, profile); }, 300);

  var lvl = document.getElementById('scoreLevelLabel');
  if (lvl) { lvl.textContent = profile.level; lvl.style.color = profile.color; }
  var desc = document.getElementById('scoreDesc');
  if (desc) desc.textContent = profile.desc;

  var pillsEl = document.getElementById('scorePills');
  if (pillsEl) {
    pillsEl.innerHTML = profile.pills.map(function(p) {
      return '<span class="score-pill" style="background:' + profile.color + '18;color:' + profile.color + ';border:1px solid ' + profile.color + '40">' + p + '</span>';
    }).join('');
  }

  renderFactorBars(result.factors, profile);

  var banks = getBankRecs(result.normalised, result.factors);
  renderBanks(banks, profile, result.normalised);
  renderNextSteps(profile, result.factors);

  var topBank = banks[0];
  var sbn = document.getElementById('stickyBankName');
  var scl = document.getElementById('stickyCTALink');
  if (sbn) sbn.textContent = topBank.name;
  if (scl) { scl.href = topBank.url; scl.textContent = topBank.cta + ' \u2192'; }

  setTimeout(function() {
    var bar = document.getElementById('sticky-cta-bar');
    if (bar) bar.classList.add('visible');
  }, 2500);

  /* Scroll to top of simulator section, not top of page */
  var simSec = document.getElementById('simulator-section');
  if (simSec) simSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function animateGauge(score, profile) {
  var ARC_LEN = 251.3;
  var R = 80, cx = 100, cy = 110;
  var pct = score / 1000;
  var offset = ARC_LEN * (1 - pct);

  var fill = document.getElementById('gaugeFill');
  if (fill) fill.style.strokeDashoffset = offset;

  var angle = Math.PI - (pct * Math.PI);
  var nx = cx + R * Math.cos(angle);
  var ny = cy - R * Math.sin(angle);
  var needle = document.getElementById('gaugeNeedle');
  if (needle) {
    needle.setAttribute('cx', nx.toFixed(1));
    needle.setAttribute('cy', ny.toFixed(1));
    needle.style.fill = profile.color;
  }

  var current = 0, target = score, duration = 1800, start = performance.now();
  function step(now) {
    var elapsed = now - start;
    var progress = Math.min(elapsed / duration, 1);
    var ease = 1 - Math.pow(1 - progress, 3);
    current = Math.round(ease * target);
    var gn = document.getElementById('gaugeNum');
    if (gn) gn.textContent = current;
    if (progress < 1) requestAnimationFrame(step);
    else if (gn) gn.textContent = target;
  }
  requestAnimationFrame(step);
}

function renderFactorBars(factors, profile) {
  var config = [
    { id: 'duration',   label: 'Time in Germany',   maxPts: 200 },
    { id: 'employment', label: 'Employment status',  maxPts: 120 },
    { id: 'anmeldung',  label: 'Anmeldung status',   maxPts: 80  },
    { id: 'accounts',   label: 'Banking history',    maxPts: 130 },
    { id: 'payments',   label: 'Payment behaviour',  maxPts: 120 },
    { id: 'credit',     label: 'Credit history',     maxPts: 120 }
  ];
  var container = document.getElementById('factorBars');
  if (!container) return;
  container.innerHTML = '';

  config.forEach(function(fc) {
    var f = factors[fc.id];
    if (!f) return;
    var pts = Math.max(0, f.pts);
    var pct = Math.round((pts / fc.maxPts) * 100);
    var col = pct >= 70 ? '#00c4a7' : pct >= 40 ? '#c9a84c' : '#f26d6d';
    var div = document.createElement('div');
    div.className = 'factor-item';
    div.innerHTML =
      '<div class="factor-label">' + fc.label + '</div>' +
      '<div class="factor-bar-wrap"><div class="factor-bar" style="width:0%;background:' + col + '" data-target="' + pct + '"></div></div>' +
      '<div class="factor-val">' + pct + '%</div>';
    container.appendChild(div);
  });

  setTimeout(function() {
    document.querySelectorAll('.factor-bar[data-target]').forEach(function(bar) {
      bar.style.width = bar.getAttribute('data-target') + '%';
    });
  }, 500);
}

function renderBanks(banks, profile, score) {
  var rt = document.getElementById('recoTitle');
  var rs = document.getElementById('recoSub');
  if (rt) rt.textContent = score < 300 ? 'Best accounts for your situation \u2014 no SCHUFA required' : 'Top-rated accounts for your SCHUFA profile';
  if (rs) rs.textContent = score < 300
    ? 'These banks do not run a SCHUFA check and actively welcome newcomers. Open any of them today \u2014 it counts immediately towards building your history.'
    : 'Ranked by fit with your current SCHUFA profile. All links are affiliate \u2014 we may earn a small commission at no cost to you.';

  var container = document.getElementById('bankCards');
  if (!container) return;
  container.innerHTML = '';

  banks.forEach(function(bank) {
    var card = document.createElement('div');
    card.className = 'bank-card' + (bank.rank === 1 ? ' featured' : '');

    var feats = bank.features.map(function(f) {
      return '<span class="bank-feat"><span class="feat-check">\u2713</span>' + f + '</span>';
    }).join('');

    var rankLabel = bank.rank === 1 ? '\u2605 Best match' : bank.rank === 2 ? '#2 Pick' : '#3 Option';

    card.innerHTML =
      '<div class="bank-top">' +
        '<div><div class="bank-name">' + bank.name + '</div><div class="bank-tagline">' + bank.tagline + '</div></div>' +
        '<span class="bank-rank-badge rank-' + bank.rank + '">' + rankLabel + '</span>' +
      '</div>' +
      '<div class="bank-features">' + feats + '</div>' +
      '<div class="bank-why-box">' + bank.why + '</div>' +
      '<div class="bank-bottom">' +
        '<span style="font-size:.82rem;color:var(--text-muted)">' + bank.fee + ' &nbsp;&middot;&nbsp; ' + bank.schufa + ' &nbsp;&middot;&nbsp; ' + bank.time + '</span>' +
        '<a href="' + bank.url + '" target="_blank" rel="noopener sponsored" class="bank-cta ' + bank.ctaStyle + '">' + bank.cta + ' &rarr;</a>' +
      '</div>';

    container.appendChild(card);
  });
}

function renderNextSteps(profile, factors) {
  var steps = getNextSteps(profile, factors);
  var card = document.getElementById('nextStepsCard');
  if (!card) return;
  card.innerHTML =
    '<div class="next-steps-title">Your personalised action plan</div>' +
    steps.map(function(s, i) {
      return '<div class="next-step-item"><div class="step-num-circle">' + (i + 1) + '</div><div class="next-step-text">' + s + '</div></div>';
    }).join('');
}

function restartQuiz() {
  simAnswers = {};
  simSelectedIdx = -1;
  simResult = null;
  simStep = 0;
  var rs = document.getElementById('resultScreen');
  var cs = document.getElementById('calcScreen');
  var qs = document.getElementById('quiz-screen');
  var bar = document.getElementById('sticky-cta-bar');
  var calcSteps = document.querySelectorAll('.calc-step');
  if (rs) rs.style.display = 'none';
  if (cs) { cs.style.display = 'none'; }
  if (qs) qs.style.display = 'block';
  if (bar) bar.classList.remove('visible');
  calcSteps.forEach(function(el) { el.classList.remove('visible'); });
  renderQuestion(0);
  var simSec = document.getElementById('simulator-section');
  if (simSec) simSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function scrollToSim() {
  var s = document.getElementById('simulator-section');
  if (s) s.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ============================================================
   WIRE UP SIMULATOR BUTTONS
============================================================ */
document.addEventListener('DOMContentLoaded', function() {
  var nextBtn  = document.getElementById('nextBtn');
  var backBtn  = document.getElementById('backBtn');
  var restartBtn = document.getElementById('restartBtn');
  if (nextBtn)    nextBtn.addEventListener('click', goNext);
  if (backBtn)    backBtn.addEventListener('click', goBack);
  if (restartBtn) restartBtn.addEventListener('click', restartQuiz);
  simInit();
});

/* ============================================================
   ARTICLE UTILS
============================================================ */
/* Progress bar */
window.addEventListener('scroll', function() {
  var el = document.getElementById('progressBar');
  if (!el) return;
  var h = document.documentElement.scrollHeight - window.innerHeight;
  if (h > 0) el.style.width = Math.min(window.scrollY / h * 100, 100) + '%';
});

/* Sticky header */
window.addEventListener('scroll', function() {
  var hdr = document.querySelector('.global-header');
  if (hdr) hdr.classList.toggle('sticky', window.scrollY > 10);
});

/* Mobile nav */
var nt = document.getElementById('navToggle');
var nl = document.getElementById('navLinks');
if (nt && nl) nt.addEventListener('click', function() { nl.classList.toggle('open'); });

/* FAQ accordion */
function toggleFaq(btn) {
  var answer = btn.nextElementSibling;
  var isOpen = btn.getAttribute('aria-expanded') === 'true';
  document.querySelectorAll('.faq-q').forEach(function(b) {
    b.setAttribute('aria-expanded', 'false');
    if (b.nextElementSibling) b.nextElementSibling.classList.remove('open');
  });
  if (!isOpen) {
    btn.setAttribute('aria-expanded', 'true');
    answer.classList.add('open');
  }
}

/* Cookie */
function openModal(id) { var m = document.getElementById('modal-' + id); if (m) m.classList.add('open'); }
function closeModal(id){ var m = document.getElementById('modal-' + id); if (m) m.classList.remove('open'); }
function hideCookieBanner() { var b = document.getElementById('cookie-banner'); if (b) b.style.display = 'none'; }
function acceptCookies()  { localStorage.setItem('es_consent','all');       hideCookieBanner(); }
function declineCookies() { localStorage.setItem('es_consent','essential'); hideCookieBanner(); }

document.addEventListener('DOMContentLoaded', function() {
  if (!localStorage.getItem('es_consent')) {
    setTimeout(function() {
      var b = document.getElementById('cookie-banner');
      if (b) b.style.display = 'flex';
    }, 1200);
  }

  var ca  = document.getElementById('cookieAcceptBtn');
  var cd  = document.getElementById('cookieDeclineBtn');
  var csb = document.getElementById('cookieSettingsBtn');
  var csl = document.getElementById('cookieSettingsLink');
  var cmc = document.getElementById('cookieModalClose');
  var csv = document.getElementById('cookieSaveBtn');
  var mo  = document.querySelector('.modal-overlay');

  if (ca)  ca.addEventListener('click',  acceptCookies);
  if (cd)  cd.addEventListener('click',  declineCookies);
  if (csb) csb.addEventListener('click', function() { openModal('cookie-settings'); });
  if (csl) csl.addEventListener('click', function(e) { e.preventDefault(); openModal('cookie-settings'); });
  if (cmc) cmc.addEventListener('click', function() { closeModal('cookie-settings'); });
  if (mo)  mo.addEventListener('click',  function(e) { if (e.target === this) this.classList.remove('open'); });
  if (csv) csv.addEventListener('click', function() {
    var a = document.getElementById('toggle-analytics');
    var f = document.getElementById('toggle-affiliate');
    localStorage.setItem('es_consent', JSON.stringify({ necessary: true, analytics: a && a.checked, affiliate: f && f.checked }));
    hideCookieBanner();
    closeModal('cookie-settings');
  });
});
