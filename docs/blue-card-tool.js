// ══════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════
const state = {
  qualType: null,     // 'degree' | 'it' | 'vocational' | 'none'
  occType: null,      // 'shortage' | 'standard'
  recentGrad: null,   // true | false
  itChecks: [null, null, null],
  salary: 0,
  period: 'annual',
  track: null,        // 'standard' | 'shortage' | 'graduate' | 'it'
  threshold: 0,
};

const THRESHOLDS = {
  standard: 50700,
  shortage: 45934.20,
  graduate: 45934.20,
  it:       45934.20,
};

const TRACK_LABELS = {
  standard: { label: 'Standard Track',  pill: 'standard',  css: 'standard'  },
  shortage: { label: 'Shortage Track',  pill: 'shortage',  css: 'shortage'  },
  graduate: { label: 'Graduate Track',  pill: 'graduate',  css: 'graduate'  },
  it:       { label: 'IT Specialist',   pill: 'it',        css: 'it'        },
};

// ══════════════════════════════════════════════
//  STEP NAVIGATION
// ══════════════════════════════════════════════
let currentStep = 1;

function showStep(id) {
  document.querySelectorAll('.step-panel').forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
  const panel = document.getElementById(id);
  panel.style.display = 'block';
  panel.classList.add('active');
  updateProgress();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateProgress() {
  const stepNum = currentStep <= 4 ? currentStep : 4;
  ['1','2','3','4'].forEach(n => {
    const dot = document.getElementById(`dot-${n}`);
    const num = parseInt(n);
    dot.classList.remove('active','done');
    if (num < stepNum)       dot.classList.add('done');
    else if (num === stepNum) dot.classList.add('active');
  });
  ['12','23','34'].forEach(k => {
    const line = document.getElementById(`line-${k}`);
    if (!line) return;
    const stepOf = parseInt(k[0]);
    line.classList.toggle('done', stepOf < stepNum);
  });
  const labels = { 1:'Step 1 of 4 — Qualification', 2:'Step 2 of 4 — Occupation & Experience', 3:'Step 3 of 4 — Salary', 4:'Your Eligibility Passport' };
  document.getElementById('progressLabel').textContent = labels[stepNum] || '';
}

// ══════════════════════════════════════════════
//  STEP 1 — QUALIFICATION
// ══════════════════════════════════════════════
function selectQual(type) {
  state.qualType = type;
  document.querySelectorAll('.qual-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`q-${type}`).classList.add('selected');
  document.getElementById('btn1').disabled = false;
}

function goToStep2() {
  if (!state.qualType) return;
  currentStep = 2;
  if (state.qualType === 'degree') {
    showStep('step2a');
  } else if (state.qualType === 'it') {
    showStep('step2b');
  } else {
    showStep('step2c');
  }
}

// ══════════════════════════════════════════════
//  STEP 2A — DEGREE: OCCUPATION + GRAD DATE
// ══════════════════════════════════════════════
function setGradRecent(val) {
  state.recentGrad = val;
  document.getElementById('grad-yes').classList.toggle('active-yes', val === true);
  document.getElementById('grad-no').classList.toggle('active-no',  val === false);
  if (val === true) {
    state.occType = 'shortage'; // recent grads get reduced threshold on any occupation
    document.getElementById('occ-section').style.opacity = '0.45';
    document.getElementById('occ-section').style.pointerEvents = 'none';
    document.getElementById('step2a-context').innerHTML =
      'You are a <strong>recent graduate (≤ 3 years)</strong> — you automatically qualify for the reduced threshold of <strong>€45,934.20/year</strong>, regardless of your occupation.';
  } else {
    state.occType = null;
    document.getElementById('occ-section').style.opacity = '1';
    document.getElementById('occ-section').style.pointerEvents = 'auto';
    document.getElementById('step2a-context').innerHTML =
      'Let\'s determine your salary threshold. <strong>Shortage occupations get the reduced rate.</strong>';
    // Unselect all chips
    document.querySelectorAll('.occ-chip').forEach(c => c.classList.remove('selected'));
  }
  checkStep2aComplete();
}

function selectOcc(el, type) {
  if (state.recentGrad === true) return;
  document.querySelectorAll('.occ-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected', type);
  state.occType = type;
  checkStep2aComplete();
}

function checkStep2aComplete() {
  const ready = state.recentGrad === true || (state.recentGrad !== null && state.occType !== null);
  document.getElementById('btn2a').disabled = !ready;
}

function goToStep3() {
  currentStep = 3;
  // Determine track
  if (state.qualType === 'it') {
    state.track = 'it';
  } else if (state.recentGrad === true) {
    state.track = 'graduate';
  } else if (state.occType === 'shortage') {
    state.track = 'shortage';
  } else {
    state.track = 'standard';
  }
  state.threshold = THRESHOLDS[state.track];
  updateStep3UI();
  showStep('step3');
}

// ══════════════════════════════════════════════
//  STEP 2B — IT SPECIALIST
// ══════════════════════════════════════════════
function setIT(qNum, val) {
  state.itChecks[qNum - 1] = val;
  const yesBtn = document.getElementById(`it${qNum}-yes`);
  const noBtn  = document.getElementById(`it${qNum}-no`);
  yesBtn.classList.toggle('yes-active', val === true);
  noBtn.classList.toggle('no-active',  val === false);

  const allAnswered = state.itChecks.every(v => v !== null);
  const allYes      = state.itChecks.every(v => v === true);
  const hasNo       = state.itChecks.some(v => v === false);

  document.getElementById('it-warning').style.display = (allAnswered && hasNo) ? 'block' : 'none';
  document.getElementById('btn2b').disabled = !(allAnswered && allYes);
}

function goBack(toStep) {
  currentStep = toStep;
  if (toStep === 1) showStep('step1');
  else if (toStep === 2) {
    if (state.qualType === 'degree') showStep('step2a');
    else showStep('step2b');
  }
}

// ══════════════════════════════════════════════
//  STEP 3 — SALARY
// ══════════════════════════════════════════════
function updateStep3UI() {
  const trackInfo = TRACK_LABELS[state.track];
  const threshold = state.threshold;
  document.getElementById('step3-q').textContent =
    state.qualType === 'it'
      ? 'What is the gross annual salary in your IT job offer?'
      : 'What is the gross annual salary in your offer?';

  const contextMap = {
    standard: `Your track: <strong>Standard Occupation</strong>. Salary must reach <strong>€50,700/year gross</strong> to qualify.`,
    shortage: `Your track: <strong>Shortage Occupation</strong>. The reduced threshold applies: <strong>€45,934.20/year gross</strong>.`,
    graduate: `Your track: <strong>Recent Graduate</strong>. You get the reduced threshold: <strong>€45,934.20/year gross</strong>, on any occupation.`,
    it:       `Your track: <strong>IT Specialist</strong>. The shortage threshold applies: <strong>€45,934.20/year gross</strong>.`,
  };
  document.getElementById('step3-context').textContent = `(${trackInfo.label})`;

  // Reset gauge
  const fill = document.getElementById('gaugeFill');
  fill.style.strokeDasharray = '0 314';
  fill.style.stroke = '#3a4550';
  document.getElementById('gaugeValText').textContent = '—';
  document.getElementById('gaugeValText').setAttribute('fill', '#5c6b7a');
  document.getElementById('salaryInput').value = '';
  document.getElementById('btn3').disabled = true;
}

function setPeriod(p) {
  state.period = p;
  document.getElementById('btn-annual').classList.toggle('active', p === 'annual');
  document.getElementById('btn-monthly').classList.toggle('active', p === 'monthly');
  updateSalary();
}

// Full arc length of the 270° gauge path (radius 84, angle 270°)
const GAUGE_ARC = 2 * Math.PI * 84 * (270/360); // ≈ 395

function updateSalary() {
  const raw = parseFloat(document.getElementById('salaryInput').value) || 0;
  const annual = state.period === 'monthly' ? raw * 12 : raw;
  state.salary = annual;

  const thresh  = state.threshold;
  const pct     = Math.min(annual / thresh, 1.15); // cap display at 115%
  const arcFill = pct * GAUGE_ARC;

  const fill = document.getElementById('gaugeFill');
  fill.style.strokeDasharray = `${arcFill} ${GAUGE_ARC}`;

  const gap = annual - thresh;
  const borderline = gap >= -thresh * 0.10 && gap < 0; // within 10% below

  let color, valFill;
  if (annual <= 0) { color = '#3a4550'; valFill = '#5c6b7a'; }
  else if (annual >= thresh) { color = '#00c4a7'; valFill = '#00c4a7'; }
  else if (borderline)       { color = '#c9a84c'; valFill = '#c9a84c'; }
  else                       { color = '#3a4550'; valFill = '#8b949e'; }

  fill.style.stroke = color;

  const valEl = document.getElementById('gaugeValText');
  valEl.textContent = annual > 0 ? '€' + Math.round(annual/1000) + 'k' : '—';
  valEl.setAttribute('fill', valFill);

  // Feedback
  const fb = document.getElementById('salaryFeedback');
  fb.classList.remove('below','borderline','above');
  if (annual <= 0) {
    fb.classList.add('below');
    fb.textContent = 'Enter your salary above to see your eligibility.';
    document.getElementById('btn3').disabled = true;
  } else if (annual >= thresh) {
    fb.classList.add('above');
    const surplus = (annual - thresh).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
    fb.innerHTML = `<strong>✓ Your offer exceeds the threshold by €${surplus}</strong> — you meet the salary requirement for the EU Blue Card.`;
    document.getElementById('btn3').disabled = false;
  } else if (borderline) {
    fb.classList.add('borderline');
    const shortfall = Math.abs(gap).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
    fb.innerHTML = `<strong>⚡ Very close — you are €${shortfall} below the threshold.</strong> Guaranteed bonuses in your contract may close the gap. See tips on the next screen.`;
    document.getElementById('btn3').disabled = false;
  } else {
    fb.classList.add('below');
    const shortfall = Math.abs(gap).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
    fb.innerHTML = `Your offer is €${shortfall} below the threshold. A salary increase or renegotiation would be needed.`;
    document.getElementById('btn3').disabled = false;
  }
}

// ══════════════════════════════════════════════
//  STEP 4 — RESULT
// ══════════════════════════════════════════════
function goToResult() {
  currentStep = 4;
  buildPassport();
  showStep('step4');
  if (state.salary >= state.threshold) spawnConfetti();
}

function buildPassport() {
  const thresh  = state.threshold;
  const salary  = state.salary;
  const gap     = salary - thresh;
  const eligible   = gap >= 0;
  const borderline = gap >= -thresh * 0.10 && gap < 0;
  const ineligible = gap < -thresh * 0.10;

  const trackInfo = TRACK_LABELS[state.track];

  // Date
  document.getElementById('passportDate').textContent =
    new Date().toLocaleDateString('en-GB', {day:'2-digit', month:'short', year:'numeric'});

  // Status
  const icon    = document.getElementById('statusIcon');
  const verdict = document.getElementById('statusVerdict');
  const trackPill = document.getElementById('statusTrackPill');

  icon.className = 'status-icon-wrap';
  verdict.className = 'status-verdict';

  if (eligible) {
    icon.classList.add('eligible');
    icon.textContent = '✓';
    verdict.classList.add('eligible');
    verdict.textContent = 'Eligible — You qualify for the EU Blue Card';
  } else if (borderline) {
    icon.classList.add('borderline');
    icon.textContent = '⚡';
    verdict.classList.add('borderline');
    verdict.textContent = 'Borderline — Very close, see bridging options';
  } else {
    icon.classList.add('ineligible');
    icon.textContent = '✗';
    verdict.classList.add('ineligible');
    verdict.textContent = 'Not yet eligible — Salary below threshold';
  }

  trackPill.textContent = trackInfo.label;
  trackPill.className = `track-pill ${trackInfo.css}`;

  // Salary bar
  const barPct = Math.min((salary / thresh) * 100, 100);
  const barFill = document.getElementById('salaryBarFill');
  barFill.className = 'salary-bar-fill ' + (eligible ? 'above' : borderline ? 'borderline' : 'below');
  setTimeout(() => { barFill.style.width = barPct + '%'; }, 200);

  document.getElementById('barThresholdLabel').textContent = `← €${(thresh/1000).toFixed(1)}k threshold`;
  document.getElementById('resOfferVal').textContent   = '€' + salary.toLocaleString('de-DE', {maximumFractionDigits:0}) + '/yr';
  document.getElementById('resThresholdVal').textContent = '€' + thresh.toLocaleString('de-DE', {minimumFractionDigits:2}) + '/yr';

  const gapEl    = document.getElementById('resGapVal');
  const gapLabel = document.getElementById('resGapLabel');
  if (eligible) {
    gapLabel.textContent = 'Surplus';
    gapEl.className = 'sal-num-val gap positive';
    gapEl.textContent = '+€' + gap.toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
  } else {
    gapLabel.textContent = 'Shortfall';
    gapEl.className = 'sal-num-val gap negative';
    gapEl.textContent = '−€' + Math.abs(gap).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
  }

  // Borderline section
  document.getElementById('borderlineSection').style.display = borderline ? 'block' : 'none';

  // Benefits (always shown for eligible/borderline)
  document.getElementById('benefitsSection').style.display = ineligible ? 'none' : 'block';
  document.getElementById('timelineSection').style.display = ineligible ? 'none' : 'block';

  // PR timeline
  document.getElementById('prFinalMonths').textContent =
    state.track === 'shortage' ? '21 months (B1) / 33 without' : '21 months (B1) / 33 without';

  // Next steps
  buildNextSteps(eligible, borderline, ineligible);

  // Share links
  const shareUrl = encodeURIComponent('https://expatscore.de/legal/blue-card-tool');
  const track    = trackInfo.label;
  const shareText = eligible
    ? encodeURIComponent(`I just checked my EU Blue Card eligibility for Germany 2026 — I qualify on the ${track}! Free tool by @ExpatScore:`)
    : encodeURIComponent(`Just used this free EU Blue Card eligibility tool for Germany 2026. Takes 2 min — shows your exact threshold, track, and next steps:`)
  document.getElementById('shareLinkedIn').href = `https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`;
  document.getElementById('shareTwitter').href  = `https://twitter.com/intent/tweet?text=${shareText}&url=${shareUrl}`;
}

function buildNextSteps(eligible, borderline, ineligible) {
  const container = document.getElementById('nextSteps');
  const steps = [];

  if (eligible) {
    steps.push({ title:'Apply for your German employment visa', desc:'Contact the German embassy in your country. Processing: 6–20 weeks.', link:'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card' });
    steps.push({ title:'Get your Steuer-ID (Tax ID)', desc:'Register your address (Anmeldung) within 14 days of arriving. Your Tax ID is automatically sent.', link:'/legal/steuer-id-guide' });
    steps.push({ title:'Open your German bank account', desc:'N26 is the fastest option — English app, BaFin-licensed, SCHUFA-building DE-IBAN.', link:'/banking/n26-bank-erfahrungen' });
    steps.push({ title:'Enroll in TK health insurance', desc:'Apply before your employment start date. Employer pays half your contribution.', link:'/insurance/tk-health-insurance' });
    steps.push({ title:'Start building your SCHUFA score', desc:'Your first bank account and mobile contract build your German credit history from day one.', link:'/guides/schufa-guide' });
  } else if (borderline) {
    steps.push({ title:'Negotiate guaranteed bonuses into your contract', desc:'Christmas or holiday bonuses count toward the threshold if contractually guaranteed — not discretionary.', link:'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card' });
    steps.push({ title:'Check if your role qualifies as a shortage occupation', desc:'If your occupation is on Germany\'s shortage list, you may already qualify at the lower threshold.', link:'https://expatscore.de/legal/blue-card-tool' });
    steps.push({ title:'Consider a part-time-to-full-time contract upgrade', desc:'If the offer is for reduced hours, a full-time contract may push you above the threshold.', link:'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card' });
    steps.push({ title:'Prepare your documents now while negotiating', desc:'Qualification recognition, degree translations, and work references can take months. Start now.', link:'https://anabin.kmk.org/anabin' });
  } else {
    steps.push({ title:'Explore the Skilled Worker Visa (§18a AufenthG)', desc:'Lower salary requirements than the Blue Card. Requires recognised vocational or academic qualification.', link:'https://www.make-it-in-germany.com/en/visa-residence/types/skilled-workers-with-vocational-training' });
    steps.push({ title:'Consider the Opportunity Card (Chancenkarte)', desc:'Job-seeker visa valid for 1 year. Find a suitable role in Germany, then convert to a work permit.', link:'https://www.make-it-in-germany.com/en/visa-residence/types/opportunity-card' });
    steps.push({ title:'Build your qualifications portfolio', desc:'IT certifications, portfolio work, or a postgraduate degree may open new pathways.', link:'https://www.make-it-in-germany.com' });
  }

  container.innerHTML = steps.map((s, i) => `
    <a class="next-step" href="${s.link}" ${s.link.startsWith('http') ? 'target="_blank" rel="noopener"' : ''}>
      <div class="next-step-num">${i + 1}</div>
      <div class="next-step-text"><strong>${s.title}</strong>${s.desc}</div>
      <span class="next-step-arrow">→</span>
    </a>
  `).join('');
}

// ══════════════════════════════════════════════
//  CONFETTI
// ══════════════════════════════════════════════
function spawnConfetti() {
  const container = document.getElementById('confettiContainer');
  const colors = ['#c9a84c','#00c4a7','#e4c97a','#33d4bb','#ffffff','#4a9eff','#3ecf8e'];
  for (let i = 0; i < 80; i++) {
    setTimeout(() => {
      const el = document.createElement('div');
      el.className = 'confetti-piece';
      el.style.cssText = `
        left: ${Math.random()*100}%;
        top: -10px;
        background: ${colors[Math.floor(Math.random()*colors.length)]};
        animation-delay: ${Math.random()*1}s;
        animation-duration: ${2 + Math.random()*1.5}s;
        border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
        width: ${6 + Math.random()*6}px;
        height: ${6 + Math.random()*6}px;
        transform: rotate(${Math.random()*360}deg);
      `;
      container.appendChild(el);
      setTimeout(() => el.remove(), 4000);
    }, i * 25);
  }
}

// ══════════════════════════════════════════════
//  UTILITIES
// ══════════════════════════════════════════════
function copyLink() {
  navigator.clipboard.writeText('https://expatscore.de/legal/blue-card-tool')
    .then(() => { alert('Link copied to clipboard!'); })
    .catch(() => { alert('Copy: https://expatscore.de/legal/blue-card-tool'); });
}

function restartWizard() {
  Object.assign(state, { qualType:null, occType:null, recentGrad:null, itChecks:[null,null,null], salary:0, period:'annual', track:null, threshold:0 });
  currentStep = 1;
  document.querySelectorAll('.qual-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll('.occ-chip').forEach(c => c.classList.remove('selected','shortage','standard'));
  document.getElementById('btn1').disabled = true;
  document.getElementById('grad-yes').classList.remove('active-yes');
  document.getElementById('grad-no').classList.remove('active-no');
  document.getElementById('occ-section').style.opacity = '1';
  document.getElementById('occ-section').style.pointerEvents = 'auto';
  ['it1','it2','it3'].forEach(k => {
    document.getElementById(`${k}-yes`).classList.remove('yes-active');
    document.getElementById(`${k}-no`).classList.remove('no-active');
  });
  showStep('step1');
}

// ══════════════════════════════════════════════
//  COOKIE
// ══════════════════════════════════════════════
function openModal(id)  { const m=document.getElementById('modal-'+id); if(m) m.classList.add('open'); }
function closeModal(id) { const m=document.getElementById('modal-'+id); if(m) m.classList.remove('open'); }
function acceptCookies()  { localStorage.setItem('cookieConsent','all');       document.getElementById('cookie-banner').style.display='none'; closeModal('cookie-settings'); }
function declineCookies() { localStorage.setItem('cookieConsent','necessary'); document.getElementById('cookie-banner').style.display='none'; closeModal('cookie-settings'); }
function saveGranularCookies() { localStorage.setItem('cookieConsent','necessary'); document.getElementById('cookie-banner').style.display='none'; closeModal('cookie-settings'); }
(function(){ if(localStorage.getItem('cookieConsent')) document.getElementById('cookie-banner').style.display='none'; })();

// ══════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════
updateProgress();
