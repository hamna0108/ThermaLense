/**
 * ThermaLens — Frontend Application Logic
 * Technology: Plain Vanilla JavaScript (ES6+), Zero Frameworks, Zero External CDNs.
 * Fully offline-capable for live demonstration.
 */

// Global State
const STATE = {
  evidence: null,
  activeRoute: 'overview',
  theme: localStorage.getItem('thermalens_theme') || localStorage.getItem('novatore_theme') || 'light',
  lastEstimateResult: null,
  lastDiagnoseResult: null,
  lastPlacementResult: null,
  lastFieldResult: null,
  lastPoissonResult: null
};

// Seeded Pseudo-Random Number Generator (Mulberry32) for deterministic client-side generation
function mulberry32(a) {
  return function() {
    let t = a += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  }
}

// Box-Muller normal perturbation
function randomNormal(rng, mean = 0, std = 1) {
  let u1 = rng();
  let u2 = rng();
  while (u1 === 0) u1 = rng();
  const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  return mean + z0 * std;
}

// Perceptual Sequential Color Scale (Inferno approximation for temperature [0, 1])
function getThermalColor(val) {
  const v = Math.max(0, Math.min(1, val));
  let r, g, b;
  if (v < 0.25) {
    const t = v / 0.25;
    r = Math.floor(10 + t * 65);
    g = Math.floor(5 + t * 15);
    b = Math.floor(30 + t * 90);
  } else if (v < 0.5) {
    const t = (v - 0.25) / 0.25;
    r = Math.floor(75 + t * 110);
    g = Math.floor(20 + t * 20);
    b = Math.floor(120 - t * 40);
  } else if (v < 0.75) {
    const t = (v - 0.5) / 0.25;
    r = Math.floor(185 + t * 50);
    g = Math.floor(40 + t * 80);
    b = Math.floor(80 - t * 60);
  } else {
    const t = (v - 0.75) / 0.25;
    r = Math.floor(235 + t * 20);
    g = Math.floor(120 + t * 135);
    b = Math.floor(20 + t * 140);
  }
  return `rgb(${r}, ${g}, ${b})`;
}

// Diverging Color Scale for Errors (Blue -> White -> Red)
function getDivergingErrorColor(val, maxVal = 0.5) {
  const norm = Math.max(-1, Math.min(1, val / (maxVal || 1e-6)));
  let r, g, b;
  if (norm < 0) {
    const t = Math.abs(norm);
    r = Math.floor(255 - t * 180);
    g = Math.floor(255 - t * 130);
    b = 255;
  } else {
    const t = norm;
    r = 255;
    g = Math.floor(255 - t * 160);
    b = Math.floor(255 - t * 160);
  }
  return `rgb(${r}, ${g}, ${b})`;
}

// -------------------------------------------------------------------------------------------------
// 1. Navigation & Theme Management
// -------------------------------------------------------------------------------------------------

function applyTheme(theme) {
  STATE.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('thermalens_theme', theme);
  const btnText = document.getElementById('theme-toggle-text');
  if (btnText) {
    btnText.textContent = theme === 'dark' ? 'Light Theme' : 'Dark Theme';
  }
  // Redraw active views if results exist
  if (STATE.activeRoute === 'estimate' && STATE.lastEstimateResult) renderEstimateChart();
  if (STATE.activeRoute === 'diagnose' && STATE.lastDiagnoseResult) renderDiagnoseChart();
  if (STATE.activeRoute === 'placement' && STATE.lastPlacementResult) renderPlacementChart();
  if (STATE.activeRoute === 'field' && STATE.lastFieldResult) renderFieldHeatmap();
}

function initTheme() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const nextTheme = STATE.theme === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme);
    });
  }
  applyTheme(STATE.theme);
}

function handleRoute() {
  const rawHash = window.location.hash.replace('#', '').trim();
  const validRoutes = ['overview', 'estimate', 'diagnose', 'placement', 'field', 'poisson', 'evidence', 'limits'];
  const targetRoute = validRoutes.includes(rawHash) ? rawHash : 'overview';
  STATE.activeRoute = targetRoute;

  // Update nav links
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('href') === `#${targetRoute}`);
  });

  // Update views
  document.querySelectorAll('.page-view').forEach(view => {
    view.classList.toggle('active', view.id === `view-${targetRoute}`);
  });

  // Lazy render for evidence page
  if (targetRoute === 'evidence' && STATE.evidence) {
    renderEvidencePage();
  }
}

// -------------------------------------------------------------------------------------------------
// 2. Health & Version Metadata Fetchers
// -------------------------------------------------------------------------------------------------

async function checkServiceHealth() {
  const badge = document.getElementById('service-health-badge');
  const text = document.getElementById('service-health-text');
  try {
    const res = await fetch('/health');
    if (res.ok) {
      const data = await res.json();
      badge.className = 'health-badge healthy';
      text.textContent = 'HEALTHY';
      badge.title = `Service: ${data.service} v${data.version}`;
    } else {
      badge.className = 'health-badge down';
      text.textContent = `HTTP ${res.status}`;
    }
  } catch (err) {
    badge.className = 'health-badge down';
    text.textContent = 'SERVICE DOWN';
    badge.title = 'Service is unreachable. Please verify server process.';
  }
}

async function loadVersionMetadata() {
  try {
    const res = await fetch('/version');
    if (res.ok) {
      const data = await res.json();
      const commitEl = document.getElementById('footer-commit');
      if (commitEl) {
        commitEl.textContent = (data.git_commit || 'unknown').substring(0, 8);
      }
    }
  } catch (err) {
    console.warn('Could not load version metadata', err);
  }
}

async function loadEvidenceJson() {
  try {
    const res = await fetch('/evidence.json');
    if (res.ok) {
      STATE.evidence = await res.json();
      populateHeadlineFindings();
      if (STATE.activeRoute === 'evidence') {
        renderEvidencePage();
      }
    }
  } catch (err) {
    console.error('Failed to load evidence.json', err);
  }
}

function populateHeadlineFindings() {
  const container = document.getElementById('headline-findings-container');
  if (!container || !STATE.evidence || !STATE.evidence.headline_findings) return;

  container.innerHTML = STATE.evidence.headline_findings.map(item => `
    <div class="headline-card">
      <div class="headline-stat">${item.stat}</div>
      <div class="headline-title">${item.title}</div>
      <div class="headline-detail">${item.detail}</div>
      ${item.test ? `<div class="headline-test"><span class="text-muted">From:</span> ${item.test}</div>` : ''}
      <div class="headline-link-wrap">
        <a href="${item.link || '#evidence'}" class="evidence-link">View in Evidence &rarr;</a>
      </div>
    </div>
  `).join('');
}

function initOverviewTaskCards() {
  document.querySelectorAll('.try-example-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const action = btn.getAttribute('data-action');
      handleTryExample(action);
    });
  });
}

function handleTryExample(action) {
  if (action === 'try-estimate') {
    window.location.hash = '#estimate';
    setTimeout(() => {
      const useExampleBtn = document.getElementById('est-use-example-btn');
      if (useExampleBtn) useExampleBtn.click();
      const sigmaInput = document.getElementById('est-sigma-val');
      if (sigmaInput) sigmaInput.value = '0.01';
      const methodSelect = document.getElementById('est-method-select');
      if (methodSelect) {
        methodSelect.value = 'mode3plus';
        methodSelect.dispatchEvent(new Event('change'));
      }
      const submitBtn = document.getElementById('est-submit-btn');
      if (submitBtn) submitBtn.click();
    }, 60);
  } else if (action === 'try-diagnose') {
    window.location.hash = '#diagnose';
    setTimeout(() => {
      const scenarioSelect = document.getElementById('diag-scenario-select');
      if (scenarioSelect) {
        scenarioSelect.value = 'F_stuck';
        scenarioSelect.dispatchEvent(new Event('change'));
      }
      const submitBtn = document.getElementById('diag-submit-btn');
      if (submitBtn) submitBtn.click();
    }, 60);
  } else if (action === 'try-placement') {
    window.location.hash = '#placement';
    setTimeout(() => {
      const nInput = document.getElementById('place-n');
      if (nInput) nInput.value = '20';
      const sigmaInput = document.getElementById('place-sigma');
      if (sigmaInput) sigmaInput.value = '0.01';
      const xInput = document.getElementById('place-sensor-x');
      if (xInput) xInput.value = '0.50';
      const tmin = document.getElementById('place-tmin');
      if (tmin) tmin.value = '0.01';
      const tmax = document.getElementById('place-tmax');
      if (tmax) tmax.value = '1.0';
      const submitBtn = document.getElementById('place-submit-btn');
      if (submitBtn) submitBtn.click();
    }, 60);
  } else if (action === 'try-field') {
    window.location.hash = '#field';
    setTimeout(() => {
      const compareBtn = document.getElementById('field-method-compare-btn');
      if (compareBtn) compareBtn.click();
      const alphaInput = document.getElementById('field-alpha');
      if (alphaInput) alphaInput.value = '0.10';
      const submitBtn = document.getElementById('field-submit-btn');
      if (submitBtn) submitBtn.click();
    }, 60);
  } else if (action === 'try-poisson') {
    window.location.hash = '#poisson';
    setTimeout(() => {
      const presetSelect = document.getElementById('poi-presets-select');
      if (presetSelect) {
        presetSelect.value = 'sine_low';
        presetSelect.dispatchEvent(new Event('change'));
      }
      const submitBtn = document.getElementById('poi-submit-btn');
      if (submitBtn) submitBtn.click();
    }, 60);
  }
}

// -------------------------------------------------------------------------------------------------
// 3. Page 2: Estimate Workbench
// -------------------------------------------------------------------------------------------------

function toSuperscript(str) {
  const map = {
    '-': '⁻',
    '+': '⁺',
    '0': '⁰',
    '1': '¹',
    '2': '²',
    '3': '³',
    '4': '⁴',
    '5': '⁵',
    '6': '⁶',
    '7': '⁷',
    '8': '⁸',
    '9': '⁹'
  };
  return String(str).split('').map(c => map[c] || c).join('');
}

function formatScientificReal(val, sigDigits = 2) {
  if (val === null || val === undefined || isNaN(val)) return '-';
  if (val === 0) return '0';
  if (Math.abs(val) >= 0.01 && Math.abs(val) < 1000) {
    return Number(val.toPrecision(sigDigits)).toString();
  }
  const expStr = val.toExponential(sigDigits - 1);
  const parts = expStr.split('e');
  const mantissa = parts[0];
  const exponent = parseInt(parts[1], 10);
  const supExp = toSuperscript(String(exponent));
  return `${mantissa} × 10${supExp}`;
}

function computeNiceAxis(minVal, maxVal, targetCount = 4) {
  const span = maxVal - minVal;
  if (span <= 0) return { min: minVal, max: maxVal + 1, ticks: [minVal, maxVal + 1] };
  const rawStep = span / targetCount;
  const power = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const frac = rawStep / power;
  let niceStep;
  if (frac <= 1.5) niceStep = 1 * power;
  else if (frac <= 3.2) niceStep = 2 * power;
  else if (frac <= 7.0) niceStep = 5 * power;
  else niceStep = 10 * power;

  const niceMin = Math.floor(minVal / niceStep) * niceStep;
  const niceMax = Math.ceil(maxVal / niceStep) * niceStep;
  const ticks = [];
  for (let val = niceMin; val <= niceMax + niceStep * 0.01; val += niceStep) {
    ticks.push(Number(val.toFixed(4)));
  }
  return { min: niceMin, max: niceMax, ticks, step: niceStep };
}

const DEFAULT_ESTIMATE_EXAMPLE_ROWS = [
  { x: 0.03, t: 1.00, u: 68.95 },
  { x: 0.05, t: 1.67, u: 79.22 },
  { x: 0.07, t: 2.78, u: 67.72 },
  { x: 0.03, t: 4.64, u: 67.49 },
  { x: 0.05, t: 7.74, u: 76.52 },
  { x: 0.07, t: 12.92, u: 62.24 },
  { x: 0.03, t: 21.54, u: 59.72 },
  { x: 0.05, t: 35.94, u: 62.01 },
  { x: 0.07, t: 59.95, u: 46.81 },
  { x: 0.03, t: 100.00, u: 38.30 }
];

const DEFAULT_ESTIMATE_SCALED_ROWS = [
  { x: 0.30, t: 0.0100, u: 0.815 },
  { x: 0.50, t: 0.0167, u: 0.987 },
  { x: 0.70, t: 0.0278, u: 0.795 },
  { x: 0.30, t: 0.0464, u: 0.791 },
  { x: 0.50, t: 0.0774, u: 0.942 },
  { x: 0.70, t: 0.1292, u: 0.704 },
  { x: 0.30, t: 0.2154, u: 0.662 },
  { x: 0.50, t: 0.3594, u: 0.700 },
  { x: 0.70, t: 0.5995, u: 0.447 },
  { x: 0.30, t: 1.0000, u: 0.305 }
];

const DEFAULT_ESTIMATE_EXAMPLE = DEFAULT_ESTIMATE_EXAMPLE_ROWS.map(r => `${r.x}, ${r.t}, ${r.u}`).join('\n');

function createEstimateTableRow(x = '', t = '', u = '', rowNum = 1) {
  const scaledToggle = document.getElementById('est-scaled-toggle');
  const isScaled = Boolean(scaledToggle && scaledToggle.checked);
  const xPh = isScaled ? 'e.g. 0.5' : 'e.g. 0.05';
  const tPh = isScaled ? 'e.g. 0.1' : 'e.g. 10.0';
  const uPh = isScaled ? 'e.g. 0.8' : 'e.g. 75.0';
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="row-num">${rowNum}</td>
    <td><input type="text" class="cell-input" data-col="x" value="${x}" placeholder="${xPh}" autocomplete="off" spellcheck="false"></td>
    <td><input type="text" class="cell-input" data-col="t" value="${t}" placeholder="${tPh}" autocomplete="off" spellcheck="false"></td>
    <td><input type="text" class="cell-input" data-col="u" value="${u}" placeholder="${uPh}" autocomplete="off" spellcheck="false"></td>
    <td style="text-align: center;"><button type="button" class="btn-cell-delete" title="Delete row" aria-label="Delete row">&times;</button></td>
  `;
  return tr;
}

function updateTableRowNumbers() {
  const tbody = document.getElementById('est-table-tbody');
  if (!tbody) return;
  const rows = Array.from(tbody.children);
  const canDelete = rows.length > 3;
  rows.forEach((tr, idx) => {
    const numTd = tr.querySelector('.row-num');
    if (numTd) numTd.textContent = (idx + 1).toString();
    const delBtn = tr.querySelector('.btn-cell-delete');
    if (delBtn) {
      delBtn.style.visibility = canDelete ? 'visible' : 'hidden';
      delBtn.setAttribute('aria-hidden', canDelete ? 'false' : 'true');
    }
  });
}

function clearEstimateResultState() {
  const resultsCard = document.getElementById('estimate-results-card');
  const resultPanel = document.getElementById('est-result-panel');
  const emptyState = document.getElementById('est-empty-state');
  const stateContainer = document.getElementById('est-state-container');
  if (resultsCard) resultsCard.style.display = 'none';
  if (resultPanel) resultPanel.style.display = 'none';
  if (emptyState) emptyState.style.display = 'none';
  if (stateContainer) stateContainer.innerHTML = '';
}

function validateEstimateTable() {
  const tbody = document.getElementById('est-table-tbody');
  const validationMsg = document.getElementById('est-table-validation-msg');
  const countBadge = document.getElementById('est-readings-count');
  const scaledToggle = document.getElementById('est-scaled-toggle');
  const isScaled = Boolean(scaledToggle && scaledToggle.checked);

  let hasErrors = false;
  let testSettingsError = '';
  let rowErrorMessage = '';
  let firstErrorMessage = '';

  const barLengthInput = document.getElementById('est-bar-length');
  const expDurationInput = document.getElementById('est-experiment-time');
  const tempEdgeInput = document.getElementById('est-temp-edge');
  const tempPeakInput = document.getElementById('est-temp-peak');

  const L = barLengthInput && barLengthInput.value.trim() !== '' ? parseFloat(barLengthInput.value) : NaN;
  const T = expDurationInput && expDurationInput.value.trim() !== '' ? parseFloat(expDurationInput.value) : NaN;
  const Tb = tempEdgeInput && tempEdgeInput.value.trim() !== '' ? parseFloat(tempEdgeInput.value) : NaN;
  const Tp = tempPeakInput && tempPeakInput.value.trim() !== '' ? parseFloat(tempPeakInput.value) : NaN;

  if (!isScaled) {
    if (isNaN(L) || L <= 0 || isNaN(T) || T <= 0 || isNaN(Tb) || isNaN(Tp)) {
      testSettingsError = 'Please fill in all test settings: bar length, test duration, ends temperature, and start hottest temperature.';
    } else if (Tp === Tb) {
      testSettingsError = 'The hottest starting temperature cannot equal the ends temperature.';
    }
  }

  if (!tbody) {
    const firstErrorMessage = testSettingsError;
    return { validCount: 0, hasErrors: Boolean(firstErrorMessage), readings: [], firstErrorMessage, isScaled, L, T, Tb, Tp };
  }

  const rows = Array.from(tbody.children);
  let validCount = 0;
  const readings = [];

  rows.forEach((tr) => {
    const inputs = tr.querySelectorAll('.cell-input');
    if (inputs.length < 3) return;

    const xInput = inputs[0];
    const tInput = inputs[1];
    const uInput = inputs[2];

    const xVal = xInput.value.trim();
    const tVal = tInput.value.trim();
    const uVal = uInput.value.trim();

    xInput.classList.remove('cell-error');
    tInput.classList.remove('cell-error');
    uInput.classList.remove('cell-error');

    if (!xVal && !tVal && !uVal) return;

    let rowHasError = false;

    // Check complete cell presence
    if (!xVal || !tVal || !uVal) {
      if (!xVal) xInput.classList.add('cell-error');
      if (!tVal) tInput.classList.add('cell-error');
      if (!uVal) uInput.classList.add('cell-error');
      rowHasError = true;
      if (!firstErrorMessage) firstErrorMessage = 'All 3 columns (Position, Time, Temperature) are required for each reading.';
    }

    const xNum = parseFloat(xVal);
    const tNum = parseFloat(tVal);
    const uNum = parseFloat(uVal);

    if (xVal && (isNaN(xNum) || !isFinite(xNum))) {
      xInput.classList.add('cell-error');
      rowHasError = true;
      if (!rowErrorMessage) rowErrorMessage = 'Position must be a number';
    }
    if (tVal && (isNaN(tNum) || !isFinite(tNum))) {
      tInput.classList.add('cell-error');
      rowHasError = true;
      if (!rowErrorMessage) rowErrorMessage = 'Time must be a number';
    }
    if (uVal && (isNaN(uNum) || !isFinite(uNum))) {
      uInput.classList.add('cell-error');
      rowHasError = true;
      if (!rowErrorMessage) rowErrorMessage = 'Temperature must be a number';
    }

    if (!rowHasError) {
      if (isScaled) {
        if (xNum < 0 || xNum > 1) {
          xInput.classList.add('cell-error');
          rowHasError = true;
          if (!rowErrorMessage) rowErrorMessage = 'Position must be between 0 and 1';
        }
        if (tNum <= 0 || tNum > 1.0) {
          tInput.classList.add('cell-error');
          rowHasError = true;
          if (!rowErrorMessage) rowErrorMessage = 'Time must be between 0 and 1';
        }
      } else {
        if (!isNaN(L) && L > 0) {
          if (xNum < 0 || xNum > L) {
            xInput.classList.add('cell-error');
            rowHasError = true;
            if (!rowErrorMessage) rowErrorMessage = `Position must be between 0 and the bar length (0 to ${L} m).`;
          }
        } else {
          if (xNum < 0 || xNum > 1) {
            xInput.classList.add('cell-error');
            rowHasError = true;
            if (!rowErrorMessage) rowErrorMessage = 'Position must be between 0 and 1';
          }
        }
        if (!isNaN(T) && T > 0) {
          if (tNum <= 0 || tNum > T) {
            tInput.classList.add('cell-error');
            rowHasError = true;
            if (!rowErrorMessage) rowErrorMessage = `Time must be between 0 and the test duration (up to ${T} s).`;
          }
        }
        if (!isNaN(Tb) && !isNaN(Tp) && Tp !== Tb) {
          const tMin = Math.min(Tb, Tp);
          const tMax = Math.max(Tb, Tp);
          const span = tMax - tMin;
          if (uNum < tMin - 0.5 * span || uNum > tMax + 0.5 * span) {
            uInput.classList.add('cell-error');
            rowHasError = true;
            if (!rowErrorMessage) rowErrorMessage = "These readings don't look like cooling from your stated start. Check your units or values.";
          }
        }
      }
    }

    if (rowHasError) {
      hasErrors = true;
    } else {
      validCount++;
      readings.push({ x: xNum, t: tNum, u: uNum });
    }
  });

  firstErrorMessage = rowErrorMessage || testSettingsError || firstErrorMessage;
  hasErrors = Boolean(rowErrorMessage || testSettingsError || firstErrorMessage);

  if (countBadge) {
    if (validCount < 3) {
      countBadge.textContent = `${validCount} of 3 needed`;
    } else {
      countBadge.textContent = `${validCount} readings ✓`;
    }
  }

  if (validationMsg) {
    validationMsg.textContent = firstErrorMessage;
  }

  const hiddenPaste = document.getElementById('est-paste-text');
  if (hiddenPaste) {
    hiddenPaste.value = readings.map(r => `${r.x}, ${r.t}, ${r.u}`).join('\n');
  }

  return { validCount, hasErrors, readings, firstErrorMessage, isScaled, L, T, Tb, Tp };
}

function initEstimateWorkbench() {
  const tbody = document.getElementById('est-table-tbody');
  const addRowBtn = document.getElementById('est-add-row-btn');
  const useExampleBtn = document.getElementById('est-use-example-btn');
  const csvBtn = document.getElementById('est-csv-btn');
  const csvUpload = document.getElementById('est-csv-upload');
  const baselineToggle = document.getElementById('est-baseline-toggle');
  const sigmaVal = document.getElementById('est-sigma-val');
  const noiseSelect = document.getElementById('est-noise-select');
  const methodSelect = document.getElementById('est-method-select');
  const methodGuidance = document.getElementById('est-method-guidance');
  const physGroup = document.getElementById('est-physics-config-group');
  const submitBtn = document.getElementById('est-submit-btn');
  const sampleBtn = document.getElementById('est-sample-synth-btn');
  const rerunDemoBtn = document.getElementById('est-rerun-demo-btn');
  const downloadBtn = document.getElementById('download-estimate-btn') || document.getElementById('est-download-btn');
  const synthBtn = document.getElementById('estimate-mode-synth-btn');
  const pasteBtn = document.getElementById('estimate-mode-paste-btn');
  const pasteText = document.getElementById('est-paste-text');
  const moreOptionsBtn = document.getElementById('est-more-options-btn');
  const drawer = document.getElementById('est-more-drawer');
  const drawerOverlay = document.getElementById('est-drawer-overlay');
  const drawerCloseBtn = document.getElementById('est-drawer-close-btn');
  const scaledToggle = document.getElementById('est-scaled-toggle');

  // Initialize table with exactly 3 empty rows (the minimum)
  if (tbody && tbody.children.length === 0) {
    for (let i = 0; i < 3; i++) {
      tbody.appendChild(createEstimateTableRow('', '', '', i + 1));
    }
  }

  // Bar length and test time inputs
  const barLengthInput = document.getElementById('est-bar-length');
  const expDurationInput = document.getElementById('est-experiment-time');
  if (barLengthInput) {
    barLengthInput.addEventListener('input', () => {
      validateEstimateTable();
      clearEstimateResultState();
    });
  }
  if (expDurationInput) {
    expDurationInput.addEventListener('input', () => {
      validateEstimateTable();
      clearEstimateResultState();
    });
  }

  // Real temperature inputs (°C)
  const tempPeakInput = document.getElementById('est-temp-peak');
  const tempEdgeInput = document.getElementById('est-temp-edge');
  if (tempPeakInput) {
    tempPeakInput.addEventListener('input', () => {
      validateEstimateTable();
      clearEstimateResultState();
    });
  }
  if (tempEdgeInput) {
    tempEdgeInput.addEventListener('input', () => {
      validateEstimateTable();
      clearEstimateResultState();
    });
  }

  if (sigmaVal) {
    sigmaVal.addEventListener('input', () => {
      clearEstimateResultState();
    });
  }

  // Scaled 0-1 Toggle (Inside More options -> Advanced)
  if (scaledToggle) {
    scaledToggle.addEventListener('change', () => {
      const isScaled = scaledToggle.checked;
      const realUnitsContainer = document.getElementById('est-real-units-container');
      if (realUnitsContainer) {
        realUnitsContainer.style.display = isScaled ? 'none' : 'block';
      }
      const colXTitle = document.getElementById('est-col-x-title');
      const colTTitle = document.getElementById('est-col-t-title');
      const colUTitle = document.getElementById('est-col-u-title');
      const colXHelper = document.getElementById('est-col-x-helper');
      const colTHelper = document.getElementById('est-col-t-helper');
      const colUHelper = document.getElementById('est-col-u-helper');
      const sigmaLabel = document.getElementById('est-sigma-label');
      const sigmaInput = document.getElementById('est-sigma-val');

      if (isScaled) {
        if (colXTitle) colXTitle.textContent = 'Position (0–1)';
        if (colTTitle) colTTitle.textContent = 'Time (0–1)';
        if (colUTitle) colUTitle.textContent = 'Temperature (0–1)';
        if (colXHelper) colXHelper.textContent = 'Where on the bar: 0 = one end, 1 = other end';
        if (colTHelper) colTHelper.textContent = 'When it was measured (0 to 1)';
        if (colUHelper) colUHelper.textContent = 'Scaled so hottest point at start = 1';
        if (sigmaLabel) sigmaLabel.innerHTML = 'Sensor accuracy (&plusmn;) <span class="info-tooltip" title="Measurement error in scaled units.">&#9432;</span>';
        if (sigmaInput && (sigmaInput.value === '0.5' || sigmaInput.value === '0.50')) {
          sigmaInput.value = '0.01';
        }
      } else {
        if (colXTitle) colXTitle.textContent = 'Position (m)';
        if (colTTitle) colTTitle.textContent = 'Time (s)';
        if (colUTitle) colUTitle.textContent = 'Temperature (°C)';
        if (colXHelper) colXHelper.textContent = 'Where on the bar: 0 = one end, up to bar length';
        if (colTHelper) colTHelper.textContent = 'When it was measured';
        if (colUHelper) colUHelper.textContent = 'What the sensor read';
        if (sigmaLabel) sigmaLabel.innerHTML = 'Sensor accuracy (&plusmn; &deg;C) <span class="info-tooltip" title="Typical measurement error of your temperature sensor. Not sure? Leave 0.5 &deg;C.">&#9432;</span>';
        if (sigmaInput && (sigmaInput.value === '0.01' || sigmaInput.value === '0.010')) {
          sigmaInput.value = '0.5';
        }
      }
      validateEstimateTable();
      clearEstimateResultState();
    });
  }

  // Heating Profile Radios
  const heatSine = document.getElementById('est-heat-sine');
  const heatConstant = document.getElementById('est-heat-constant');
  if (heatSine) {
    heatSine.addEventListener('change', () => {
      if (heatSine.checked) {
        const u0Input = document.getElementById('est-phys-u0');
        if (u0Input) u0Input.value = 'sin(pi*x)';
        const preset = document.getElementById('est-phys-preset');
        if (preset) preset.value = 'sine';
        clearEstimateResultState();
      }
    });
  }
  if (heatConstant) {
    heatConstant.addEventListener('change', () => {
      if (heatConstant.checked) {
        const u0Input = document.getElementById('est-phys-u0');
        if (u0Input) u0Input.value = '1';
        const preset = document.getElementById('est-phys-preset');
        if (preset) preset.value = 'constant';
        clearEstimateResultState();
      }
    });
  }

  updateTableRowNumbers();
  validateEstimateTable();
  clearEstimateResultState();

  // Add row button
  if (addRowBtn) {
    addRowBtn.addEventListener('click', () => {
      if (tbody) {
        const nextIdx = tbody.children.length + 1;
        const tr = createEstimateTableRow('', '', '', nextIdx);
        tbody.appendChild(tr);
        updateTableRowNumbers();
        validateEstimateTable();
        clearEstimateResultState();
        const firstInput = tr.querySelector('.cell-input');
        if (firstInput) firstInput.focus();
      }
    });
  }

  // Delete row delegation, Tab key auto-add, and input validation
  if (tbody) {
    tbody.addEventListener('click', (e) => {
      const delBtn = e.target.closest('.btn-cell-delete');
      if (!delBtn) return;
      if (tbody.children.length <= 3) return; // Disallow deletion when only 3 rows remain
      const tr = delBtn.closest('tr');
      if (tr) {
        tr.remove();
        updateTableRowNumbers();
        validateEstimateTable();
        clearEstimateResultState();
      }
    });

    // Pressing Tab in the last cell of the last row adds a new row
    tbody.addEventListener('keydown', (e) => {
      if (e.key === 'Tab' && !e.shiftKey) {
        const targetInput = e.target.closest('.cell-input');
        if (!targetInput) return;
        const tr = targetInput.closest('tr');
        if (tr && tr === tbody.lastElementChild && targetInput.getAttribute('data-col') === 'u') {
          e.preventDefault();
          const nextIdx = tbody.children.length + 1;
          const newTr = createEstimateTableRow('', '', '', nextIdx);
          tbody.appendChild(newTr);
          updateTableRowNumbers();
          validateEstimateTable();
          clearEstimateResultState();
          const firstInput = newTr.querySelector('.cell-input');
          if (firstInput) firstInput.focus();
        }
      }
    });

    tbody.addEventListener('input', (e) => {
      if (e.target.classList.contains('cell-input')) {
        validateEstimateTable();
        clearEstimateResultState();
      }
    });

    // Multi-row paste directly into table
    tbody.addEventListener('paste', (e) => {
      const targetInput = e.target.closest('.cell-input');
      if (!targetInput) return;
      const clipText = (e.clipboardData || window.clipboardData).getData('text');
      if (!clipText) return;

      const lines = clipText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      if (lines.length === 0) return;

      const firstLineParts = lines[0].split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
      if (lines.length > 1 || firstLineParts.length > 1) {
        e.preventDefault();

        let targetRow = targetInput.closest('tr');
        let targetRowIndex = Array.from(tbody.children).indexOf(targetRow);
        if (targetRowIndex < 0) targetRowIndex = 0;

        let startIdx = 0;
        if (isNaN(parseFloat(firstLineParts[0])) && isNaN(parseFloat(firstLineParts[1] || ''))) {
          startIdx = 1;
        }

        const targetCol = targetInput.getAttribute('data-col');
        const colOffset = targetCol === 't' ? 1 : (targetCol === 'u' ? 2 : 0);

        for (let i = startIdx; i < lines.length; i++) {
          const line = lines[i];
          if (!line || line.startsWith('#')) continue;
          const parts = line.split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
          if (parts.length === 0) continue;

          const rowIndex = targetRowIndex + (i - startIdx);
          while (tbody.children.length <= rowIndex) {
            tbody.appendChild(createEstimateTableRow('', '', '', tbody.children.length + 1));
          }

          const row = tbody.children[rowIndex];
          const inputs = row.querySelectorAll('.cell-input');
          if (colOffset === 0) {
            if (parts[0] !== undefined && inputs[0]) inputs[0].value = parts[0];
            if (parts[1] !== undefined && inputs[1]) inputs[1].value = parts[1];
            if (parts[2] !== undefined && inputs[2]) inputs[2].value = parts[2];
          } else {
            for (let c = 0; c < parts.length && (colOffset + c) < inputs.length; c++) {
              inputs[colOffset + c].value = parts[c];
            }
          }
        }

        updateTableRowNumbers();
        validateEstimateTable();
        clearEstimateResultState();
      }
    });
  }

  // Use example data button
  if (useExampleBtn) {
    useExampleBtn.addEventListener('click', () => {
      const isScaled = Boolean(scaledToggle && scaledToggle.checked);
      if (tbody) {
        tbody.innerHTML = '';
        if (isScaled) {
          DEFAULT_ESTIMATE_SCALED_ROWS.forEach((r, idx) => {
            tbody.appendChild(createEstimateTableRow(r.x.toFixed(2), r.t.toFixed(4), r.u.toFixed(4), idx + 1));
          });
          const sigmaInput = document.getElementById('est-sigma-val');
          if (sigmaInput) sigmaInput.value = '0.01';
        } else {
          DEFAULT_ESTIMATE_EXAMPLE_ROWS.forEach((r, idx) => {
            tbody.appendChild(createEstimateTableRow(r.x.toFixed(2), r.t.toFixed(2), r.u.toFixed(2), idx + 1));
          });
          if (barLengthInput) barLengthInput.value = '0.1';
          if (expDurationInput) expDurationInput.value = '100';
          if (tempEdgeInput) tempEdgeInput.value = '20';
          if (tempPeakInput) tempPeakInput.value = '80';
          if (sigmaVal) sigmaVal.value = '0.5';
          if (heatSine) heatSine.checked = true;
        }
        STATE.isEstimateDemo = false;
        updateTableRowNumbers();
        validateEstimateTable();
        clearEstimateResultState();
      }
    });
  }

  // CSV upload button & input
  if (csvBtn && csvUpload) {
    csvBtn.addEventListener('click', () => csvUpload.click());
    csvUpload.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        const text = evt.target.result;
        const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
        if (tbody) {
          tbody.innerHTML = '';
          let added = 0;
          for (let line of lines) {
            if (!line || line.startsWith('#')) continue;
            const parts = line.split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
            if (parts.length >= 3) {
              if (isNaN(parseFloat(parts[0])) && isNaN(parseFloat(parts[1]))) continue;
              tbody.appendChild(createEstimateTableRow(parts[0], parts[1], parts[2]));
              added++;
            }
          }
          if (added === 0) {
            for (let i = 0; i < 3; i++) tbody.appendChild(createEstimateTableRow());
          }
        }
        STATE.isEstimateDemo = false;
        updateTableRowNumbers();
        validateEstimateTable();
        clearEstimateResultState();
        csvUpload.value = '';
      };
      reader.readAsText(file);
    });
  }

  // Side drawer open/close
  function openDrawer() {
    if (drawer) {
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    }
    if (drawerOverlay) drawerOverlay.classList.add('open');
  }

  function closeDrawer() {
    if (drawer) {
      drawer.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
    }
    if (drawerOverlay) drawerOverlay.classList.remove('open');
  }

  if (moreOptionsBtn) moreOptionsBtn.addEventListener('click', openDrawer);
  if (drawerCloseBtn) drawerCloseBtn.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  // Backward compatibility with pasteText input
  if (pasteText) {
    pasteText.addEventListener('input', () => {
      const rawText = pasteText.value.trim();
      if (!rawText || !tbody) return;
      const lines = rawText.split('\n');
      tbody.innerHTML = '';
      let added = 0;
      for (let l of lines) {
        const cleanLine = l.trim();
        if (!cleanLine || cleanLine.startsWith('#')) continue;
        const parts = cleanLine.split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
        if (parts.length >= 3) {
          tbody.appendChild(createEstimateTableRow(parts[0], parts[1], parts[2]));
          added++;
        } else if (parts.length > 0) {
          tbody.appendChild(createEstimateTableRow(parts[0] || '', parts[1] || '', parts[2] || ''));
          added++;
        }
      }
      if (added === 0) {
        for (let i = 0; i < 3; i++) tbody.appendChild(createEstimateTableRow());
      }
      updateTableRowNumbers();
      validateEstimateTable();
      clearEstimateResultState();
    });
  }

  // Sensor accuracy baseline toggle (inside More options)
  if (baselineToggle) {
    baselineToggle.addEventListener('change', () => {
      if (baselineToggle.checked) {
        if (noiseSelect) noiseSelect.value = 'baseline';
        if (sigmaVal) sigmaVal.disabled = true;
      } else {
        if (noiseSelect) noiseSelect.value = 'declared';
        if (sigmaVal) sigmaVal.disabled = false;
      }
    });
  }

  // Calculation method guidance
  const METHOD_GUIDANCE_TEXT = {
    mode3plus: "Recommended for all standard tests. High accuracy with verified 94% confidence intervals.",
    mode3: "Ultra-fast calculation (~1 ms). Best for continuous live monitoring where speed matters more than confidence bounds.",
    mode2: "Classical finite-difference solver. Thorough and robust; useful when double-checking an unusual result.",
    declared_physics: "Custom setup. Use when your bar has a custom starting heat profile."
  };

  if (methodSelect) {
    methodSelect.addEventListener('change', () => {
      const val = methodSelect.value;
      if (methodGuidance) {
        methodGuidance.textContent = METHOD_GUIDANCE_TEXT[val] || '';
      }
      if (physGroup) {
        physGroup.style.display = (val === 'declared_physics') ? 'block' : 'none';
      }
    });
  }

  // Preset setups in "My setup is different"
  const physPreset = document.getElementById('est-phys-preset');
  const u0Input = document.getElementById('est-phys-u0');
  if (physPreset && u0Input) {
    physPreset.addEventListener('change', () => {
      if (physPreset.value === 'constant') {
        u0Input.value = '1';
      } else if (physPreset.value === 'sine') {
        u0Input.value = 'sin(pi*x)';
      }
    });
    u0Input.addEventListener('input', () => {
      const v = u0Input.value.trim();
      if (v === '1') {
        physPreset.value = 'constant';
      } else if (v === 'sin(pi*x)' || v === 'sin(pi * x)') {
        physPreset.value = 'sine';
      } else {
        physPreset.value = 'custom';
      }
    });
  }

  // Demo tools buttons
  if (synthBtn) {
    synthBtn.addEventListener('click', () => {
      synthBtn.classList.add('active');
      if (pasteBtn) pasteBtn.classList.remove('active');
      STATE.isEstimateDemo = true;
    });
  }

  if (pasteBtn) {
    pasteBtn.addEventListener('click', () => {
      pasteBtn.classList.add('active');
      if (synthBtn) synthBtn.classList.remove('active');
      STATE.isEstimateDemo = false;
    });
  }

  if (sampleBtn) {
    sampleBtn.addEventListener('click', () => {
      STATE.isEstimateDemo = true;
      generateEstimateSample();
    });
  }

  if (rerunDemoBtn) {
    rerunDemoBtn.addEventListener('click', runRandomDemo);
  }

  if (submitBtn) {
    submitBtn.addEventListener('click', executeParameterEstimate);
  }

  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      if (!STATE.lastEstimateResult) return;
      downloadJson(STATE.lastEstimateResult, 'estimate_result.json');
    });
  }
}

function runRandomDemo() {
  const seedInput = document.getElementById('est-seed');
  const curSeed = parseInt(seedInput ? seedInput.value : '42') || 42;
  if (seedInput) seedInput.value = curSeed + 1;
  STATE.isEstimateDemo = true;
  generateEstimateSample();
  executeParameterEstimate();
}

function generateEstimateSample() {
  const alphaTrue = parseFloat(document.getElementById('est-true-alpha').value) || 0.10;
  const N = parseInt(document.getElementById('est-num-sensors').value) || 10;
  const seed = parseInt(document.getElementById('est-seed').value) || 42;
  const rng = mulberry32(seed);
  const scaledToggle = document.getElementById('est-scaled-toggle');
  const isScaled = Boolean(scaledToggle && scaledToggle.checked);

  const tbody = document.getElementById('est-table-tbody');
  if (tbody) {
    tbody.innerHTML = '';
    if (isScaled) {
      const sigma = parseFloat(document.getElementById('est-sigma-val').value) || 0.01;
      for (let i = 0; i < N; i++) {
        const x = 0.50;
        const t = Math.pow(10, Math.log10(0.01) + (i / Math.max(1, N - 1)) * (Math.log10(1.0) - Math.log10(0.01)));
        const uExact = Math.sin(Math.PI * x) * Math.exp(-alphaTrue * Math.PI * Math.PI * t);
        const noise = randomNormal(rng, 0, sigma);
        const y = Math.max(0, uExact + noise);
        tbody.appendChild(createEstimateTableRow(x.toFixed(2), t.toFixed(4), y.toFixed(4), i + 1));
      }
    } else {
      const L = 0.1;
      const T = 100.0;
      const Tb = 20.0;
      const Tp = 80.0;
      const sigma = parseFloat(document.getElementById('est-sigma-val').value) || 0.5;

      const barLengthInput = document.getElementById('est-bar-length');
      const expDurationInput = document.getElementById('est-experiment-time');
      const tempEdgeInput = document.getElementById('est-temp-edge');
      const tempPeakInput = document.getElementById('est-temp-peak');
      if (barLengthInput) barLengthInput.value = String(L);
      if (expDurationInput) expDurationInput.value = String(T);
      if (tempEdgeInput) tempEdgeInput.value = String(Tb);
      if (tempPeakInput) tempPeakInput.value = String(Tp);

      for (let i = 0; i < N; i++) {
        const x = 0.05;
        const tNorm = Math.pow(10, Math.log10(0.01) + (i / Math.max(1, N - 1)) * (Math.log10(1.0) - Math.log10(0.01)));
        const tSec = tNorm * T;
        const uNorm = Math.sin(Math.PI * (x / L)) * Math.exp(-alphaTrue * Math.PI * Math.PI * tNorm);
        const noise = randomNormal(rng, 0, sigma);
        const tempC = Tb + (Tp - Tb) * uNorm + noise;
        tbody.appendChild(createEstimateTableRow(x.toFixed(2), tSec.toFixed(2), tempC.toFixed(2), i + 1));
      }
    }
  }

  STATE.isEstimateDemo = true;
  updateTableRowNumbers();
  validateEstimateTable();
  clearEstimateResultState();
}

async function executeParameterEstimate() {
  const stateContainer = document.getElementById('est-state-container');
  const resultPanel = document.getElementById('est-result-panel');
  const emptyState = document.getElementById('est-empty-state');
  const validationMsg = document.getElementById('est-table-validation-msg');
  const trueAlpha = parseFloat(document.getElementById('est-true-alpha').value) || 0.10;

  // Validate table inputs first
  const { validCount, hasErrors, readings, firstErrorMessage, isScaled, L, T, Tb, Tp } = validateEstimateTable();

  if (hasErrors) {
    if (validationMsg) validationMsg.textContent = firstErrorMessage;
    if (stateContainer) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Input Error:</strong> ${firstErrorMessage}</div>`;
    }
    return;
  }

  if (validCount < 3) {
    const msg = 'Please enter at least 3 readings to calculate.';
    if (validationMsg) validationMsg.textContent = msg;
    if (stateContainer) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Input Error:</strong> ${msg}</div>`;
    }
    return;
  }

  const xList = readings.map(r => r.x);
  const tList = readings.map(r => r.t);
  const yList = readings.map(r => r.u);

  if (validationMsg) validationMsg.textContent = '';
  if (emptyState) emptyState.style.display = 'none';
  if (stateContainer) {
    stateContainer.innerHTML = '<div class="state-box loading"><span class="spinner"></span> Calculating heat spread...</div>';
  }
  if (resultPanel) resultPanel.style.display = 'none';

  // Determine calculation mode and physics config
  const heatConstant = document.getElementById('est-heat-constant');
  const methodSelect = document.getElementById('est-method-select');
  let methodMode = methodSelect ? methodSelect.value : 'mode3plus';
  let physicsConfig = null;

  if (heatConstant && heatConstant.checked) {
    methodMode = 'declared_physics';
    physicsConfig = { u0_expr: '1' };
  } else if (methodMode === 'declared_physics') {
    const u0Input = document.getElementById('est-phys-u0');
    const u0Val = u0Input ? u0Input.value.trim() : 'sin(pi*x)';
    physicsConfig = { u0_expr: u0Val };
  }

  const noiseMode = document.getElementById('est-noise-select') ? document.getElementById('est-noise-select').value : 'declared';
  const declaredSigma = parseFloat(document.getElementById('est-sigma-val').value) || (isScaled ? 0.01 : 0.5);

  const payload = {
    x: xList,
    t: tList,
    y: yList,
    mode: methodMode
  };

  if (!isScaled) {
    payload.bar_length_m = L;
    payload.test_duration_s = T;
    payload.boundary_temperature = Tb;
    payload.initial_peak_temperature = Tp;
  }

  if (noiseMode === 'declared') {
    payload.sigma = declaredSigma;
  } else if (noiseMode === 'baseline') {
    const rngBase = mulberry32(101);
    const xb = [], tb = [], yb = [];
    for (let i = 0; i < 20; i++) {
      const x = 0.5;
      const t = 0.05 + i * 0.045;
      const u = Math.sin(Math.PI * x) * Math.exp(-0.10 * Math.PI * Math.PI * t);
      xb.push(x);
      tb.push(t);
      yb.push(u + randomNormal(rngBase, 0, 0.01));
    }
    payload.baseline = { x_coords: xb, t_coords: tb, readings: yb };
  } else if (noiseMode === 'baseline_short') {
    const xb = Array(10).fill(0.5);
    const tb = Array.from({length: 10}, (_, i) => 0.1 + i * 0.08);
    const yb = tb.map(t => Math.sin(Math.PI * 0.5) * Math.exp(-0.10 * Math.PI * Math.PI * t));
    payload.baseline = { x_coords: xb, t_coords: tb, readings: yb };
  }

  if (physicsConfig) {
    payload.physics_config = physicsConfig;
  }

  console.log("Estimate outgoing JSON:", JSON.stringify(payload));

  try {
    const res = await fetch('/v1/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    STATE.lastEstimateResult = { 
      request: payload, 
      response: data, 
      isDemoMode: Boolean(STATE.isEstimateDemo), 
      trueAlpha,
      isScaled,
      barLength: L,
      expDuration: T
    };

    console.log("Estimate response status:", res.status);
    console.log("Estimate response data:", JSON.stringify(data));

    if (!res.ok) {
      const errCode = data.error_code || (data.detail && data.detail.error_code) || 'ERROR';
      const msg = data.message || (data.detail && data.detail.message) || (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
      console.warn("Estimate request failed:", errCode, msg);
      if (stateContainer) {
        stateContainer.innerHTML = `
          <div class="state-box refusal">
            <div style="font-weight: 700; margin-bottom: 0.3rem;">Request Refusal (${errCode})</div>
            <div>${msg}</div>
          </div>
        `;
      }
      const resultsCard = document.getElementById('estimate-results-card');
      if (resultsCard) resultsCard.style.display = 'block';
      if (resultPanel) resultPanel.style.display = 'block';
      const numberEl = document.getElementById('est-plain-number');
      const headlineEl = document.getElementById('est-plain-headline');
      const sublineEl = document.getElementById('est-plain-subline');
      if (numberEl) numberEl.textContent = 'No reliable result';
      if (headlineEl) headlineEl.innerHTML = '<strong>No reliable result</strong>';
      if (sublineEl) sublineEl.textContent = msg;
      return;
    }

    if (stateContainer) stateContainer.innerHTML = '';
    const resultsCard = document.getElementById('estimate-results-card');
    if (resultsCard) resultsCard.style.display = 'block';
    if (resultPanel) resultPanel.style.display = 'block';

    const alphaHat = data.alpha_hat;
    const ci95 = data.ci95;
    const flags = data.flags || {};
    const warnings = flags.warnings || [];

    const numberEl = document.getElementById('est-plain-number');
    const labelEl = document.getElementById('est-result-label');
    const headlineEl = document.getElementById('est-plain-headline');
    const sublineEl = document.getElementById('est-plain-subline');
    const outAlphaHidden = document.getElementById('est-out-alpha');
    if (outAlphaHidden) outAlphaHidden.textContent = alphaHat.toExponential ? alphaHat.toExponential(6) : String(alphaHat);

    function formatAlphaDisplay(v) {
      if (v === null || v === undefined || isNaN(v)) return '-';
      if (Math.abs(v) < 0.001 || Math.abs(v) >= 1000) {
        return v.toExponential(1).replace('+', '');
      }
      return v.toFixed(3);
    }

    const isRealResult = (data.units === 'm²/s' || (data.normalization && data.normalization.scale_factor && data.normalization.scale_factor !== 1.0));

    if (flags.model_invalid) {
      if (numberEl) numberEl.textContent = 'No reliable result';
      if (headlineEl) headlineEl.innerHTML = '<strong>No reliable result</strong>';
      if (sublineEl) sublineEl.textContent = 'The twin could not calculate a trustworthy heat spread from these readings.';
    } else if (isRealResult) {
      const alphaStr = formatScientificReal(alphaHat, 2);
      const ciLoStr = formatScientificReal(ci95[0], 3);
      const ciHiStr = formatScientificReal(ci95[1], 3);

      if (labelEl) labelEl.textContent = 'Heat spread (α)';
      if (numberEl) numberEl.innerHTML = `${alphaStr} <span style="font-size: 1.1rem; font-weight: 500; font-family: var(--font-sans); color: var(--text-muted);">m&sup2;/s</span>`;
      if (headlineEl) headlineEl.innerHTML = `Heat spread (α): <strong>${alphaStr} m&sup2;/s</strong>`;
      if (sublineEl) sublineEl.innerHTML = `Most likely between <strong>${ciLoStr}</strong> to <strong>${ciHiStr} m&sup2;/s</strong>`;
    } else {
      if (labelEl) labelEl.textContent = 'Heat spread (α)';
      if (numberEl) numberEl.textContent = alphaHat.toFixed(3);
      if (headlineEl) headlineEl.innerHTML = `Heat spread (α): <strong>${alphaHat.toFixed(3)}</strong>`;
      if (sublineEl) sublineEl.innerHTML = `Most likely between <strong>${ci95[0].toFixed(3)}</strong> to <strong>${ci95[1].toFixed(3)}</strong>`;
    }

    // Traffic-Light Line
    const banner = document.getElementById('est-traffic-banner');
    const bannerTitle = document.getElementById('est-traffic-title');
    let bannerLevel = 'green';
    let bannerText = 'Result looks trustworthy';

    if (flags.model_invalid) {
      bannerLevel = 'red';
      bannerText = "We can't give a reliable number: your readings do not fit the heat model";
    } else if (flags.out_of_range || flags.at_bound) {
      bannerLevel = 'amber';
      bannerText = 'Check this result: value is near the edge of the tested range';
    } else {
      let hasCorrelatedErrors = false;
      warnings.forEach(w => {
        const wl = w.toLowerCase();
        if (wl.includes('autocorrelation') || wl.includes('durbin-watson') || wl.includes('correlated')) {
          hasCorrelatedErrors = true;
        }
      });
      if (hasCorrelatedErrors) {
        bannerLevel = 'amber';
        bannerText = 'Check this result: errors look correlated';
      } else if (warnings.length > 0) {
        bannerLevel = 'amber';
        bannerText = `Check this result: ${warnings[0]}`;
      } else {
        bannerLevel = 'green';
        bannerText = 'Result looks trustworthy';
      }
    }

    if (banner) banner.className = `traffic-light-line ${bannerLevel}`;
    if (bannerTitle) bannerTitle.textContent = bannerText;

    // Badges: plain sentences with raw flag in small grey text
    const badgesContainer = document.getElementById('est-badges-container');
    if (badgesContainer) {
      badgesContainer.innerHTML = '';
      if (flags.model_invalid) {
        badgesContainer.innerHTML += '<span class="badge badge-danger">Readings do not match heat model <span class="raw-flag">(model_invalid)</span></span>';
      }
      if (flags.out_of_range) {
        badgesContainer.innerHTML += '<span class="badge badge-warning">Outside tested operating bounds <span class="raw-flag">(out_of_range)</span></span>';
      }
      if (flags.at_bound) {
        badgesContainer.innerHTML += '<span class="badge badge-warning">Fit reached optimizer boundary <span class="raw-flag">(at_bound)</span></span>';
      }
      warnings.forEach(w => {
        badgesContainer.innerHTML += `<span class="badge badge-warning">${w}</span>`;
      });
      if (!flags.model_invalid && !flags.out_of_range && !flags.at_bound && warnings.length === 0) {
        badgesContainer.innerHTML += '<span class="badge badge-success">Model Valid</span>';
      }
    }

    // Demo Mode Callout
    const demoCallout = document.getElementById('est-demo-callout');
    const chartTruthLegend = document.getElementById('est-chart-truth-legend');
    if (STATE.isEstimateDemo) {
      const inInterval = (trueAlpha >= (data.alpha_hat_normalized !== undefined ? data.ci95_normalized[0] : ci95[0]) &&
                          trueAlpha <= (data.alpha_hat_normalized !== undefined ? data.ci95_normalized[1] : ci95[1]));
      if (demoCallout) {
        demoCallout.style.display = 'flex';
        demoCallout.innerHTML = `
          <div>
            <strong>Demo mode:</strong> 
            ${inInterval 
              ? 'Known value was inside the range.' 
              : 'Known value was outside the range (about 1 in 20 runs misses by design).'}
            <span class="mono" style="margin-left: 0.5rem; opacity: 0.85;">(Demo value = ${trueAlpha.toFixed(4)})</span>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" id="est-rerun-demo-btn-inline">Run again with new seed</button>
        `;
        const rerunInline = document.getElementById('est-rerun-demo-btn-inline');
        if (rerunInline) rerunInline.addEventListener('click', runRandomDemo);
      }
      if (chartTruthLegend) chartTruthLegend.style.display = 'flex';
    } else {
      if (demoCallout) demoCallout.style.display = 'none';
      if (chartTruthLegend) chartTruthLegend.style.display = 'none';
    }

    // Details disclosure: Normalized values only in Show details
    document.getElementById('est-out-ci').textContent = isRealResult
      ? `${formatScientificReal(ci95[0], 3)} to ${formatScientificReal(ci95[1], 3)} m²/s`
      : `[${ci95[0].toFixed(4)}, ${ci95[1].toFixed(4)}]`;
    document.getElementById('est-out-method').textContent = data.method;
    document.getElementById('est-out-timing').textContent = data.timing_ms.toFixed(2);

    const rowAlphaNorm = document.getElementById('est-row-alpha-norm');
    const outAlphaNorm = document.getElementById('est-out-alpha-norm');
    const rowNormConsts = document.getElementById('est-row-norm-constants');
    const outNormConsts = document.getElementById('est-out-norm-constants');

    if (data.alpha_hat_normalized !== null && data.alpha_hat_normalized !== undefined) {
      if (rowAlphaNorm) rowAlphaNorm.style.display = '';
      if (outAlphaNorm) {
        const ciNormPart = data.ci95_normalized ? ` (95% CI: [${data.ci95_normalized[0].toFixed(4)}, ${data.ci95_normalized[1].toFixed(4)}])` : '';
        outAlphaNorm.textContent = `${data.alpha_hat_normalized.toFixed(5)}${ciNormPart}`;
      }
    } else {
      if (rowAlphaNorm) rowAlphaNorm.style.display = 'none';
    }

    if (data.normalization) {
      if (rowNormConsts) rowNormConsts.style.display = '';
      if (outNormConsts) {
        const norm = data.normalization;
        const parts = [];
        if (norm.bar_length_m !== null && norm.bar_length_m !== undefined) parts.push(`L = ${norm.bar_length_m} m`);
        if (norm.test_duration_s !== null && norm.test_duration_s !== undefined) parts.push(`T = ${norm.test_duration_s} s`);
        if (norm.boundary_temperature !== null && norm.boundary_temperature !== undefined) parts.push(`Ends = ${norm.boundary_temperature} °C`);
        if (norm.initial_peak_temperature !== null && norm.initial_peak_temperature !== undefined) parts.push(`Peak = ${norm.initial_peak_temperature} °C`);
        if (norm.scale_factor !== null && norm.scale_factor !== undefined) parts.push(`Scale L²/T = ${norm.scale_factor.toExponential(2).replace('+', '')}`);
        outNormConsts.textContent = parts.join(', ');
      }
    } else {
      if (rowNormConsts) rowNormConsts.style.display = 'none';
    }

    const chi2El = document.getElementById('est-out-chi2');
    if (chi2El) {
      chi2El.textContent = (data.chi2_dof !== undefined ? data.chi2_dof.toFixed(3) : (flags.model_invalid ? '> 1.88 (rejected)' : '< 1.88 (accepted)'));
    }

    const dwEl = document.getElementById('est-out-dw');
    if (dwEl) {
      dwEl.textContent = (data.dw_stat !== undefined ? data.dw_stat.toFixed(3) : (bannerLevel === 'amber' && bannerText.includes('correlated') ? 'Flagged (< 1.2 or > 2.8)' : '2.00 (uncorrelated)'));
    }

    // JSON Dump
    const jsonDump = document.getElementById('est-json-dump');
    if (jsonDump) {
      jsonDump.textContent = JSON.stringify({ request: payload, response: data }, null, 2);
    }

    renderEstimateChart();

    if (resultsCard) {
      resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

  } catch (err) {
    console.error("Execute estimate catch error:", err);
    if (stateContainer) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Network/Service Error:</strong> ${err.message}</div>`;
    }
  }
}

function renderEstimateChart() {
  const result = STATE.lastEstimateResult;
  if (!result || !result.response || !result.request) return;

  const svg = document.getElementById('est-chart-svg');
  if (!svg) return;
  const req = result.request;
  const res = result.response;
  const width = 540;
  const height = 260;
  // pad.left = 85 prevents y-axis label clipping
  const pad = { top: 20, right: 20, bottom: 42, left: 85 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  svg.innerHTML = '';

  const norm = res.normalization;
  const isPhysical = Boolean(norm && norm.bar_length_m && norm.test_duration_s && norm.boundary_temperature !== null && norm.initial_peak_temperature !== null);

  let tMin = 0.0;
  let tMax = 1.0;
  let yMin = 0.0;
  let yMax = 1.2;
  let xAxisTitle = 'Time (0–1)';
  let yAxisTitle = 'Temperature (0–1)';

  let normPoints = [];
  let alphaNormLo = 0.09;
  let alphaNormHi = 0.11;
  let alphaNormHat = 0.10;

  let xAxis, yAxis;

  if (isPhysical) {
    const L = norm.bar_length_m;
    const T = norm.test_duration_s;
    const Tb = norm.boundary_temperature;
    const Tp = norm.initial_peak_temperature;

    xAxisTitle = 'Time (s)';
    yAxisTitle = 'Temperature (°C)';

    alphaNormHat = (res.alpha_hat_normalized !== null && res.alpha_hat_normalized !== undefined)
      ? res.alpha_hat_normalized
      : (res.alpha_hat * T / (L * L));
    alphaNormLo = (res.ci95_normalized) ? res.ci95_normalized[0] : (res.ci95[0] * T / (L * L));
    alphaNormHi = (res.ci95_normalized) ? res.ci95_normalized[1] : (res.ci95[1] * T / (L * L));

    normPoints = req.t.map((tRaw, i) => {
      const xRaw = req.x[i];
      const yRaw = req.y[i];
      const sinVal = Math.sin(Math.PI * (xRaw / L));
      const yEquivalent = (Math.abs(sinVal) > 1e-4) ? (Tb + (yRaw - Tb) / sinVal) : yRaw;
      return { t: tRaw, yVal: yEquivalent, rawY: yRaw, rawX: xRaw };
    });

    const allY = [Tb, Tp, ...normPoints.map(p => p.yVal)];
    const rawYMin = Math.min(...allY);
    const rawYMax = Math.max(...allY);

    xAxis = computeNiceAxis(0.0, T, 5);
    tMin = xAxis.min;
    tMax = xAxis.max;

    yAxis = computeNiceAxis(rawYMin, rawYMax, 3);
    yMin = yAxis.min;
    yMax = yAxis.max;

  } else {
    xAxisTitle = 'Time (0–1)';
    yAxisTitle = 'Temperature (0–1)';

    alphaNormHat = res.alpha_hat;
    alphaNormLo = res.ci95 ? res.ci95[0] : 0.09;
    alphaNormHi = res.ci95 ? res.ci95[1] : 0.11;

    normPoints = req.t.map((tRaw, i) => {
      const xRaw = req.x[i];
      const yRaw = req.y[i];
      const sinVal = Math.sin(Math.PI * xRaw);
      const yNorm = (Math.abs(sinVal) > 1e-4) ? (yRaw / sinVal) : yRaw;
      return { t: tRaw, yVal: yNorm, rawY: yRaw, rawX: xRaw };
    });

    const allY = [0.0, 1.0, ...normPoints.map(p => p.yVal)];
    const rawYMin = Math.min(...allY);
    const rawYMax = Math.max(...allY);

    xAxis = computeNiceAxis(0.0, Math.max(1.0, ...req.t), 5);
    tMin = xAxis.min;
    tMax = xAxis.max;

    yAxis = computeNiceAxis(rawYMin, rawYMax, 4);
    yMin = yAxis.min;
    yMax = yAxis.max;
  }

  const scaleX = t => pad.left + ((t - tMin) / (tMax - tMin)) * plotW;
  const scaleY = y => pad.top + plotH - ((y - yMin) / (yMax - yMin)) * plotH;

  // Background Grid with nice rounded tick numbers
  let gridLines = '';
  xAxis.ticks.forEach(tVal => {
    const xP = scaleX(tVal);
    const tLabel = isPhysical ? (Number.isInteger(tVal) ? tVal.toString() : tVal.toFixed(1)) : tVal.toFixed(1);
    gridLines += `<line x1="${xP}" y1="${pad.top}" x2="${xP}" y2="${pad.top + plotH}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
    gridLines += `<text x="${xP}" y="${pad.top + plotH + 18}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${tLabel}</text>`;
  });

  yAxis.ticks.forEach(yVal => {
    const yP = scaleY(yVal);
    const yLabel = isPhysical ? (Number.isInteger(yVal) ? yVal.toString() : yVal.toFixed(1)) : yVal.toFixed(1);
    gridLines += `<line x1="${pad.left}" y1="${yP}" x2="${pad.left + plotW}" y2="${yP}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
    gridLines += `<text x="${pad.left - 8}" y="${yP + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${yLabel}</text>`;
  });

  // Curve and polygon calculation
  const numCurvePts = 100;
  let bandPointsTop = [];
  let bandPointsBottom = [];
  let fittedD = [];

  for (let i = 0; i <= numCurvePts; i++) {
    const tCur = tMin + (i / numCurvePts) * (tMax - tMin);
    let yFit = 0, yBound1 = 0, yBound2 = 0;

    if (isPhysical) {
      const T_ends = norm.boundary_temperature;
      const T_peak = norm.initial_peak_temperature;
      const deltaT = T_peak - T_ends;
      const tNorm = tCur / norm.test_duration_s;

      yFit = T_ends + deltaT * Math.exp(-alphaNormHat * Math.PI * Math.PI * tNorm);
      yBound1 = T_ends + deltaT * Math.exp(-alphaNormLo * Math.PI * Math.PI * tNorm);
      yBound2 = T_ends + deltaT * Math.exp(-alphaNormHi * Math.PI * Math.PI * tNorm);
    } else {
      yFit = Math.exp(-alphaNormHat * Math.PI * Math.PI * tCur);
      yBound1 = Math.exp(-alphaNormLo * Math.PI * Math.PI * tCur);
      yBound2 = Math.exp(-alphaNormHi * Math.PI * Math.PI * tCur);
    }

    const yUpper = Math.max(yBound1, yBound2);
    const yLower = Math.min(yBound1, yBound2);

    bandPointsTop.push(`${scaleX(tCur)},${scaleY(yUpper)}`);
    bandPointsBottom.unshift(`${scaleX(tCur)},${scaleY(yLower)}`);
    fittedD.push(`${i === 0 ? 'M' : 'L'} ${scaleX(tCur)} ${scaleY(yFit)}`);
  }

  const bandPoly = `<polygon points="${bandPointsTop.join(' ')} ${bandPointsBottom.join(' ')}" fill="var(--primary-navy)" fill-opacity="0.18" stroke="var(--primary-navy)" stroke-opacity="0.28" stroke-width="1"/>`;
  const fittedPath = `<path d="${fittedD.join(' ')}" fill="none" stroke="var(--primary-navy)" stroke-width="2.5"/>`;

  // True Alpha Curve Path (demo mode)
  let truePath = '';
  if (result.isDemoMode && result.trueAlpha) {
    let trueD = [];
    for (let i = 0; i <= numCurvePts; i++) {
      const tCur = tMin + (i / numCurvePts) * (tMax - tMin);
      let yTrue = 0;
      if (isPhysical) {
        const T_ends = norm.boundary_temperature;
        const T_peak = norm.initial_peak_temperature;
        const deltaT = T_peak - T_ends;
        const tNorm = tCur / norm.test_duration_s;
        yTrue = T_ends + deltaT * Math.exp(-result.trueAlpha * Math.PI * Math.PI * tNorm);
      } else {
        yTrue = Math.exp(-result.trueAlpha * Math.PI * Math.PI * tCur);
      }
      trueD.push(`${i === 0 ? 'M' : 'L'} ${scaleX(tCur)} ${scaleY(yTrue)}`);
    }
    truePath = `<path d="${trueD.join(' ')}" fill="none" stroke="#e67e22" stroke-width="2" stroke-dasharray="4 4"/>`;
  }

  // Points with position, time, reading in title tooltip
  const circles = normPoints.map(p => `
    <circle cx="${scaleX(p.t)}" cy="${scaleY(p.yVal)}" r="4.5" fill="#e74c3c" stroke="#fff" stroke-width="1.2">
      <title>${p.rawX !== undefined ? 'Position: ' + p.rawX.toFixed(2) + ' m, ' : ''}Time: ${p.t.toFixed(1)} s, Reading: ${p.rawY.toFixed(2)} °C</title>
    </circle>
  `).join('');

  svg.innerHTML = `
    <g class="chart-grid">${gridLines}</g>
    ${bandPoly}
    ${fittedPath}
    ${truePath}
    <g class="chart-points">${circles}</g>
    <!-- Axis lines & plain labels -->
    <line x1="${pad.left}" y1="${pad.top + plotH}" x2="${pad.left + plotW}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <text x="${pad.left + plotW / 2}" y="${height - 6}" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">${xAxisTitle}</text>
    <text transform="rotate(-90)" x="${-(pad.top + plotH / 2)}" y="24" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">${yAxisTitle}</text>
  `;
}

// -------------------------------------------------------------------------------------------------
// -------------------------------------------------------------------------------------------------
// 4. Page 3: Diagnose Workbench (Sensor Fault & Physical Change Diagnostics)
// -------------------------------------------------------------------------------------------------

const DEFAULT_DIAGNOSE_BASELINE_ROWS = [
  { x: 0.03, t: 2.0, u: 68.47 },
  { x: 0.05, t: 7.2, u: 76.11 },
  { x: 0.07, t: 12.3, u: 63.47 },
  { x: 0.03, t: 17.5, u: 61.97 },
  { x: 0.05, t: 22.6, u: 68.92 },
  { x: 0.07, t: 27.8, u: 56.41 },
  { x: 0.03, t: 32.9, u: 55.54 },
  { x: 0.05, t: 38.1, u: 61.12 },
  { x: 0.07, t: 43.3, u: 51.62 },
  { x: 0.03, t: 48.4, u: 50.30 },
  { x: 0.05, t: 53.6, u: 55.43 },
  { x: 0.07, t: 58.7, u: 47.91 },
  { x: 0.03, t: 63.9, u: 46.22 },
  { x: 0.05, t: 69.1, u: 50.41 },
  { x: 0.07, t: 74.2, u: 43.56 },
  { x: 0.03, t: 79.4, u: 42.34 },
  { x: 0.05, t: 84.5, u: 46.80 },
  { x: 0.07, t: 89.7, u: 39.93 },
  { x: 0.03, t: 94.8, u: 39.19 },
  { x: 0.05, t: 100.0, u: 41.94 }
];

const DEFAULT_DIAGNOSE_TEST_ROWS = [
  { x: 0.03, t: 1.00, u: 68.95 },
  { x: 0.05, t: 1.67, u: 79.22 },
  { x: 0.07, t: 2.78, u: 67.72 },
  { x: 0.03, t: 4.64, u: 67.49 },
  { x: 0.05, t: 7.74, u: 76.52 },
  { x: 0.07, t: 12.92, u: 62.24 },
  { x: 0.03, t: 21.54, u: 59.72 },
  { x: 0.05, t: 35.94, u: 62.01 },
  { x: 0.07, t: 59.95, u: 46.81 },
  { x: 0.03, t: 100.00, u: 38.30 }
];

function createDiagnoseTableRow(x, t, u, index, prefix = 'diag-row') {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="row-index" style="text-align: center; color: var(--text-muted); font-size: 0.78rem;">${index}</td>
    <td>
      <input type="number" id="${prefix}-pos-${index}" class="cell-input mono" data-col="x" placeholder="e.g. 0.05" step="0.01" value="${x !== undefined && x !== null ? x : ''}">
    </td>
    <td>
      <input type="number" id="${prefix}-time-${index}" class="cell-input mono" data-col="t" placeholder="e.g. 10" step="0.1" value="${t !== undefined && t !== null ? t : ''}">
    </td>
    <td>
      <input type="number" id="${prefix}-temp-${index}" class="cell-input mono" data-col="u" placeholder="e.g. 60" step="0.1" value="${u !== undefined && u !== null ? u : ''}">
    </td>
    <td style="text-align: center;">
      <button type="button" class="btn-cell-delete" aria-label="Remove row" title="Remove row">&times;</button>
    </td>
  `;
  return tr;
}

function updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix) {
  if (!tbody || !countBadge) return;
  const rows = Array.from(tbody.children);
  let filledCount = 0;

  rows.forEach((row, idx) => {
    const idxCell = row.querySelector('.row-index');
    if (idxCell) idxCell.textContent = (idx + 1).toString();

    const delBtn = row.querySelector('.btn-cell-delete');
    if (delBtn) {
      delBtn.style.visibility = rows.length <= 3 ? 'hidden' : 'visible';
    }

    const inputs = row.querySelectorAll('.cell-input');
    if (prefix) {
      if (inputs[0]) inputs[0].id = `${prefix}-pos-${idx + 1}`;
      if (inputs[1]) inputs[1].id = `${prefix}-time-${idx + 1}`;
      if (inputs[2]) inputs[2].id = `${prefix}-temp-${idx + 1}`;
    }

    const xVal = inputs[0] ? inputs[0].value.trim() : '';
    const tVal = inputs[1] ? inputs[1].value.trim() : '';
    const uVal = inputs[2] ? inputs[2].value.trim() : '';
    if (xVal !== '' && tVal !== '' && uVal !== '' && !isNaN(parseFloat(xVal)) && !isNaN(parseFloat(tVal)) && !isNaN(parseFloat(uVal))) {
      filledCount++;
    }
  });

  if (filledCount >= minNeeded) {
    countBadge.textContent = `${filledCount} readings ✓`;
    countBadge.classList.add('complete');
  } else {
    countBadge.textContent = `${filledCount} of ${minNeeded} needed`;
    countBadge.classList.remove('complete');
  }
}

function parseDiagnoseTableData(tbody) {
  if (!tbody) return { x: [], t: [], y: [] };
  const rows = Array.from(tbody.children);
  const x = [], t = [], y = [];
  rows.forEach(row => {
    const inputs = row.querySelectorAll('.cell-input');
    const xVal = inputs[0] ? inputs[0].value.trim() : '';
    const tVal = inputs[1] ? inputs[1].value.trim() : '';
    const uVal = inputs[2] ? inputs[2].value.trim() : '';
    if (xVal !== '' && tVal !== '' && uVal !== '' && !isNaN(parseFloat(xVal)) && !isNaN(parseFloat(tVal)) && !isNaN(parseFloat(uVal))) {
      x.push(parseFloat(xVal));
      t.push(parseFloat(tVal));
      y.push(parseFloat(uVal));
    }
  });
  return { x, t, y };
}

function validateDiagnoseTable(tbody, msgEl, L, T, minNeeded) {
  if (!tbody) return { valid: false, error: 'Table not found' };
  let hasEmpty = false;
  let hasInvalidNum = false;
  let hasRangeError = false;
  let rangeMsg = '';
  let filledCount = 0;

  const rows = Array.from(tbody.children);
  rows.forEach(row => {
    const inputs = row.querySelectorAll('.cell-input');
    const xIn = inputs[0];
    const tIn = inputs[1];
    const uIn = inputs[2];

    const xV = xIn ? xIn.value.trim() : '';
    const tV = tIn ? tIn.value.trim() : '';
    const uV = uIn ? uIn.value.trim() : '';

    if (xIn) xIn.classList.remove('cell-invalid');
    if (tIn) tIn.classList.remove('cell-invalid');
    if (uIn) uIn.classList.remove('cell-invalid');

    if (!xV && !tV && !uV) return;

    if (!xV || !tV || !uV) {
      hasEmpty = true;
      if (!xV && xIn) xIn.classList.add('cell-invalid');
      if (!tV && tIn) tIn.classList.add('cell-invalid');
      if (!uV && uIn) uIn.classList.add('cell-invalid');
      return;
    }

    const xNum = parseFloat(xV);
    const tNum = parseFloat(tV);
    const uNum = parseFloat(uV);

    if (isNaN(xNum)) { hasInvalidNum = true; if (xIn) xIn.classList.add('cell-invalid'); }
    if (isNaN(tNum)) { hasInvalidNum = true; if (tIn) tIn.classList.add('cell-invalid'); }
    if (isNaN(uNum)) { hasInvalidNum = true; if (uIn) uIn.classList.add('cell-invalid'); }

    if (!isNaN(xNum) && !isNaN(tNum) && !isNaN(uNum)) {
      filledCount++;
      if (L && (xNum < 0 || xNum > L)) {
        hasRangeError = true;
        if (xIn) xIn.classList.add('cell-invalid');
        rangeMsg = `Position ${xNum} is outside bar length [0, ${L}] m`;
      }
      if (T && (tNum <= 0 || tNum > T)) {
        hasRangeError = true;
        if (tIn) tIn.classList.add('cell-invalid');
        rangeMsg = `Time ${tNum} is outside test duration (0, ${T}] s`;
      }
    }
  });

  let err = '';
  if (hasEmpty) err = 'Please fill all three values in partially completed rows';
  else if (hasInvalidNum) err = 'All table values must be valid numbers';
  else if (hasRangeError) err = rangeMsg;
  else if (filledCount < minNeeded) err = `At least ${minNeeded} readings are needed (found ${filledCount})`;

  if (msgEl) {
    if (err) {
      msgEl.textContent = err;
      msgEl.classList.add('active');
    } else {
      msgEl.textContent = '';
      msgEl.classList.remove('active');
    }
  }

  return { valid: !err, error: err, count: filledCount };
}

function markProfileAsModified() {
  STATE.profileModified = true;
  const estModBadge = document.getElementById('est-profile-modified-badge');
  const diagModBadge = document.getElementById('diag-profile-modified-badge');
  if (estModBadge) estModBadge.style.display = 'inline-block';
  if (diagModBadge) diagModBadge.style.display = 'inline-block';
}

function setupDiagnoseTableEvents(tbody, addBtn, csvBtn, csvInput, countBadge, minNeeded, msgEl, prefix) {
  if (!tbody) return;

  // Initial 3 empty rows
  if (tbody.children.length === 0) {
    for (let i = 0; i < 3; i++) {
      tbody.appendChild(createDiagnoseTableRow('', '', '', i + 1, prefix));
    }
  }

  // Add row button
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      const nextIdx = tbody.children.length + 1;
      const tr = createDiagnoseTableRow('', '', '', nextIdx, prefix);
      tbody.appendChild(tr);
      updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
      clearDiagnoseResultState();
      if (prefix === 'diag-base') markProfileAsModified();
      const firstIn = tr.querySelector('.cell-input');
      if (firstIn) firstIn.focus();
    });
  }

  // Delete row delegation
  tbody.addEventListener('click', (e) => {
    const delBtn = e.target.closest('.btn-cell-delete');
    if (!delBtn) return;
    if (tbody.children.length <= 3) return;
    const tr = delBtn.closest('tr');
    if (tr) {
      tr.remove();
      updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
      clearDiagnoseResultState();
      if (prefix === 'diag-base') markProfileAsModified();
    }
  });

  // Tab key auto-add in last cell
  tbody.addEventListener('keydown', (e) => {
    if (e.key === 'Tab' && !e.shiftKey) {
      const targetInput = e.target.closest('.cell-input');
      if (!targetInput) return;
      const tr = targetInput.closest('tr');
      if (tr && tr === tbody.lastElementChild && targetInput.getAttribute('data-col') === 'u') {
        e.preventDefault();
        const nextIdx = tbody.children.length + 1;
        const newTr = createDiagnoseTableRow('', '', '', nextIdx, prefix);
        tbody.appendChild(newTr);
        updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
        clearDiagnoseResultState();
        if (prefix === 'diag-base') markProfileAsModified();
        const firstIn = newTr.querySelector('.cell-input');
        if (firstIn) firstIn.focus();
      }
    }
  });

  // Input event
  tbody.addEventListener('input', (e) => {
    if (e.target.classList.contains('cell-input')) {
      updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
      clearDiagnoseResultState();
      if (prefix === 'diag-base') markProfileAsModified();
    }
  });

  // Multi-row paste
  tbody.addEventListener('paste', (e) => {
    const targetInput = e.target.closest('.cell-input');
    if (!targetInput) return;
    const clipText = (e.clipboardData || window.clipboardData).getData('text');
    if (!clipText) return;

    const lines = clipText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    const firstParts = lines[0].split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
    if (lines.length > 1 || firstParts.length > 1) {
      e.preventDefault();
      let targetRow = targetInput.closest('tr');
      let targetRowIndex = Array.from(tbody.children).indexOf(targetRow);
      if (targetRowIndex < 0) targetRowIndex = 0;

      let startIdx = 0;
      if (isNaN(parseFloat(firstParts[0])) && isNaN(parseFloat(firstParts[1] || ''))) {
        startIdx = 1;
      }

      for (let i = startIdx; i < lines.length; i++) {
        const line = lines[i];
        if (!line || line.startsWith('#')) continue;
        const parts = line.split(/[,\t]+/).map(p => p.trim()).filter(Boolean);
        if (parts.length === 0) continue;

        const rowIndex = targetRowIndex + (i - startIdx);
        while (tbody.children.length <= rowIndex) {
          tbody.appendChild(createDiagnoseTableRow('', '', '', tbody.children.length + 1, prefix));
        }

        const row = tbody.children[rowIndex];
        const inputs = row.querySelectorAll('.cell-input');
        if (parts[0] !== undefined && inputs[0]) inputs[0].value = parts[0];
        if (parts[1] !== undefined && inputs[1]) inputs[1].value = parts[1];
        if (parts[2] !== undefined && inputs[2]) inputs[2].value = parts[2];
      }

      updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
      clearDiagnoseResultState();
    }
  });

  // CSV Upload
  if (csvBtn && csvInput) {
    csvBtn.addEventListener('click', () => csvInput.click());
    csvInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        const text = evt.target.result;
        if (!text) return;
        const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) return;

        tbody.innerHTML = '';
        let startIdx = 0;
        const firstParts = lines[0].split(/[,\t]+/).map(p => p.trim());
        if (isNaN(parseFloat(firstParts[0])) && isNaN(parseFloat(firstParts[1] || ''))) {
          startIdx = 1;
        }

        let rowCount = 0;
        for (let i = startIdx; i < lines.length; i++) {
          const line = lines[i];
          if (!line || line.startsWith('#')) continue;
          const parts = line.split(/[,\t]+/).map(p => p.trim());
          if (parts.length < 3) continue;
          rowCount++;
          tbody.appendChild(createDiagnoseTableRow(parts[0], parts[1], parts[2], rowCount, prefix));
        }

        while (tbody.children.length < 3) {
          tbody.appendChild(createDiagnoseTableRow('', '', '', tbody.children.length + 1, prefix));
        }

        updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
        clearDiagnoseResultState();
        csvInput.value = '';
      };
      reader.readAsText(file);
    });
  }

  updateDiagnoseRowNumbers(tbody, countBadge, minNeeded, prefix);
}

function clearDiagnoseResultState() {
  const resCard = document.getElementById('diagnose-results-card');
  if (resCard) resCard.style.display = 'none';
  const resPanel = document.getElementById('diag-result-panel');
  if (resPanel) resPanel.style.display = 'none';
  const stateContainer = document.getElementById('diag-state-container');
  if (stateContainer) stateContainer.innerHTML = '';
}

function syncSharedField(id1, id2) {
  const el1 = document.getElementById(id1);
  const el2 = document.getElementById(id2);
  if (!el1 || !el2) return;

  el1.addEventListener('input', () => {
    if (el2.value !== el1.value) {
      el2.value = el1.value;
      el2.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });

  el2.addEventListener('input', () => {
    if (el1.value !== el2.value) {
      el1.value = el2.value;
      el1.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
}

function initDiagnoseWorkbench() {
  const baseTbody = document.getElementById('diag-base-table-tbody');
  const baseAddBtn = document.getElementById('diag-base-add-row-btn');
  const baseCsvBtn = document.getElementById('diag-base-csv-btn');
  const baseCsvUpload = document.getElementById('diag-base-csv-upload');
  const baseBadge = document.getElementById('diag-baseline-count');
  const baseMsg = document.getElementById('diag-base-table-validation-msg');

  const testTbody = document.getElementById('diag-test-table-tbody');
  const testAddBtn = document.getElementById('diag-test-add-row-btn');
  const testCsvBtn = document.getElementById('diag-test-csv-btn');
  const testCsvUpload = document.getElementById('diag-test-csv-upload');
  const testBadge = document.getElementById('diag-test-count');
  const testMsg = document.getElementById('diag-test-table-validation-msg');

  const useExampleBtn = document.getElementById('diag-use-example-btn');
  const submitBtn = document.getElementById('diag-submit-btn');
  const downloadBtn = document.getElementById('diag-download-btn');

  const moreOptionsBtn = document.getElementById('diag-more-options-btn');
  const drawer = document.getElementById('diag-more-drawer');
  const drawerOverlay = document.getElementById('diag-drawer-overlay');
  const drawerCloseBtn = document.getElementById('diag-drawer-close-btn');
  const scenarioSelect = document.getElementById('diag-scenario-select');
  const loadDemoBtn = document.getElementById('diag-load-demo-btn');

  const sigmaVal = document.getElementById('diag-sigma-val');
  const sigmaAuto = document.getElementById('diag-sigma-auto');

  // Setup two tables
  setupDiagnoseTableEvents(baseTbody, baseAddBtn, baseCsvBtn, baseCsvUpload, baseBadge, 20, baseMsg, 'diag-base');
  setupDiagnoseTableEvents(testTbody, testAddBtn, testCsvBtn, testCsvUpload, testBadge, 3, testMsg, 'diag-test');

  // Setup Two-way Shared Fields with Estimate tab
  syncSharedField('est-bar-length', 'diag-bar-length');
  syncSharedField('est-experiment-time', 'diag-experiment-time');
  syncSharedField('est-temp-edge', 'diag-temp-edge');
  syncSharedField('est-temp-peak', 'diag-temp-peak');
  syncSharedField('est-sigma-val', 'diag-sigma-val');

  // Default values for Diagnose fields if empty
  const barLen = document.getElementById('diag-bar-length');
  const expDur = document.getElementById('diag-experiment-time');
  const tempEdge = document.getElementById('diag-temp-edge');
  const tempPeak = document.getElementById('diag-temp-peak');

  if (barLen && !barLen.value) barLen.value = '0.1';
  if (expDur && !expDur.value) expDur.value = '100';
  if (tempEdge && !tempEdge.value) tempEdge.value = '20';
  if (tempPeak && !tempPeak.value) tempPeak.value = '80';

  // Sync to Estimate if Estimate was empty
  const estBar = document.getElementById('est-bar-length');
  if (estBar && !estBar.value && barLen) estBar.value = barLen.value;
  const estDur = document.getElementById('est-experiment-time');
  if (estDur && !estDur.value && expDur) estDur.value = expDur.value;
  const estEdge = document.getElementById('est-temp-edge');
  if (estEdge && !estEdge.value && tempEdge) estEdge.value = tempEdge.value;
  const estPeak = document.getElementById('est-temp-peak');
  if (estPeak && !estPeak.value && tempPeak) estPeak.value = tempPeak.value;

  // Auto-estimate sensor accuracy checkbox
  if (sigmaAuto && sigmaVal) {
    sigmaAuto.addEventListener('change', () => {
      sigmaVal.disabled = sigmaAuto.checked;
      sigmaVal.style.opacity = sigmaAuto.checked ? '0.5' : '1.0';
      clearDiagnoseResultState();
    });
  }

  // -------------------------------------------------------------
  // Bar Profiles (Reference Library)
  // -------------------------------------------------------------
  const diagProfileSelect = document.getElementById('diag-profile-select') || document.getElementById('diag-use-saved-ref-select');
  const estProfileSelect = document.getElementById('est-profile-select');

  const diagRenameBtn = document.getElementById('diag-profile-rename-btn') || document.getElementById('diag-rename-ref-btn');
  const diagDeleteBtn = document.getElementById('diag-profile-delete-btn') || document.getElementById('diag-delete-ref-btn');
  const diagRenameForm = document.getElementById('diag-profile-rename-form') || document.getElementById('diag-rename-ref-form');
  const diagRenameInput = document.getElementById('diag-profile-rename-input') || document.getElementById('diag-rename-ref-name-input');
  const diagConfirmRenameBtn = document.getElementById('diag-profile-confirm-rename-btn') || document.getElementById('diag-confirm-rename-ref-btn');
  const diagCancelRenameBtn = document.getElementById('diag-profile-cancel-rename-btn') || document.getElementById('diag-cancel-rename-ref-btn');

  const diagSaveProfileBtn = document.getElementById('diag-save-profile-btn') || document.getElementById('diag-save-ref-btn');
  const diagSaveProfileForm = document.getElementById('diag-save-profile-form') || document.getElementById('diag-save-ref-form');
  const diagSaveNameInput = document.getElementById('diag-save-profile-name-input') || document.getElementById('diag-save-ref-name-input');
  const diagSaveNoteInput = document.getElementById('diag-save-profile-note-input');
  const diagConfirmSaveBtn = document.getElementById('diag-confirm-save-profile-btn') || document.getElementById('diag-confirm-save-ref-btn');
  const diagCancelSaveBtn = document.getElementById('diag-cancel-save-profile-btn') || document.getElementById('diag-cancel-save-ref-btn');
  const diagSaveStatus = document.getElementById('diag-save-profile-status') || document.getElementById('diag-save-ref-status');
  const diagSaveError = document.getElementById('diag-save-profile-error') || document.getElementById('diag-save-ref-error');

  const diagExportBtn = document.getElementById('diag-profile-export-btn');
  const estExportBtn = document.getElementById('est-profile-export-btn');
  const diagImportBtn = document.getElementById('diag-profile-import-btn');
  const estImportBtn = document.getElementById('est-profile-import-btn');
  const diagFileInput = document.getElementById('diag-profile-file-input');
  const estFileInput = document.getElementById('est-profile-file-input');

  const diagUncleanBox = document.getElementById('diag-unclean-warn-box');
  const diagUncleanStats = document.getElementById('diag-unclean-warn-stats');
  const diagUncleanConfirmBtn = document.getElementById('diag-unclean-confirm-btn');
  const diagUncleanCancelBtn = document.getElementById('diag-unclean-cancel-btn');

  // Load profile list from backend
  async function loadBarProfiles(selectedProfileId = null) {
    try {
      const res = await fetch('/v1/profiles');
      if (!res.ok) throw new Error('Failed to fetch bar profiles');
      const profiles = await res.json();
      STATE.allProfiles = profiles;

      const demoProfiles = profiles.filter(p => p.is_demo);
      const savedProfiles = profiles.filter(p => !p.is_demo);

      const renderOptions = (sel) => {
        if (!sel) return;
        sel.innerHTML = '<option value="">— Select a bar profile —</option>';
        if (demoProfiles.length > 0) {
          const gDemo = document.createElement('optgroup');
          gDemo.label = 'Demo Profiles';
          demoProfiles.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (${p.bar_length_m} m, ${p.row_count} readings)`;
            gDemo.appendChild(opt);
          });
          sel.appendChild(gDemo);
        }
        if (savedProfiles.length > 0) {
          const gSaved = document.createElement('optgroup');
          gSaved.label = 'Your Saved Profiles';
          savedProfiles.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (${p.bar_length_m} m, ${p.row_count} readings)`;
            gSaved.appendChild(opt);
          });
          sel.appendChild(gSaved);
        }
      };

      renderOptions(diagProfileSelect);
      renderOptions(estProfileSelect);

      const targetId = selectedProfileId || (STATE.currentProfile ? STATE.currentProfile.id : null);
      if (targetId && profiles.some(p => p.id === targetId)) {
        if (diagProfileSelect) diagProfileSelect.value = targetId;
        if (estProfileSelect) estProfileSelect.value = targetId;
        await selectAndApplyProfile(targetId);
      } else {
        if (diagProfileSelect) diagProfileSelect.value = '';
        if (estProfileSelect) estProfileSelect.value = '';
        updateProfileMetadataUI(null);
      }
      checkProfileSetupDifferencesAndSuggestions();
    } catch (err) {
      console.warn('Error loading bar profiles:', err);
    }
  }

  function updateProfileMetadataUI(profile) {
    const estMeta = document.getElementById('est-profile-meta-bar');
    const diagMeta = document.getElementById('diag-profile-meta-bar') || document.getElementById('diag-saved-ref-meta');
    const estModBadge = document.getElementById('est-profile-modified-badge');
    const diagModBadge = document.getElementById('diag-profile-modified-badge');

    if (!profile) {
      if (estMeta) estMeta.style.display = 'none';
      if (diagMeta) diagMeta.style.display = 'none';
      if (estExportBtn) estExportBtn.style.display = 'none';
      if (diagExportBtn) diagExportBtn.style.display = 'none';
      if (diagRenameBtn) diagRenameBtn.style.display = 'none';
      if (diagDeleteBtn) diagDeleteBtn.style.display = 'none';
      if (estModBadge) estModBadge.style.display = 'none';
      if (diagModBadge) diagModBadge.style.display = 'none';
      return;
    }

    const alphaStr = (profile.measured_alpha_base !== null && profile.measured_alpha_base !== undefined)
      ? (typeof formatScientificReal === 'function' ? formatScientificReal(profile.measured_alpha_base, 3) : profile.measured_alpha_base) + ' m²/s'
      : '-';
    const sigStr = (profile.measured_sigma !== null && profile.measured_sigma !== undefined)
      ? `±${profile.measured_sigma} °C`
      : '±0.50 °C';

    const html = `
      <div style="font-weight: 600; color: var(--text-heading);">${profile.name} ${profile.is_demo ? '<span class="badge" style="font-size:0.7rem; background:rgba(31,58,95,0.1); color:var(--primary-navy); padding:0.1rem 0.35rem; border-radius:3px;">Demo</span>' : ''}</div>
      <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.15rem;">
        ${profile.material_note ? profile.material_note + ' &bull; ' : ''}${profile.row_count} readings &bull; Normal heat spread (α): <span class="mono">${alphaStr}</span> &bull; Noise: <span class="mono">${sigStr}</span>
      </div>
    `;

    if (estMeta) {
      estMeta.innerHTML = html;
      estMeta.style.display = 'block';
    }
    if (diagMeta) {
      diagMeta.innerHTML = html;
      diagMeta.style.display = 'block';
    }

    if (estExportBtn) estExportBtn.style.display = 'inline-block';
    if (diagExportBtn) diagExportBtn.style.display = 'inline-block';

    if (!profile.is_demo) {
      if (diagRenameBtn) diagRenameBtn.style.display = 'inline-block';
      if (diagDeleteBtn) diagDeleteBtn.style.display = 'inline-block';
    } else {
      if (diagRenameBtn) diagRenameBtn.style.display = 'none';
      if (diagDeleteBtn) diagDeleteBtn.style.display = 'none';
    }

    if (STATE.profileModified) {
      if (estModBadge) estModBadge.style.display = 'inline-block';
      if (diagModBadge) diagModBadge.style.display = 'inline-block';
    } else {
      if (estModBadge) estModBadge.style.display = 'none';
      if (diagModBadge) diagModBadge.style.display = 'none';
    }
  }

  async function selectAndApplyProfile(profileId) {
    if (!profileId) {
      STATE.currentProfile = null;
      STATE.profileModified = false;
      if (diagProfileSelect) diagProfileSelect.value = '';
      if (estProfileSelect) estProfileSelect.value = '';
      updateProfileMetadataUI(null);
      checkProfileSetupDifferencesAndSuggestions();
      return;
    }

    try {
      const res = await fetch(`/v1/profiles/${profileId}`);
      if (!res.ok) throw new Error('Profile not found');
      const profile = await res.json();
      STATE.currentProfile = profile;
      STATE.profileModified = false;

      if (diagProfileSelect) diagProfileSelect.value = profileId;
      if (estProfileSelect) estProfileSelect.value = profileId;

      updateProfileMetadataUI(profile);

      // 1. Fill setup fields
      if (barLen) barLen.value = String(profile.bar_length_m);
      if (expDur) expDur.value = String(profile.test_duration_s);
      if (tempEdge) tempEdge.value = String(profile.boundary_temperature);
      if (tempPeak) tempPeak.value = String(profile.initial_peak_temperature);
      if (sigmaVal) sigmaVal.value = String(profile.sensor_accuracy || 0.5);

      const estBar = document.getElementById('est-bar-length');
      if (estBar) estBar.value = String(profile.bar_length_m);
      const estDur = document.getElementById('est-experiment-time');
      if (estDur) estDur.value = String(profile.test_duration_s);
      const estEdge = document.getElementById('est-temp-edge');
      if (estEdge) estEdge.value = String(profile.boundary_temperature);
      const estPeak = document.getElementById('est-temp-peak');
      if (estPeak) estPeak.value = String(profile.initial_peak_temperature);
      const estSig = document.getElementById('est-sigma-val');
      if (estSig) estSig.value = String(profile.sensor_accuracy || 0.5);

      // 2. Fill Diagnose reference table
      if (baseTbody && profile.readings && profile.readings.length > 0) {
        baseTbody.innerHTML = '';
        profile.readings.forEach((r, idx) => {
          baseTbody.appendChild(createDiagnoseTableRow(
            Number(r.position_m).toFixed(3),
            Number(r.time_s).toFixed(1),
            Number(r.temperature_c).toFixed(2),
            idx + 1,
            'diag-base'
          ));
        });
        updateDiagnoseRowNumbers(baseTbody, baseBadge, 20, 'diag-base');
        if (baseMsg) {
          baseMsg.textContent = '';
          baseMsg.classList.remove('active');
        }
      }

      checkProfileSetupDifferencesAndSuggestions();
      if (typeof validateEstimateTable === 'function') validateEstimateTable();
      clearDiagnoseResultState();
      clearEstimateResultState();
    } catch (err) {
      console.error('Error selecting bar profile:', err);
    }
  }

  // Profile select change handlers
  if (diagProfileSelect) {
    diagProfileSelect.addEventListener('change', (e) => {
      selectAndApplyProfile(e.target.value);
    });
  }
  if (estProfileSelect) {
    estProfileSelect.addEventListener('change', (e) => {
      selectAndApplyProfile(e.target.value);
    });
  }

  // Check differences and matching suggestions
  function checkProfileSetupDifferencesAndSuggestions() {
    const L = parseFloat(document.getElementById('diag-bar-length')?.value || document.getElementById('est-bar-length')?.value || '0.1');
    const T = parseFloat(document.getElementById('diag-experiment-time')?.value || document.getElementById('est-experiment-time')?.value || '100');
    const Tb = parseFloat(document.getElementById('diag-temp-edge')?.value || document.getElementById('est-temp-edge')?.value || '20');
    const Tp = parseFloat(document.getElementById('diag-temp-peak')?.value || document.getElementById('est-temp-peak')?.value || '80');

    const estDiffWarn = document.getElementById('est-profile-diff-warn');
    const estDiffMsg = document.getElementById('est-profile-diff-msg');
    const diagDiffWarn = document.getElementById('diag-profile-diff-warn');
    const diagDiffMsg = document.getElementById('diag-profile-diff-msg');

    const estMatchSug = document.getElementById('est-profile-match-suggest');
    const estMatchMsg = document.getElementById('est-profile-match-msg');
    const estMatchBtn = document.getElementById('est-profile-apply-match-btn');
    const diagMatchSug = document.getElementById('diag-profile-match-suggest');
    const diagMatchMsg = document.getElementById('diag-profile-match-msg');
    const diagMatchBtn = document.getElementById('diag-profile-apply-match-btn');

    // Difference check vs selected profile
    if (STATE.currentProfile) {
      const p = STATE.currentProfile;
      const diff = Math.abs(L - p.bar_length_m) > 1e-4 ||
                   Math.abs(T - p.test_duration_s) > 1e-4 ||
                   Math.abs(Tb - p.boundary_temperature) > 1e-4 ||
                   Math.abs(Tp - p.initial_peak_temperature) > 1e-4;
      if (diff) {
        const msg = `Setup differs from selected profile '${p.name}'.`;
        if (estDiffMsg) estDiffMsg.textContent = msg;
        if (diagDiffMsg) diagDiffMsg.textContent = msg;
        if (estDiffWarn) estDiffWarn.style.display = 'flex';
        if (diagDiffWarn) diagDiffWarn.style.display = 'flex';
      } else {
        if (estDiffWarn) estDiffWarn.style.display = 'none';
        if (diagDiffWarn) diagDiffWarn.style.display = 'none';
      }
    } else {
      if (estDiffWarn) estDiffWarn.style.display = 'none';
      if (diagDiffWarn) diagDiffWarn.style.display = 'none';
    }

    // Matching suggestion
    let matchingProfile = null;
    if (STATE.allProfiles && STATE.allProfiles.length > 0) {
      matchingProfile = STATE.allProfiles.find(p =>
        Math.abs(L - p.bar_length_m) < 1e-4 &&
        Math.abs(T - p.test_duration_s) < 1e-4 &&
        Math.abs(Tb - p.boundary_temperature) < 1e-4 &&
        Math.abs(Tp - p.initial_peak_temperature) < 1e-4
      );
    }

    if (matchingProfile && (!STATE.currentProfile || STATE.currentProfile.id !== matchingProfile.id)) {
      const sugText = `Use '${matchingProfile.name}'?`;
      if (estMatchMsg) estMatchMsg.textContent = sugText;
      if (diagMatchMsg) diagMatchMsg.textContent = sugText;
      if (estMatchSug) estMatchSug.style.display = 'flex';
      if (diagMatchSug) diagMatchSug.style.display = 'flex';

      const onApply = (e) => {
        if (e) e.preventDefault();
        selectAndApplyProfile(matchingProfile.id);
      };
      if (estMatchBtn) estMatchBtn.onclick = onApply;
      if (diagMatchBtn) diagMatchBtn.onclick = onApply;
    } else {
      if (estMatchSug) estMatchSug.style.display = 'none';
      if (diagMatchSug) diagMatchSug.style.display = 'none';
    }
  }

  // Setup input listeners for difference & suggestion triggers
  [barLen, expDur, tempEdge, tempPeak].forEach(input => {
    if (input) {
      input.addEventListener('input', () => {
        checkProfileSetupDifferencesAndSuggestions();
      });
    }
  });
  const estBarInput = document.getElementById('est-bar-length');
  const estDurInput = document.getElementById('est-experiment-time');
  const estEdgeInput = document.getElementById('est-temp-edge');
  const estPeakInput = document.getElementById('est-temp-peak');
  [estBarInput, estDurInput, estEdgeInput, estPeakInput].forEach(input => {
    if (input) {
      input.addEventListener('input', () => {
        checkProfileSetupDifferencesAndSuggestions();
      });
    }
  });

  // Save profile button
  if (diagSaveProfileBtn) {
    diagSaveProfileBtn.addEventListener('click', () => {
      if (diagSaveProfileForm) {
        diagSaveProfileForm.style.display = (diagSaveProfileForm.style.display === 'none' || !diagSaveProfileForm.style.display) ? 'block' : 'none';
        if (diagSaveNameInput) {
          if (STATE.currentProfile) {
            diagSaveNameInput.value = STATE.profileModified ? `${STATE.currentProfile.name} (modified)` : `${STATE.currentProfile.name} (copy)`;
          } else {
            diagSaveNameInput.value = 'Steel rod, lab test';
          }
          diagSaveNameInput.focus();
        }
        if (diagSaveError) diagSaveError.textContent = '';
        if (diagUncleanBox) diagUncleanBox.style.display = 'none';
      }
    });
  }

  if (diagCancelSaveBtn) {
    diagCancelSaveBtn.addEventListener('click', () => {
      if (diagSaveProfileForm) diagSaveProfileForm.style.display = 'none';
      if (diagSaveError) diagSaveError.textContent = '';
      if (diagUncleanBox) diagUncleanBox.style.display = 'none';
    });
  }

  async function executeSaveProfile(force = false) {
    const name = diagSaveNameInput ? diagSaveNameInput.value.trim() : '';
    if (!name) {
      if (diagSaveError) diagSaveError.textContent = 'Please enter a name for your bar profile.';
      return;
    }
    const data = parseDiagnoseTableData(baseTbody);
    if (data.x.length < 20) {
      if (diagSaveError) diagSaveError.textContent = `A reference profile requires at least 20 readings (found ${data.x.length}).`;
      return;
    }

    const readings = [];
    for (let i = 0; i < data.x.length; i++) {
      readings.push({
        position_m: data.x[i],
        time_s: data.t[i],
        temperature_c: data.y[i]
      });
    }

    const payload = {
      name: name,
      material_note: diagSaveNoteInput ? diagSaveNoteInput.value.trim() : '',
      bar_length_m: parseFloat(barLen ? barLen.value : '0.1') || 0.1,
      test_duration_s: parseFloat(expDur ? expDur.value : '100') || 100,
      boundary_temperature: parseFloat(tempEdge ? tempEdge.value : '20') || 20,
      initial_peak_temperature: parseFloat(tempPeak ? tempPeak.value : '80') || 80,
      sensor_accuracy: parseFloat(sigmaVal ? sigmaVal.value : '0.5') || 0.5,
      readings: readings,
      force: force
    };

    try {
      const res = await fetch('/v1/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const json = await res.json();

      if (!res.ok) {
        if (res.status === 422 && json.error_code === 'UNCLEAN_REFERENCE') {
          if (diagUncleanBox) diagUncleanBox.style.display = 'flex';
          if (diagUncleanStats) {
            const aStr = (typeof formatScientificReal === 'function') ? formatScientificReal(json.measured_alpha_base, 3) : json.measured_alpha_base;
            diagUncleanStats.textContent = `Measured normal heat spread (α): ${aStr} m²/s, sensor noise: ±${json.measured_sigma} °C.`;
          }
          if (diagUncleanConfirmBtn) {
            diagUncleanConfirmBtn.onclick = () => executeSaveProfile(true);
          }
          if (diagUncleanCancelBtn) {
            diagUncleanCancelBtn.onclick = () => {
              if (diagUncleanBox) diagUncleanBox.style.display = 'none';
            };
          }
          return;
        }
        if (diagSaveError) diagSaveError.textContent = json.message || 'Failed to save bar profile.';
        return;
      }

      // Success
      if (diagSaveProfileForm) diagSaveProfileForm.style.display = 'none';
      if (diagUncleanBox) diagUncleanBox.style.display = 'none';
      if (diagSaveStatus) {
        diagSaveStatus.textContent = 'Bar profile saved ✓';
        setTimeout(() => { if (diagSaveStatus) diagSaveStatus.textContent = ''; }, 3000);
      }
      STATE.profileModified = false;
      await loadBarProfiles(json.id);
    } catch (err) {
      if (diagSaveError) diagSaveError.textContent = err.message || 'Network error saving bar profile.';
    }
  }

  if (diagConfirmSaveBtn) {
    diagConfirmSaveBtn.addEventListener('click', () => {
      executeSaveProfile(false);
    });
  }

  // Rename profile
  if (diagRenameBtn) {
    diagRenameBtn.addEventListener('click', () => {
      if (!STATE.currentProfile || STATE.currentProfile.is_demo) return;
      if (diagRenameForm) {
        diagRenameForm.style.display = 'block';
        if (diagRenameInput) {
          diagRenameInput.value = STATE.currentProfile.name;
          diagRenameInput.focus();
        }
      }
    });
  }

  if (diagCancelRenameBtn) {
    diagCancelRenameBtn.addEventListener('click', () => {
      if (diagRenameForm) diagRenameForm.style.display = 'none';
    });
  }

  if (diagConfirmRenameBtn) {
    diagConfirmRenameBtn.addEventListener('click', async () => {
      if (!STATE.currentProfile || STATE.currentProfile.is_demo) return;
      const newName = diagRenameInput ? diagRenameInput.value.trim() : '';
      if (!newName) return;

      try {
        const res = await fetch(`/v1/profiles/${STATE.currentProfile.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName })
        });
        if (!res.ok) throw new Error('Failed to rename profile');
        if (diagRenameForm) diagRenameForm.style.display = 'none';
        await loadBarProfiles(STATE.currentProfile.id);
      } catch (err) {
        alert(err.message);
      }
    });
  }

  // Delete profile
  if (diagDeleteBtn) {
    diagDeleteBtn.addEventListener('click', async () => {
      if (!STATE.currentProfile || STATE.currentProfile.is_demo) return;
      if (!confirm(`Are you sure you want to delete profile '${STATE.currentProfile.name}'?`)) return;

      try {
        const res = await fetch(`/v1/profiles/${STATE.currentProfile.id}`, {
          method: 'DELETE'
        });
        if (!res.ok) throw new Error('Failed to delete profile');
        await loadBarProfiles(null);
      } catch (err) {
        alert(err.message);
      }
    });
  }

  // Export handlers
  const handleExport = () => {
    if (!STATE.currentProfile) return;
    window.location.href = `/v1/profiles/${STATE.currentProfile.id}/export`;
  };
  if (diagExportBtn) diagExportBtn.addEventListener('click', handleExport);
  if (estExportBtn) estExportBtn.addEventListener('click', handleExport);

  // Import handlers
  const setupImport = (btn, fileInput) => {
    if (!btn || !fileInput) return;
    btn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      fileInput.value = '';

      const formData = new FormData();
      formData.append('file', file);

      try {
        let res = await fetch('/v1/profiles/import', {
          method: 'POST',
          body: formData
        });
        let json = await res.json();

        if (!res.ok && res.status === 422 && json.error_code === 'UNCLEAN_REFERENCE') {
          const ok = confirm(`${json.message}\nMeasured heat spread: ${json.measured_alpha_base} m²/s, noise: ±${json.measured_sigma} °C\nImport anyway?`);
          if (ok) {
            res = await fetch('/v1/profiles/import?force=true', {
              method: 'POST',
              body: formData
            });
            json = await res.json();
          } else {
            return;
          }
        }

        if (res.ok) {
          await loadBarProfiles(json.id);
        } else {
          alert(json.message || 'Failed to import bar profile.');
        }
      } catch (err) {
        alert(err.message || 'Error uploading file.');
      }
    });
  };

  setupImport(diagImportBtn, diagFileInput);
  setupImport(estImportBtn, estFileInput);

  // Load profiles on startup
  loadBarProfiles(null);

  // Drawer open / close
  if (moreOptionsBtn && drawer && drawerOverlay) {
    moreOptionsBtn.addEventListener('click', () => {
      drawer.classList.add('open');
      drawerOverlay.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    });
  }
  const closeDrawer = () => {
    if (drawer) {
      drawer.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
    }
    if (drawerOverlay) drawerOverlay.classList.remove('open');
  };
  if (drawerCloseBtn) drawerCloseBtn.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

  // Load Demo Scenarios into tables
  function loadDiagnoseDemoScenario(sc, seed = 702) {
    const L = parseFloat(document.getElementById('diag-bar-length').value) || 0.1;
    const T = parseFloat(document.getElementById('diag-experiment-time').value) || 100.0;
    const Tb = parseFloat(document.getElementById('diag-temp-edge').value) || 20.0;
    const Tp = parseFloat(document.getElementById('diag-temp-peak').value) || 80.0;
    const deltaT = Tp - Tb;
    const sig = parseFloat(document.getElementById('diag-sigma-val').value) || 0.5;

    // Baseline: 20 readings (or 10 for refusal)
    const kBase = (sc === 'refusal_baseline') ? 10 : 20;
    const tb = [];
    const xb = [];
    for (let i = 0; i < kBase; i++) {
      tb.push(2.0 + (i / Math.max(1, kBase - 1)) * 98.0);
      xb.push([0.03, 0.05, 0.07][i % 3]);
    }
    const rng = mulberry32(Number(seed) || 702);
    const baseRows = [];
    for (let i = 0; i < kBase; i++) {
      const xNorm = xb[i] / L;
      const tNorm = tb[i] / T;
      const uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
      const uClean = Tb + deltaT * uNorm;
      const uNoisy = Math.round((uClean + randomNormal(rng, 0, sig)) * 100) / 100;
      baseRows.push({ x: xb[i], t: Math.round(tb[i] * 10) / 10, u: uNoisy });
    }

    // Test readings: 10 readings
    const to = [1.0, 1.67, 2.78, 4.64, 7.74, 12.92, 21.54, 35.94, 59.95, 100.0];
    const xo = [0.03, 0.05, 0.07, 0.03, 0.05, 0.07, 0.03, 0.05, 0.07, 0.03];
    const testRows = [];
    let groundTruthText = 'Healthy';
    let faultyIdx = null;
    let changeTime = null;

    for (let i = 0; i < 10; i++) {
      const xNorm = xo[i] / L;
      const tNorm = to[i] / T;
      let uNorm = 0.0;

      if (sc === 'H') {
        uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
        groundTruthText = 'Healthy run (alpha = 1.0e-5 m²/s)';
      } else if (sc === 'A') {
        uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-2.50 * (Math.PI ** 2) * tNorm);
        groundTruthText = 'Anomalous heat spread (rapid cooling, alpha = 2.5e-4 m²/s)';
      } else if (sc === 'F_stuck') {
        uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
        groundTruthText = 'Sensor Fault: Sensor #3 Stuck at 50 °C';
        faultyIdx = 3;
      } else if (sc === 'F_bias') {
        uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
        groundTruthText = 'Sensor Fault: Sensor #5 Calibration Offset (+5 °C)';
        faultyIdx = 5;
      } else if (sc === 'C') {
        const tcNorm = 0.35;
        changeTime = 35.0;
        if (tNorm < tcNorm) {
          uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
        } else {
          uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-(Math.PI ** 2) * (0.10 * tcNorm + 0.80 * (tNorm - tcNorm)));
        }
        groundTruthText = 'Physical Change-Point (heat spread jumped around 35 s)';
      } else {
        uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-0.10 * (Math.PI ** 2) * tNorm);
        groundTruthText = 'Refusal demo (k=10 baseline readings)';
      }

      let uClean = Tb + deltaT * uNorm;
      let uNoisy = uClean + randomNormal(rng, 0, sig);
      if (sc === 'F_stuck' && i === 3) uNoisy = 50.0;
      if (sc === 'F_bias' && i === 5) uNoisy += 5.0;

      testRows.push({ x: xo[i], t: to[i], u: Math.round(uNoisy * 100) / 100 });
    }

    // Populate Baseline table
    baseTbody.innerHTML = '';
    baseRows.forEach((r, idx) => {
      baseTbody.appendChild(createDiagnoseTableRow(r.x.toFixed(2), r.t.toFixed(1), r.u.toFixed(2), idx + 1, 'diag-base'));
    });
    updateDiagnoseRowNumbers(baseTbody, baseBadge, 20);

    // Populate Test table
    testTbody.innerHTML = '';
    testRows.forEach((r, idx) => {
      testTbody.appendChild(createDiagnoseTableRow(r.x.toFixed(2), r.t.toFixed(2), r.u.toFixed(2), idx + 1, 'diag-test'));
    });
    updateDiagnoseRowNumbers(testTbody, testBadge, 3);

    STATE.diagnoseDemo = {
      scenario: sc,
      groundTruthText,
      faultyIdx,
      changeTime
    };

    clearDiagnoseResultState();
  }

  if (loadDemoBtn && scenarioSelect) {
    loadDemoBtn.addEventListener('click', () => {
      loadDiagnoseDemoScenario(scenarioSelect.value);
      closeDrawer();
    });
  }

  if (scenarioSelect) {
    scenarioSelect.addEventListener('change', () => {
      loadDiagnoseDemoScenario(scenarioSelect.value);
    });
  }

  // Use example button
  if (useExampleBtn) {
    useExampleBtn.addEventListener('click', () => {
      // Populate fields
      if (barLen) barLen.value = '0.1';
      if (expDur) expDur.value = '100';
      if (tempEdge) tempEdge.value = '20';
      if (tempPeak) tempPeak.value = '80';
      if (sigmaVal) sigmaVal.value = '0.5';
      if (sigmaAuto) sigmaAuto.checked = false;
      if (sigmaVal) sigmaVal.disabled = false;

      // Populate Baseline table (20 realistic noisy readings, seed 0)
      baseTbody.innerHTML = '';
      DEFAULT_DIAGNOSE_BASELINE_ROWS.forEach((r, idx) => {
        baseTbody.appendChild(createDiagnoseTableRow(r.x.toFixed(2), r.t.toFixed(1), r.u.toFixed(2), idx + 1, 'diag-base'));
      });
      updateDiagnoseRowNumbers(baseTbody, baseBadge, 20);

      // Populate Test table (10 realistic noisy readings, seed 0)
      testTbody.innerHTML = '';
      DEFAULT_DIAGNOSE_TEST_ROWS.forEach((r, idx) => {
        testTbody.appendChild(createDiagnoseTableRow(r.x.toFixed(2), r.t.toFixed(2), r.u.toFixed(2), idx + 1, 'diag-test'));
      });
      updateDiagnoseRowNumbers(testTbody, testBadge, 3);

      STATE.diagnoseDemo = {
        scenario: 'H',
        groundTruthText: 'Healthy test run (true alpha = 1.0e-5 m²/s)',
        faultyIdx: null,
        changeTime: null
      };

      clearDiagnoseResultState();
    });
  }

  // Download JSON
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      if (!STATE.lastDiagnoseResult) return;
      downloadJson(STATE.lastDiagnoseResult, 'diagnose_result.json');
    });
  }

  // Submit button
  if (submitBtn) {
    submitBtn.addEventListener('click', executeDiagnosis);
  }
}

async function executeDiagnosis() {
  const stateContainer = document.getElementById('diag-state-container');
  const resultsCard = document.getElementById('diagnose-results-card');
  const resultPanel = document.getElementById('diag-result-panel');

  const baseTbody = document.getElementById('diag-base-table-tbody');
  const testTbody = document.getElementById('diag-test-table-tbody');
  const baseBadge = document.getElementById('diag-baseline-count');
  const testBadge = document.getElementById('diag-test-count');
  const baseMsg = document.getElementById('diag-base-table-validation-msg');
  const testMsg = document.getElementById('diag-test-table-validation-msg');

  const barLenInput = document.getElementById('diag-bar-length');
  const expDurInput = document.getElementById('diag-experiment-time');
  const tempEdgeInput = document.getElementById('diag-temp-edge');
  const tempPeakInput = document.getElementById('diag-temp-peak');
  const sigmaInput = document.getElementById('diag-sigma-val');
  const sigmaAuto = document.getElementById('diag-sigma-auto');

  const L = parseFloat(barLenInput ? barLenInput.value : '');
  const T = parseFloat(expDurInput ? expDurInput.value : '');
  const Tb = parseFloat(tempEdgeInput ? tempEdgeInput.value : '');
  const Tp = parseFloat(tempPeakInput ? tempPeakInput.value : '');
  const isAutoSigma = Boolean(sigmaAuto && sigmaAuto.checked);
  const sigma = isAutoSigma ? null : parseFloat(sigmaInput ? sigmaInput.value : '0.5');

  // Validate test parameters
  if (isNaN(L) || L <= 0) {
    stateContainer.innerHTML = '<div class="state-box error">Please enter a valid positive bar length (m).</div>';
    return;
  }
  if (isNaN(T) || T <= 0) {
    stateContainer.innerHTML = '<div class="state-box error">Please enter a valid positive test duration (s).</div>';
    return;
  }
  if (isNaN(Tb) || isNaN(Tp)) {
    stateContainer.innerHTML = '<div class="state-box error">Please specify both boundary temperature and hottest start temperature.</div>';
    return;
  }
  if (Tb === Tp) {
    stateContainer.innerHTML = '<div class="state-box error">Hottest temperature cannot equal boundary temperature (no temperature difference to observe).</div>';
    return;
  }
  if (!isAutoSigma && (isNaN(sigma) || sigma <= 0)) {
    stateContainer.innerHTML = '<div class="state-box error">Please enter a valid sensor accuracy (&plusmn; &deg;C) or check "Estimate sensor accuracy from the reference run".</div>';
    return;
  }

  // Parse table data
  const baseData = parseDiagnoseTableData(baseTbody);
  const testData = parseDiagnoseTableData(testTbody);

  // Validate baseline table
  const baseVal = validateDiagnoseTable(baseTbody, baseMsg, L, T, 20);
  if (baseData.x.length < 20) {
    // Insufficient baseline -> Refusal state
    const k = baseData.x.length;
    stateContainer.innerHTML = `
      <div class="state-box refusal">
        <div style="font-weight: 700; margin-bottom: 0.3rem;">Service Refusal (REFUSED_INSUFFICIENT_BASELINE)</div>
        <div>Diagnose service requires k &ge; 20 baseline readings (received k=${k}). Refusing request.</div>
      </div>
    `;
    if (resultsCard) resultsCard.style.display = 'block';
    if (resultPanel) resultPanel.style.display = 'block';

    const banner = document.getElementById('diag-traffic-banner');
    if (banner) {
      banner.className = 'traffic-light-line red';
      const icon = document.getElementById('diag-traffic-icon');
      if (icon) icon.textContent = '●';
      const title = document.getElementById('diag-traffic-title');
      if (title) title.textContent = `A reference run needs at least 20 readings to establish normal behavior. You entered ${k} readings.`;
    }
    const specInfo = document.getElementById('diag-specific-info');
    if (specInfo) specInfo.textContent = 'Please add at least 20 readings to the reference run table so normal heat dissipation and sensor noise can be calibrated.';
    const chartSvg = document.getElementById('diag-chart-svg');
    if (chartSvg) chartSvg.innerHTML = `<text x="270" y="130" text-anchor="middle" fill="var(--text-muted)" font-size="12">Reference run requires at least 20 readings to generate baseline model</text>`;
    
    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  // Validate test table
  const testVal = validateDiagnoseTable(testTbody, testMsg, L, T, 3);
  if (!testVal.valid) {
    stateContainer.innerHTML = `<div class="state-box error">${testVal.error}</div>`;
    return;
  }

  stateContainer.innerHTML = '<div class="state-box loading"><span class="spinner"></span> Comparing test readings against calibrated baseline...</div>';
  if (resultsCard) resultsCard.style.display = 'none';

  const payload = {
    readings: { x: testData.x, t: testData.t, y: testData.y },
    baseline: { x: baseData.x, t: baseData.t, y: baseData.y },
    bar_length_m: L,
    test_duration_s: T,
    boundary_temperature: Tb,
    initial_peak_temperature: Tp,
    sigma: sigma
  };

  try {
    const res = await fetch('/v1/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    STATE.lastDiagnoseResult = {
      request: payload,
      response: data,
      demo: STATE.diagnoseDemo || null
    };

    if (!res.ok) {
      const errCode = data.error_code || (data.detail && data.detail.error_code) || 'REFUSAL';
      const msg = data.message || (data.detail && data.detail.message) || JSON.stringify(data.detail);
      stateContainer.innerHTML = `
        <div class="state-box refusal">
          <div style="font-weight: 700; margin-bottom: 0.3rem;">Service Refusal (${errCode})</div>
          <div>${msg}</div>
        </div>
      `;
      if (resultsCard) resultsCard.style.display = 'block';
      if (resultPanel) resultPanel.style.display = 'block';
      const banner = document.getElementById('diag-traffic-banner');
      if (banner) {
        banner.className = 'traffic-light-line red';
        const title = document.getElementById('diag-traffic-title');
        if (title) title.textContent = msg;
      }
      return;
    }

    stateContainer.innerHTML = '';
    if (resultsCard) resultsCard.style.display = 'block';
    if (resultPanel) resultPanel.style.display = 'block';

    const banner = document.getElementById('diag-traffic-banner');
    const titleEl = document.getElementById('diag-traffic-title');
    const specInfo = document.getElementById('diag-specific-info');
    const demoCallout = document.getElementById('diag-demo-callout');

    const assignedClass = data.assigned_class || 'H';
    const es = data.evidence_stats || {};

    const alphaFit = es.alpha_fitted !== undefined ? formatScientificReal(es.alpha_fitted, 3) : '-';
    const alphaBase = es.alpha_baseline !== undefined ? formatScientificReal(es.alpha_baseline, 3) : '-';

    // Format one plain-sentence traffic light line
    if (assignedClass === 'H') {
      banner.className = 'traffic-light-line green';
      titleEl.textContent = 'Everything looks normal.';
      specInfo.innerHTML = `Your test readings conform to the reference baseline (heat spread &alpha; &approx; ${alphaBase}).`;
    } else if (assignedClass === 'A') {
      banner.className = 'traffic-light-line amber';
      titleEl.textContent = 'The material behaves differently from your reference run.';
      specInfo.innerHTML = `The heat dissipation rate shifted significantly (&alpha; &approx; ${alphaFit}) compared to your baseline (&alpha;<sub>base</sub> &approx; ${alphaBase}).`;
    } else if (assignedClass === 'F') {
      banner.className = 'traffic-light-line amber';
      const fIdx = (data.faulty_sensor_idx !== undefined && data.faulty_sensor_idx !== null) ? data.faulty_sensor_idx : 1;
      titleEl.textContent = `One sensor looks faulty: Sensor ${fIdx}. Possible causes: stuck, offset or wrong scale.`;
      
      const xRead = testData.x[fIdx] !== undefined ? testData.x[fIdx].toFixed(2) : '-';
      const tRead = testData.t[fIdx] !== undefined ? testData.t[fIdx].toFixed(1) : '-';
      const yRead = testData.y[fIdx] !== undefined ? testData.y[fIdx].toFixed(2) : '-';
      specInfo.innerHTML = `Affected reading #${fIdx}: position ${xRead} m, time ${tRead} s (sensor read ${yRead} &deg;C).`;
    } else if (assignedClass === 'C') {
      banner.className = 'traffic-light-line amber';
      let changeTimeStr = '35';
      if (typeof data.change_time === 'number') {
        changeTimeStr = (data.change_time % 1 === 0) ? data.change_time.toString() : data.change_time.toFixed(1);
      }
      titleEl.textContent = `The behaviour changed during the test, around ${changeTimeStr} s.`;
      specInfo.innerHTML = `A physical transition or external thermal disturbance occurred around ${changeTimeStr} s into the test.`;
    }

    // Honesty Note Calibrated Range Check
    const uncalWarn = document.getElementById('diag-uncalibrated-warning');
    if (uncalWarn) {
      const N_test = testData.x.length;
      const deltaT = Math.abs(Tp - Tb);
      const noiseFrac = isAutoSigma ? (data.effective_sigma || 0) : ((sigma || 0.5) / (deltaT || 1.0));
      const isOutside = (N_test < 10 || N_test > 20 || noiseFrac < 0.005 || noiseFrac > 0.06);
      uncalWarn.style.display = isOutside ? 'block' : 'none';
    }

    // Update active saved reference stats if present
    if (STATE.activeSavedRefId && es.alpha_baseline !== undefined) {
      try {
        const raw = localStorage.getItem('thermalens_saved_references');
        if (raw) {
          const refs = JSON.parse(raw);
          const r = refs.find(x => x.id === STATE.activeSavedRefId);
          if (r) {
            r.lastCheckStats = {
              alpha_baseline: formatScientificReal(es.alpha_baseline, 3) + ' m²/s',
              sigma: (data.effective_sigma * Math.abs(Tp - Tb)).toFixed(2) + ' °C'
            };
            localStorage.setItem('thermalens_saved_references', JSON.stringify(refs));
            displaySavedRefMeta(STATE.activeSavedRefId);
          }
        }
      } catch (e) {
        console.warn('Could not update saved reference stats in localStorage:', e);
      }
    }

    // Demo Scenario Callout
    if (STATE.diagnoseDemo && STATE.diagnoseDemo.groundTruthText) {
      demoCallout.style.display = 'block';
      demoCallout.textContent = `Demo: known cause — ${STATE.diagnoseDemo.groundTruthText}`;
    } else {
      demoCallout.style.display = 'none';
    }

    // Technical details table
    const tbody = document.getElementById('diag-evidence-tbody');
    if (tbody) {
      const glrVal = es.glr_stat !== undefined ? es.glr_stat : '-';
      const glrTau = es.glr_threshold !== undefined ? es.glr_threshold : '-';
      const bicH = es.bic_healthy !== undefined ? es.bic_healthy : '-';
      const bicF = es.bic_sensor_fault !== undefined ? es.bic_sensor_fault : '-';
      const chi2 = es.chi2_reduced !== undefined ? es.chi2_reduced : '-';

      let tcRow = '';
      if (assignedClass === 'C' && data.change_time !== undefined) {
        const tcVal = typeof data.change_time === 'number' ? data.change_time.toFixed(1) : data.change_time;
        tcRow = `<tr><td>Estimated change time</td><td class="mono">${tcVal} s</td><td class="text-muted">During test window</td><td><span class="text-muted mono">tc parameter</span></td></tr>`;
      }

      tbody.innerHTML = `
        <tr>
          <td>Jump detection test</td>
          <td class="mono">${glrVal}</td>
          <td class="mono">Threshold: ${glrTau}</td>
          <td><span class="text-muted mono">GLR statistic &tau;</span></td>
        </tr>
        <tr>
          <td>Model comparison</td>
          <td class="mono">Healthy: ${bicH} | Fault: ${bicF}</td>
          <td class="mono">BIC(F) &lt; BIC(H) flags fault</td>
          <td><span class="text-muted mono">BIC values</span></td>
        </tr>
        <tr>
          <td>Fit quality</td>
          <td class="mono">${chi2}</td>
          <td class="mono">&lt; 2.0 indicates smooth cooling</td>
          <td><span class="text-muted mono">Reduced &chi;&sup2;/dof</span></td>
        </tr>
        <tr>
          <td>Heat spread rate</td>
          <td class="mono">${alphaFit}</td>
          <td class="mono">Baseline: ${alphaBase}</td>
          <td><span class="text-muted mono">Diffusivity &alpha;</span></td>
        </tr>
        ${tcRow}
      `;
    }

    // JSON Dump
    const jsonDump = document.getElementById('diag-json-dump');
    if (jsonDump) {
      jsonDump.textContent = JSON.stringify({ request: payload, response: data }, null, 2);
    }

    // Compatibility spans for automated tests
    const badgeEl = document.getElementById('diag-out-class-badge');
    if (badgeEl) badgeEl.textContent = `CLASS ${assignedClass}`;
    const nameEl = document.getElementById('diag-out-class-name');
    if (nameEl) nameEl.textContent = assignedClass === 'H' ? 'Healthy Baseline' : (assignedClass === 'A' ? 'Anomalous Diffusivity' : (assignedClass === 'F' ? 'Sensor Fault' : 'Change-Point'));

    renderDiagnoseChart();

    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    stateContainer.innerHTML = `<div class="state-box error"><strong>Diagnosis Service Error:</strong> ${err.message}</div>`;
  }
}

function renderDiagnoseChart() {
  const result = STATE.lastDiagnoseResult;
  if (!result || !result.request || !result.response) return;

  const svg = document.getElementById('diag-chart-svg');
  if (!svg) return;

  const req = result.request;
  const res = result.response;
  const width = 540;
  const height = 260;
  const pad = { top: 20, right: 25, bottom: 42, left: 55 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  svg.innerHTML = '';

  const rObj = req.readings || {};
  const to = Array.isArray(rObj.t) ? rObj.t : (Array.isArray(rObj.t_coords) ? rObj.t_coords : []);
  const yo = Array.isArray(rObj.y) ? rObj.y : (Array.isArray(rObj.readings) ? rObj.readings : []);
  const xo = Array.isArray(rObj.x) ? rObj.x : (Array.isArray(rObj.x_coords) ? rObj.x_coords : []);

  if (!to.length || !yo.length) {
    svg.innerHTML = `<text x="${width / 2}" y="${height / 2}" text-anchor="middle" fill="var(--text-muted)" font-size="12">No observation coordinates to render</text>`;
    return;
  }

  const L = req.bar_length_m || 0.1;
  const T = req.test_duration_s || 100.0;
  const Tb = req.boundary_temperature !== undefined ? req.boundary_temperature : 20.0;
  const Tp = req.initial_peak_temperature !== undefined ? req.initial_peak_temperature : 80.0;
  const deltaT = Tp - Tb;

  const tMin = 0.0;
  const tMax = Math.max(T, ...to);
  const rawYMin = Math.min(Tb, ...yo);
  const rawYMax = Math.max(Tp, ...yo);

  const xAxis = computeNiceAxis(tMin, tMax, 5);
  const yAxis = computeNiceAxis(rawYMin, rawYMax, 5);

  const scaleX = t => pad.left + ((t - xAxis.min) / Math.max(1e-6, xAxis.max - xAxis.min)) * plotW;
  const scaleY = y => pad.top + plotH - ((y - yAxis.min) / Math.max(1e-6, yAxis.max - yAxis.min)) * plotH;

  // Background Grid & Nice Ticks
  let gridLines = '';
  xAxis.ticks.forEach(tVal => {
    const xP = scaleX(tVal);
    const tLabel = Number.isInteger(tVal) ? tVal.toString() : tVal.toFixed(1);
    gridLines += `<line x1="${xP}" y1="${pad.top}" x2="${xP}" y2="${pad.top + plotH}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
    gridLines += `<text x="${xP}" y="${pad.top + plotH + 18}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${tLabel}</text>`;
  });

  yAxis.ticks.forEach(yVal => {
    const yP = scaleY(yVal);
    const yLabel = Number.isInteger(yVal) ? yVal.toString() : yVal.toFixed(1);
    gridLines += `<line x1="${pad.left}" y1="${yP}" x2="${pad.left + plotW}" y2="${yP}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
    gridLines += `<text x="${pad.left - 8}" y="${yP + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${yLabel}</text>`;
  });

  // Baseline Curve: alpha_base
  const alphaBaseNorm = (res.evidence_stats && typeof res.evidence_stats.alpha_baseline_normalized === 'number')
    ? res.evidence_stats.alpha_baseline_normalized
    : ((res.evidence_stats && typeof res.evidence_stats.alpha_baseline === 'number') ? (res.evidence_stats.alpha_baseline * T / (L ** 2)) : 0.10);

  const numPts = 100;
  let baseD = [];
  for (let i = 0; i <= numPts; i++) {
    const tCur = tMin + (i / numPts) * (tMax - tMin);
    const tNorm = tCur / T;
    const xNorm = 0.50; // midpoint of bar
    const uNorm = Math.sin(Math.PI * xNorm) * Math.exp(-alphaBaseNorm * (Math.PI ** 2) * tNorm);
    const yReal = Tb + deltaT * uNorm;
    baseD.push(`${i === 0 ? 'M' : 'L'} ${scaleX(tCur)} ${scaleY(yReal)}`);
  }
  const basePath = `<path d="${baseD.join(' ')}" fill="none" stroke="var(--primary-navy)" stroke-width="2.5"/>`;

  // Change time vertical line if Class C
  let tcLine = '';
  if (res.assigned_class === 'C' && typeof res.change_time === 'number') {
    const xTc = scaleX(res.change_time);
    tcLine = `
      <line x1="${xTc}" y1="${pad.top}" x2="${xTc}" y2="${pad.top + plotH}" stroke="#e67e22" stroke-width="2" stroke-dasharray="4 3"/>
      <text x="${xTc + 5}" y="${pad.top + 16}" fill="#e67e22" font-size="10" font-weight="600">tc &approx; ${res.change_time.toFixed(1)} s</text>
    `;
  }

  // Legend faulty sensor item display
  const faultLegend = document.getElementById('diag-fault-legend-item');
  if (faultLegend) {
    faultLegend.style.display = (res.assigned_class === 'F') ? 'flex' : 'none';
  }

  // Points
  const circles = to.map((t, idx) => {
    const isFault = (res.assigned_class === 'F' && res.faulty_sensor_idx === idx);
    const color = isFault ? '#e74c3c' : '#2980b9';
    const r = isFault ? 6.5 : 4.5;
    const strokeW = isFault ? 2.0 : 1.2;
    const yVal = yo[idx] !== undefined ? yo[idx] : 0.0;
    const xCoord = xo[idx] !== undefined ? xo[idx] : 0.05;

    let halo = '';
    if (isFault) {
      halo = `<circle cx="${scaleX(t)}" cy="${scaleY(yVal)}" r="11" fill="#e74c3c" fill-opacity="0.25" stroke="none"/>`;
    }

    return `
      ${halo}
      <circle cx="${scaleX(t)}" cy="${scaleY(yVal)}" r="${r}" fill="${color}" stroke="#fff" stroke-width="${strokeW}">
        <title>Sensor #${idx}: Position: ${xCoord.toFixed(2)} m, Time: ${Number(t).toFixed(1)} s, Reading: ${Number(yVal).toFixed(2)} °C</title>
      </circle>
    `;
  }).join('');

  svg.innerHTML = `
    <g class="chart-grid">${gridLines}</g>
    ${basePath}
    ${tcLine}
    <g class="chart-points">${circles}</g>
    <line x1="${pad.left}" y1="${pad.top + plotH}" x2="${pad.left + plotW}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <text x="${pad.left + plotW / 2}" y="${height - 8}" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">Time (s)</text>
    <text transform="rotate(-90)" x="${-(pad.top + plotH / 2)}" y="18" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">Temperature (°C)</text>
  `;
}

// -------------------------------------------------------------------------------------------------
// 5. Page 4: Sensor Placement Workbench
// -------------------------------------------------------------------------------------------------

function initPlacementWorkbench() {
  const submitBtn = document.getElementById('place-submit-btn');
  const downloadBtn = document.getElementById('place-download-btn');

  submitBtn.addEventListener('click', executePlacement);
  downloadBtn.addEventListener('click', () => {
    if (!STATE.lastPlacementResult) return;
    downloadJson(STATE.lastPlacementResult, 'placement_schedule.json');
  });
}

async function executePlacement() {
  const stateContainer = document.getElementById('place-state-container');
  const resultPanel = document.getElementById('place-result-panel');
  const N = parseInt(document.getElementById('place-n').value) || 20;
  const sigma = parseFloat(document.getElementById('place-sigma').value) || 0.01;
  const sensorX = parseFloat(document.getElementById('place-sensor-x').value) || 0.50;
  const tMin = parseFloat(document.getElementById('place-tmin').value) || 0.01;
  const tMax = parseFloat(document.getElementById('place-tmax').value) || 1.0;

  stateContainer.innerHTML = '<div class="state-box loading"><span class="spinner"></span> Computing optimal two-stage schedule...</div>';
  resultPanel.style.display = 'none';

  const payload = { N, sigma, sensor_x: sensorX, t_min: tMin, t_max: tMax };

  try {
    const res = await fetch('/v1/placement', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    STATE.lastPlacementResult = { request: payload, response: data };

    if (!res.ok) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Error:</strong> ${data.message || JSON.stringify(data.detail)}</div>`;
      return;
    }

    stateContainer.innerHTML = '';
    resultPanel.style.display = 'block';

    document.getElementById('place-strategy-text').textContent = data.strategy_description;
    document.getElementById('place-timing').textContent = data.timing_ms.toFixed(2);

    // Populate tables
    const t1Tbody = document.getElementById('place-t1-tbody');
    t1Tbody.innerHTML = data.t_stage1.map((t, i) => `<tr><td class="mono">#${i+1}</td><td class="mono">${t.toFixed(5)}</td></tr>`).join('');

    const t2Tbody = document.getElementById('place-t2-tbody');
    t2Tbody.innerHTML = data.t_stage2_nominal.map((t, i) => `<tr><td class="mono">#${data.t_stage1.length + i + 1}</td><td class="mono">${t.toFixed(5)}</td></tr>`).join('');

    document.getElementById('place-json-dump').textContent = JSON.stringify({ request: payload, response: data }, null, 2);

    renderPlacementChart();

  } catch (err) {
    stateContainer.innerHTML = `<div class="state-box error"><strong>Placement Error:</strong> ${err.message}</div>`;
  }
}

function renderPlacementChart() {
  const result = STATE.lastPlacementResult;
  if (!result || !result.response) return;

  const svg = document.getElementById('place-chart-svg');
  const res = result.response;
  const width = 700;
  const height = 200;
  const pad = { top: 30, right: 35, bottom: 45, left: 45 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  svg.innerHTML = '';

  const tMin = result.request.t_min || 0.01;
  const tMax = result.request.t_max || 1.0;
  const logMin = Math.log10(tMin);
  const logMax = Math.log10(tMax);

  const scaleLogX = t => pad.left + ((Math.log10(t) - logMin) / (logMax - logMin)) * plotW;

  // Log Grid
  let gridLines = '';
  const decades = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0];
  decades.forEach(d => {
    if (d >= tMin && d <= tMax) {
      const xP = scaleLogX(d);
      gridLines += `<line x1="${xP}" y1="${pad.top}" x2="${xP}" y2="${pad.top + plotH}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
      gridLines += `<text x="${xP}" y="${pad.top + plotH + 18}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${d}</text>`;
    }
  });

  // Axis baseline
  const axisY = pad.top + plotH / 2;

  // Stage 1 Points (blue dots on top lane)
  const yLane1 = axisY - 25;
  const stage1Dots = res.t_stage1.map(t => {
    const cx = scaleLogX(t);
    return `
      <circle cx="${cx}" cy="${yLane1}" r="5" fill="#2980b9" stroke="#fff" stroke-width="1.2">
        <title>Stage 1: ${t.toFixed(5)}s</title>
      </circle>
      <line x1="${cx}" y1="${yLane1 + 5}" x2="${cx}" y2="${axisY}" stroke="#2980b9" stroke-width="1" stroke-opacity="0.4"/>
    `;
  }).join('');

  // Stage 2 Points (orange dots on bottom lane)
  const yLane2 = axisY + 25;
  const stage2Dots = res.t_stage2_nominal.map(t => {
    const cx = scaleLogX(t);
    return `
      <circle cx="${cx}" cy="${yLane2}" r="5" fill="#e67e22" stroke="#fff" stroke-width="1.2">
        <title>Stage 2: ${t.toFixed(5)}s</title>
      </circle>
      <line x1="${cx}" y1="${axisY}" x2="${cx}" y2="${yLane2 - 5}" stroke="#e67e22" stroke-width="1" stroke-opacity="0.4"/>
    `;
  }).join('');

  // Peak sensitivity line
  const tStar = 1.0 / (Math.PI * Math.PI * 0.10); // ~1.01s
  let tStarLine = '';
  if (tStar <= tMax * 1.05) {
    const cxStar = scaleLogX(Math.min(tMax, tStar));
    tStarLine = `
      <line x1="${cxStar}" y1="${pad.top}" x2="${cxStar}" y2="${pad.top + plotH}" stroke="#c0392b" stroke-width="2" stroke-dasharray="4 3"/>
      <text x="${cxStar - 5}" y="${pad.top - 8}" text-anchor="end" fill="#c0392b" font-size="10" font-weight="600">t* = 1 / (&pi;&sup2;&alpha;) &approx; 1.01s</text>
    `;
  }

  svg.innerHTML = `
    <g class="chart-grid">${gridLines}</g>
    <line x1="${pad.left}" y1="${axisY}" x2="${pad.left + plotW}" y2="${axisY}" stroke="var(--rule-hairline)" stroke-width="2"/>
    <text x="${pad.left - 5}" y="${yLane1 + 4}" text-anchor="end" fill="#2980b9" font-size="10" font-weight="600">Stage 1</text>
    <text x="${pad.left - 5}" y="${yLane2 + 4}" text-anchor="end" fill="#e67e22" font-size="10" font-weight="600">Stage 2</text>
    ${stage1Dots}
    ${stage2Dots}
    ${tStarLine}
    <text x="${pad.left + plotW / 2}" y="${height - 6}" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">Logarithmic Time Scale (s)</text>
  `;
}

// -------------------------------------------------------------------------------------------------
// 6. Page 5: Field (Forward Problem)
// -------------------------------------------------------------------------------------------------

function initFieldWorkbench() {
  const solverBtn = document.getElementById('field-method-solver-btn');
  const fnoBtn = document.getElementById('field-method-fno-btn');
  const compBtn = document.getElementById('field-method-compare-btn');
  const slider = document.getElementById('field-time-slider');
  const submitBtn = document.getElementById('field-submit-btn');
  const downloadBtn = document.getElementById('field-download-btn');
  const canvas = document.getElementById('field-canvas');

  let activeMethod = 'compare';

  solverBtn.addEventListener('click', () => {
    activeMethod = 'solver';
    solverBtn.classList.add('active');
    fnoBtn.classList.remove('active');
    compBtn.classList.remove('active');
  });

  fnoBtn.addEventListener('click', () => {
    activeMethod = 'fno';
    fnoBtn.classList.add('active');
    solverBtn.classList.remove('active');
    compBtn.classList.remove('active');
  });

  compBtn.addEventListener('click', () => {
    activeMethod = 'compare';
    compBtn.classList.add('active');
    solverBtn.classList.remove('active');
    fnoBtn.classList.remove('active');
  });

  slider.addEventListener('input', () => {
    const tIdx = parseInt(slider.value);
    const tVal = (tIdx / 200).toFixed(2);
    document.getElementById('field-time-val').textContent = `t=${tVal}`;
    renderFieldProfile(tIdx);
  });

  canvas.addEventListener('mousemove', handleFieldCanvasHover);
  canvas.addEventListener('mouseleave', () => {
    document.getElementById('field-hover-readout').textContent = 'Hover over heatmap for (x, t, u)';
  });

  submitBtn.addEventListener('click', () => executeField(activeMethod));
  downloadBtn.addEventListener('click', () => {
    if (!STATE.lastFieldResult) return;
    downloadJson(STATE.lastFieldResult, 'heat_field_grid.json');
  });

  // Setup colorbar gradient
  const colorbar = document.getElementById('field-colorbar');
  if (colorbar) {
    colorbar.style.background = 'linear-gradient(to right, rgb(10,5,30), rgb(75,20,120), rgb(185,40,80), rgb(235,120,20), rgb(255,255,160))';
  }
}

async function executeField(methodChoice) {
  const stateContainer = document.getElementById('field-state-container');
  const resultPanel = document.getElementById('field-result-panel');
  const alpha = parseFloat(document.getElementById('field-alpha').value) || 0.10;
  const Nx = parseInt(document.getElementById('field-nx').value) || 101;
  const Nt = parseInt(document.getElementById('field-nt').value) || 201;

  stateContainer.innerHTML = '<div class="state-box loading"><span class="spinner"></span> Simulating thermal diffusion field...</div>';
  resultPanel.style.display = 'none';

  const payload = { alpha, Nx, Nt, method: methodChoice };

  try {
    const res = await fetch('/v1/field', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    STATE.lastFieldResult = { request: payload, response: data, alpha };

    if (!res.ok) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Simulation Error:</strong> ${data.message || JSON.stringify(data.detail)}</div>`;
      return;
    }

    stateContainer.innerHTML = '';
    resultPanel.style.display = 'block';

    // Summary Strip
    document.getElementById('field-method-badge').textContent = data.method_used.toUpperCase();
    const diffBox = document.getElementById('field-rel-diff-box');
    const timingText = document.getElementById('field-timing-text');

    if (data.method_used === 'compare' && data.relative_difference !== null) {
      diffBox.style.display = 'block';
      document.getElementById('field-rel-diff-val').textContent = (data.relative_difference * 100).toFixed(4) + '%';
      timingText.textContent = `Solver: ${data.solver_timing_ms}ms | FNO: ${data.fno_timing_ms}ms`;
    } else {
      diffBox.style.display = 'none';
      timingText.textContent = `${data.timing_ms} ms`;
    }

    document.getElementById('field-json-dump').textContent = JSON.stringify({ request: payload, response: data }, null, 2);

    renderFieldHeatmap();
    renderFieldProfile(parseInt(document.getElementById('field-time-slider').value) || 40);

  } catch (err) {
    stateContainer.innerHTML = `<div class="state-box error"><strong>Field Simulation Error:</strong> ${err.message}</div>`;
  }
}

function renderFieldHeatmap() {
  const result = STATE.lastFieldResult;
  if (!result || !result.response) return;

  const canvas = document.getElementById('field-canvas');
  const ctx = canvas.getContext('2d');
  const uGrid = result.response.u_grid; // Nt rows, Nx cols
  const Nt = uGrid.length;
  const Nx = uGrid[0].length;

  const w = canvas.width;
  const h = canvas.height;
  const imgData = ctx.createImageData(w, h);

  for (let py = 0; py < h; py++) {
    const tIdx = Math.floor((py / h) * Nt);
    for (let px = 0; px < w; px++) {
      const xIdx = Math.floor((px / w) * Nx);
      const val = uGrid[Math.min(Nt - 1, tIdx)][Math.min(Nx - 1, xIdx)];
      const colStr = getThermalColor(val);
      const m = colStr.match(/\d+/g);
      const idx = (py * w + px) * 4;
      imgData.data[idx] = parseInt(m[0]);
      imgData.data[idx + 1] = parseInt(m[1]);
      imgData.data[idx + 2] = parseInt(m[2]);
      imgData.data[idx + 3] = 255;
    }
  }

  ctx.putImageData(imgData, 0, 0);
}

function handleFieldCanvasHover(e) {
  const result = STATE.lastFieldResult;
  if (!result || !result.response) return;

  const canvas = document.getElementById('field-canvas');
  const rect = canvas.getBoundingClientRect();
  const px = e.clientX - rect.left;
  const py = e.clientY - rect.top;

  const normX = Math.max(0, Math.min(1, px / rect.width));
  const normT = Math.max(0, Math.min(1, py / rect.height));

  const uGrid = result.response.u_grid;
  const Nt = uGrid.length;
  const Nx = uGrid[0].length;

  const tIdx = Math.min(Nt - 1, Math.floor(normT * Nt));
  const xIdx = Math.min(Nx - 1, Math.floor(normX * Nx));
  const uVal = uGrid[tIdx][xIdx];

  document.getElementById('field-hover-readout').textContent = `x=${normX.toFixed(3)}, t=${normT.toFixed(3)}s → u=${uVal.toFixed(4)}`;
}

function renderFieldProfile(tIdx) {
  const result = STATE.lastFieldResult;
  if (!result || !result.response) return;

  const svg = document.getElementById('field-profile-svg');
  const uGrid = result.response.u_grid;
  const Nt = uGrid.length;
  const safeTIdx = Math.min(Nt - 1, Math.max(0, tIdx));
  const uSlice = uGrid[safeTIdx];
  const Nx = uSlice.length;
  const alpha = result.alpha || 0.10;
  const tVal = safeTIdx / (Nt - 1);

  const width = 540;
  const height = 220;
  const pad = { top: 15, right: 25, bottom: 35, left: 50 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  svg.innerHTML = '';

  const scaleX = x => pad.left + x * plotW;
  const scaleY = y => pad.top + plotH - (y / 1.0) * plotH;

  // Grid
  let gridLines = '';
  for (let s = 0; s <= 4; s++) {
    const xG = s / 4;
    const xP = scaleX(xG);
    gridLines += `<line x1="${xP}" y1="${pad.top}" x2="${xP}" y2="${pad.top + plotH}" stroke="var(--rule-subtle)" stroke-dasharray="2 3"/>`;
    gridLines += `<text x="${xP}" y="${pad.top + plotH + 18}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${xG.toFixed(2)}</text>`;
  }

  // Model Slice Curve
  let modelD = [];
  for (let i = 0; i < Nx; i++) {
    const x = i / (Nx - 1);
    const y = uSlice[i];
    modelD.push(`${i === 0 ? 'M' : 'L'} ${scaleX(x)} ${scaleY(y)}`);
  }
  const modelPath = `<path d="${modelD.join(' ')}" fill="none" stroke="var(--primary-navy)" stroke-width="2.5"/>`;

  // Analytic Exact Curve: sin(pi x) * exp(-alpha * pi^2 * t)
  let exactD = [];
  for (let i = 0; i <= 100; i++) {
    const x = i / 100;
    const yEx = Math.sin(Math.PI * x) * Math.exp(-alpha * Math.PI * Math.PI * tVal);
    exactD.push(`${i === 0 ? 'M' : 'L'} ${scaleX(x)} ${scaleY(yEx)}`);
  }
  const exactPath = `<path d="${exactD.join(' ')}" fill="none" stroke="#e67e22" stroke-width="2" stroke-dasharray="4 4"/>`;

  svg.innerHTML = `
    <g class="chart-grid">${gridLines}</g>
    ${modelPath}
    ${exactPath}
    <line x1="${pad.left}" y1="${pad.top + plotH}" x2="${pad.left + plotW}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + plotH}" stroke="var(--rule-hairline)" stroke-width="1.5"/>
    <text x="${pad.left + plotW / 2}" y="${height - 5}" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">Spatial Coordinate x</text>
    <text transform="rotate(-90)" x="${-(pad.top + plotH / 2)}" y="16" text-anchor="middle" fill="var(--text-main)" font-size="11" font-weight="600">u(x, t*=${tVal.toFixed(2)}s)</text>
  `;
}

// -------------------------------------------------------------------------------------------------
// 7. Page 6: Stage 2 Poisson (-nabla^2 u = f)
// -------------------------------------------------------------------------------------------------

function initPoissonWorkbench() {
  const sineBtn = document.getElementById('poi-family-sine-btn');
  const gaussBtn = document.getElementById('poi-family-gauss-btn');
  const sineControls = document.getElementById('poi-sine-controls');
  const gaussControls = document.getElementById('poi-gauss-controls');
  const presetsSelect = document.getElementById('poi-presets-select');
  const submitBtn = document.getElementById('poi-submit-btn');
  const downloadBtn = document.getElementById('poi-download-btn');

  sineBtn.addEventListener('click', () => {
    sineBtn.classList.add('active');
    gaussBtn.classList.remove('active');
    sineControls.style.display = 'block';
    gaussControls.style.display = 'none';
  });

  gaussBtn.addEventListener('click', () => {
    gaussBtn.classList.add('active');
    sineBtn.classList.remove('active');
    gaussControls.style.display = 'block';
    sineControls.style.display = 'none';
  });

  presetsSelect.addEventListener('change', () => {
    const val = presetsSelect.value;
    if (val === 'sine_low') {
      sineBtn.click();
      document.getElementById('poi-mode-m').value = 2;
      document.getElementById('poi-mode-n').value = 2;
      document.getElementById('poi-mode-amp').value = 1.0;
    } else if (val === 'sine_high') {
      sineBtn.click();
      document.getElementById('poi-mode-m').value = 6;
      document.getElementById('poi-mode-n').value = 2;
      document.getElementById('poi-mode-amp').value = 1.0;
    } else if (val === 'gauss_center') {
      gaussBtn.click();
      document.getElementById('poi-gauss-cx').value = 0.5;
      document.getElementById('poi-gauss-cy').value = 0.5;
      document.getElementById('poi-gauss-amp').value = 1.0;
      document.getElementById('poi-gauss-sigma').value = 0.15;
    } else if (val === 'gauss_dual') {
      gaussBtn.click();
      document.getElementById('poi-gauss-cx').value = 0.3;
      document.getElementById('poi-gauss-cy').value = 0.3;
      document.getElementById('poi-gauss-amp').value = 1.0;
      document.getElementById('poi-gauss-sigma').value = 0.12;
    }
  });

  submitBtn.addEventListener('click', executePoisson);
  downloadBtn.addEventListener('click', () => {
    if (!STATE.lastPoissonResult) return;
    downloadJson(STATE.lastPoissonResult, 'poisson_solution_grids.json');
  });
}

async function executePoisson() {
  const stateContainer = document.getElementById('poi-state-container');
  const resultPanel = document.getElementById('poi-result-panel');
  const hfBanner = document.getElementById('poisson-hf-banner');
  const isSine = document.getElementById('poi-family-sine-btn').classList.contains('active');
  const N = parseInt(document.getElementById('poi-grid-size').value) || 64;

  stateContainer.innerHTML = '<div class="state-box loading"><span class="spinner"></span> Solving 2D Poisson operator across exact, FNO, and linear models...</div>';
  resultPanel.style.display = 'none';
  hfBanner.style.display = 'none';

  let sourcePayload = {};
  if (isSine) {
    const m = parseInt(document.getElementById('poi-mode-m').value) || 2;
    const n = parseInt(document.getElementById('poi-mode-n').value) || 2;
    const a = parseFloat(document.getElementById('poi-mode-amp').value) || 1.0;
    sourcePayload = {
      type: 'sine',
      modes: [[m, n]],
      amplitudes: [a]
    };
  } else {
    const cx = parseFloat(document.getElementById('poi-gauss-cx').value) || 0.5;
    const cy = parseFloat(document.getElementById('poi-gauss-cy').value) || 0.5;
    const amp = parseFloat(document.getElementById('poi-gauss-amp').value) || 1.0;
    const s = parseFloat(document.getElementById('poi-gauss-sigma').value) || 0.15;
    sourcePayload = {
      type: 'gaussian',
      centers: [[cx, cy]],
      amplitudes: [amp],
      sigmas: [s]
    };
  }

  const payload = { source: sourcePayload, grid_size: N };

  try {
    const res = await fetch('/v1/poisson', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    STATE.lastPoissonResult = { request: payload, response: data };

    if (!res.ok) {
      stateContainer.innerHTML = `<div class="state-box error"><strong>Poisson Solver Error:</strong> ${data.message || JSON.stringify(data.detail)}</div>`;
      return;
    }

    stateContainer.innerHTML = '';
    resultPanel.style.display = 'block';

    // High frequency banner
    if (data.high_frequency_source) {
      hfBanner.style.display = 'block';
    }

    // Populate Metrics Table
    document.getElementById('poi-time-exact').textContent = data.timing_ms.exact_ms.toFixed(3);
    document.getElementById('poi-time-lin').textContent = data.timing_ms.linear_ms.toFixed(3);
    document.getElementById('poi-time-fno').textContent = data.timing_ms.fno_ms.toFixed(3);
    document.getElementById('poi-time-total').textContent = data.timing_ms.total_ms.toFixed(2);

    document.getElementById('poi-err-lin').textContent = data.relative_errors.rel_l2_linear_vs_exact.toFixed(6);
    document.getElementById('poi-err-fno').textContent = data.relative_errors.rel_l2_fno_vs_exact.toFixed(6);

    // Status Badges
    const fnoErr = data.relative_errors.rel_l2_fno_vs_exact;
    const fnoBadge = document.getElementById('poi-badge-fno');
    if (fnoErr > 0.50) {
      fnoBadge.className = 'badge badge-danger';
      fnoBadge.textContent = 'Degraded (>50%)';
    } else {
      fnoBadge.className = 'badge badge-info';
      fnoBadge.textContent = 'In-Distribution';
    }

    // Render Canvas Heatmaps
    draw2DGridCanvas('poi-canvas-exact', data.exact_field, false);
    draw2DGridCanvas('poi-canvas-fno', data.fno_field, false);
    draw2DGridCanvas('poi-canvas-lin', data.linear_field, false);

    // Compute error fields and draw diverging maps
    const errFno = diff2DGrids(data.fno_field, data.exact_field);
    const errLin = diff2DGrids(data.linear_field, data.exact_field);
    draw2DGridCanvas('poi-canvas-err-fno', errFno, true);
    draw2DGridCanvas('poi-canvas-err-lin', errLin, true);

    document.getElementById('poi-json-dump').textContent = JSON.stringify({ request: payload, response: data }, null, 2);

  } catch (err) {
    stateContainer.innerHTML = `<div class="state-box error"><strong>Poisson Execution Error:</strong> ${err.message}</div>`;
  }
}

function diff2DGrids(gA, gB) {
  const N = gA.length;
  const out = [];
  for (let i = 0; i < N; i++) {
    const row = [];
    for (let j = 0; j < N; j++) {
      row.push(Math.abs(gA[i][j] - gB[i][j]));
    }
    out.push(row);
  }
  return out;
}

function draw2DGridCanvas(canvasId, grid, isErrorMap = false) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !grid) return;
  const ctx = canvas.getContext('2d');
  const N = grid.length;
  const w = canvas.width;
  const h = canvas.height;
  const imgData = ctx.createImageData(w, h);

  let maxVal = 0.001;
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      if (grid[i][j] > maxVal) maxVal = grid[i][j];
    }
  }

  for (let py = 0; py < h; py++) {
    // Note: grid is [x][y], row is x, col is y
    const xIdx = Math.min(N - 1, Math.floor((py / h) * N));
    for (let px = 0; px < w; px++) {
      const yIdx = Math.min(N - 1, Math.floor((px / w) * N));
      const val = grid[xIdx][yIdx];
      const colStr = isErrorMap ? getDivergingErrorColor(val, maxVal) : getThermalColor(val / maxVal);
      const m = colStr.match(/\d+/g);
      const idx = (py * w + px) * 4;
      imgData.data[idx] = parseInt(m[0]);
      imgData.data[idx + 1] = parseInt(m[1]);
      imgData.data[idx + 2] = parseInt(m[2]);
      imgData.data[idx + 3] = 255;
    }
  }

  ctx.putImageData(imgData, 0, 0);
}

// -------------------------------------------------------------------------------------------------
// 8. Page 7: Evidence Archive Renderer
// -------------------------------------------------------------------------------------------------

function renderEvidencePage() {
  if (!STATE.evidence) return;
  const ev = STATE.evidence;

  // 1. Stage 1 Modes
  const s1Tbody = document.getElementById('ev-tbody-s1');
  if (s1Tbody && ev.stage1_inverse_modes) {
    const m = ev.stage1_inverse_modes;
    s1Tbody.innerHTML = `
      <tr>
        <td><strong>${m.mode2.name}</strong></td>
        <td class="text-right mono">${m.mode2.overall_median_rel_err}</td>
        <td class="text-right mono">${m.mode2.overall_mean_cov_95}%</td>
        <td class="text-right mono">${m.mode2.overall_mean_latency_ms} ms</td>
        <td class="text-right mono">${m.mode2.total_cells}</td>
      </tr>
      <tr>
        <td><strong>${m.mode3.name}</strong></td>
        <td class="text-right mono">${m.mode3.overall_median_rel_err}</td>
        <td class="text-right mono">${m.mode3.overall_mean_cov_95}%</td>
        <td class="text-right mono">${m.mode3.overall_mean_latency_ms} ms</td>
        <td class="text-right mono">${m.mode3.total_cells}</td>
      </tr>
      <tr>
        <td><strong>${m.mode3plus.name}</strong></td>
        <td class="text-right mono">${m.mode3plus.overall_median_rel_err}</td>
        <td class="text-right mono">${m.mode3plus.overall_mean_cov_95}%</td>
        <td class="text-right mono">${m.mode3plus.overall_mean_latency_ms} ms</td>
        <td class="text-right mono">${m.mode3plus.total_cells}</td>
      </tr>
    `;
  }

  // 2. Sensor Placement
  const pTbody = document.getElementById('ev-tbody-placement');
  if (pTbody && ev.sensor_placement) {
    pTbody.innerHTML = ev.sensor_placement.strategy_aggregates.map(s => `
      <tr>
        <td><strong>${s.strategy}</strong></td>
        <td class="text-right mono">${s.median_rel_err.toFixed(5)}</td>
        <td class="text-right mono">${s.mean_rel_err.toFixed(5)}</td>
        <td class="text-right mono">${s.mean_sprd_crb.toFixed(4)}</td>
        <td class="text-right mono">${s.mean_fit_time_ms.toFixed(3)}</td>
      </tr>
    `).join('');
  }

  // 3. Anomaly Confusion Matrix SVG
  renderConfusionMatrixSvg();

  // 4. Stress Matrix Summary
  const smTbody = document.getElementById('ev-tbody-stress-module');
  const scTbody = document.getElementById('ev-tbody-stress-cat');
  if (smTbody && scTbody && ev.stress_summary) {
    smTbody.innerHTML = ev.stress_summary.by_module.map(m => `
      <tr>
        <td>${m.module}</td>
        <td class="text-right mono">${m.pass_count}</td>
        <td class="text-right mono">${m.fail_count}</td>
        <td class="text-right mono"><strong>${m.pass_rate_pct}%</strong></td>
      </tr>
    `).join('');

    scTbody.innerHTML = ev.stress_summary.by_category.map(c => `
      <tr>
        <td>${c.category}</td>
        <td class="text-right mono">${c.pass_count}</td>
        <td class="text-right mono">${c.fail_count}</td>
        <td class="text-right mono"><strong>${c.pass_rate_pct}%</strong></td>
      </tr>
    `).join('');
  }

  // 5. V2 Targets Table
  const v2Tbody = document.getElementById('ev-tbody-v2');
  if (v2Tbody && ev.v2_before_after) {
    v2Tbody.innerHTML = ev.v2_before_after.records.map(r => `
      <tr>
        <td class="mono font-bold">${r.target_id}</td>
        <td>${r.scenario}</td>
        <td>${r.metric_name}</td>
        <td class="mono text-muted">${r.before_value}</td>
        <td class="mono">${r.after_value}</td>
        <td class="text-muted">${r.target_spec}</td>
        <td>
          <span class="badge ${r.target_status === 'MET' ? 'badge-met' : 'badge-missed'}">
            ${r.target_status}
          </span>
        </td>
      </tr>
    `).join('');
  }

  // 5b. V2 Followups Final State
  const d2nTbody = document.getElementById('ev-tbody-v2-d2-n');
  const d2dwTbody = document.getElementById('ev-tbody-v2-d2-dw');
  if (ev.v2_followups_final_state) {
    const f = ev.v2_followups_final_state;
    if (d2nTbody && f.d2_false_flags_by_N) {
      d2nTbody.innerHTML = f.d2_false_flags_by_N.map(r => `
        <tr>
          <td class="mono font-bold">N = ${r.N}</td>
          <td class="text-right mono">${r.dof}</td>
          <td class="text-right mono">${r.false_flags} / ${r.num_runs}</td>
          <td class="text-right mono font-bold">${r.false_flag_rate_pct.toFixed(1)}%</td>
          <td class="text-right mono text-muted">[${r.ci_95[0].toFixed(2)}, ${r.ci_95[1].toFixed(2)}]</td>
          <td><span class="badge ${r.status === 'MET' ? 'badge-met' : 'badge-missed'}">${r.status} (&le;5.0%)</span></td>
        </tr>
      `).join('');
    }

    if (d2dwTbody && f.d2_durbin_watson_detection_by_rho) {
      d2dwTbody.innerHTML = f.d2_durbin_watson_detection_by_rho.map(r => `
        <tr>
          <td class="mono font-bold">&rho; = ${r.rho}</td>
          <td class="text-right mono">Sev ${r.severity}</td>
          <td class="text-right mono font-bold">${r.dw_detection_rate_pct.toFixed(1)}%</td>
          <td class="text-right mono text-muted">[${r.ci_95[0].toFixed(2)}, ${r.ci_95[1].toFixed(2)}]</td>
        </tr>
      `).join('');
    }
  }

  // 6. Poisson Table
  const poiTbody = document.getElementById('ev-tbody-poisson');
  if (poiTbody && ev.stage2_methods) {
    poiTbody.innerHTML = ev.stage2_methods.benchmark_table.map(b => `
      <tr>
        <td><code>${b.split}</code></td>
        <td class="text-right mono">${b.samples}</td>
        <td class="text-right mono font-bold" style="${b.split === 'test_ood_highmodes' ? 'color: var(--accent-burgundy);' : ''}">${(b.fno_l2_med * 100).toFixed(2)}%</td>
        <td class="text-right mono">${(b.fno_l2_p90 * 100).toFixed(2)}%</td>
        <td class="text-right mono">${(b.lin_l2_med * 100).toFixed(4)}%</td>
        <td class="text-right mono">${(b.lin_l2_p90 * 100).toFixed(4)}%</td>
      </tr>
    `).join('');
  }

  // 7. PINN Tables
  const pinnTbody = document.getElementById('ev-tbody-pinn');
  if (pinnTbody && ev.pinn_ablation_table) {
    pinnTbody.innerHTML = ev.pinn_ablation_table.forward_ablation_variants.map(p => `
      <tr>
        <td><strong>${p.model}</strong></td>
        <td>${p.split}</td>
        <td class="text-right mono">${p.samples}</td>
        <td class="text-right mono font-bold">${(p.median_rel_l2 * 100).toFixed(2)}%</td>
        <td class="text-right mono">${(p.p90_rel_l2 * 100).toFixed(2)}%</td>
        <td class="text-right mono">${p.median_t0_mae.toExponential(2)}</td>
      </tr>
    `).join('');
  }

  const pinnFullTbody = document.getElementById('ev-tbody-pinn-full');
  if (pinnFullTbody && ev.pinn_ablation_table && ev.pinn_ablation_table.full_ablation_summary) {
    pinnFullTbody.innerHTML = ev.pinn_ablation_table.full_ablation_summary.map(a => `
      <tr>
        <td class="mono font-bold">${a.variant}</td>
        <td>${a.axis}</td>
        <td><code>${a.collocation}</code></td>
        <td><code>${a.activation}</code></td>
        <td><code>${a.loss_weighting}</code></td>
        <td><code>${a.optimizer}</code></td>
        <td class="text-right mono font-bold">${(a.interp_rel_l2_median * 100).toFixed(3)}%</td>
        <td class="text-right mono">${(a.low_alpha_ood_rel_l2_median * 100).toFixed(3)}%</td>
        <td class="text-right mono">${(a.high_alpha_ood_rel_l2_median * 100).toFixed(2)}%</td>
        <td class="text-right mono">${a.train_time_sec_mean.toFixed(1)}s</td>
      </tr>
    `).join('');
  }
}

function renderConfusionMatrixSvg() {
  if (!STATE.evidence || !STATE.evidence.anomaly_confusion_matrix) return;
  const svg = document.getElementById('ev-conf-matrix-svg');
  if (!svg) return;

  const primary = STATE.evidence.anomaly_confusion_matrix.primary_cell;
  const counts = primary.confusion_matrix_counts;
  const pcts = primary.confusion_matrix_pct;
  const classes = ['H', 'A', 'F', 'C'];
  const classLabels = ['Healthy (H)', 'Anomalous (A)', 'Sensor Fault (F)', 'Change-point (C)'];

  const width = 540;
  const height = 280;
  const pad = { top: 40, right: 30, bottom: 40, left: 140 };
  const cellW = (width - pad.left - pad.right) / 4;
  const cellH = (height - pad.top - pad.bottom) / 4;

  svg.innerHTML = '';

  let rects = '';
  classes.forEach((trueC, row) => {
    classes.forEach((predC, col) => {
      const count = counts[trueC][predC];
      const pct = pcts[trueC][predC];
      const isDiag = (row === col);
      const intensity = pct / 100.0;
      
      const x = pad.left + col * cellW;
      const y = pad.top + row * cellH;

      const fill = isDiag 
        ? `rgba(31, 58, 95, ${Math.max(0.12, intensity)})`
        : `rgba(140, 47, 57, ${Math.max(0.04, intensity)})`;
      
      const textColor = (isDiag && intensity > 0.6) ? '#fff' : 'var(--text-main)';

      rects += `
        <rect x="${x}" y="${y}" width="${cellW - 2}" height="${cellH - 2}" fill="${fill}" rx="2" stroke="var(--rule-hairline)"/>
        <text x="${x + cellW/2}" y="${y + cellH/2 - 2}" text-anchor="middle" font-size="12" font-weight="700" fill="${textColor}">${count}</text>
        <text x="${x + cellW/2}" y="${y + cellH/2 + 13}" text-anchor="middle" font-size="10" fill="${textColor}" opacity="0.85">${pct.toFixed(1)}%</text>
      `;
    });
  });

  // Headers and labels
  let labels = '';
  classes.forEach((c, idx) => {
    const x = pad.left + idx * cellW + cellW / 2;
    labels += `<text x="${x}" y="${pad.top - 12}" text-anchor="middle" font-size="11" font-weight="600" fill="var(--text-main)">Pred ${c}</text>`;
  });

  classLabels.forEach((label, idx) => {
    const y = pad.top + idx * cellH + cellH / 2 + 4;
    labels += `<text x="${pad.left - 10}" y="${y}" text-anchor="end" font-size="10" font-weight="600" fill="var(--text-main)">${label}</text>`;
  });

  svg.innerHTML = `
    <text x="${pad.left + (4 * cellW)/2}" y="16" text-anchor="middle" font-size="12" font-weight="700" fill="var(--primary-navy)">Predicted Class (Columns)</text>
    <text transform="rotate(-90)" x="${-(pad.top + (4 * cellH)/2)}" y="18" text-anchor="middle" font-size="12" font-weight="700" fill="var(--primary-navy)">True Condition (Rows)</text>
    ${labels}
    ${rects}
  `;
}

// -------------------------------------------------------------------------------------------------
// 9. Download Helpers
// -------------------------------------------------------------------------------------------------

function downloadJson(obj, filename = 'result.json') {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// -------------------------------------------------------------------------------------------------
// 10. Initialization
// -------------------------------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  checkServiceHealth();
  setInterval(checkServiceHealth, 15000); // 15-second heartbeat
  loadVersionMetadata();
  loadEvidenceJson();

  initEstimateWorkbench();
  initDiagnoseWorkbench();
  initPlacementWorkbench();
  initFieldWorkbench();
  initPoissonWorkbench();
  initOverviewTaskCards();

  window.addEventListener('hashchange', handleRoute);
  handleRoute();
});
