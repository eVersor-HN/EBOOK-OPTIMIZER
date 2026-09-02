/* EBOOK-OPTIMIZER - interface logic.
   No framework: the server returns JSON, this renders it. */

'use strict';

const $ = (id) => document.getElementById(id);

// Bumped whenever the page needs a server feature that older builds do
// not have. The server serves these files straight from disk, so an
// already running process can hand out a new page while its own Python
// is still the old one - which looks exactly like a dead button.
const NEEDS_VERSION = '0.4.1';

const STATE = {
  cwd: '',
  selection: [],      // {path, name, size}
  status: null,
  target: 'identical',   // active quality target
  jobId: null,
  poll: null,
  rendered: 0,
  lastOutDir: '',
};

/* ------------------------------------------------------------- Helpers */

function human(n) {
  if (n === null || n === undefined) return '';
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = Number(n);
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + ' ' + u[i];
}

function notify(msg, stop) {
  const el = $('staleWarn');
  el.hidden = false;
  el.className = stop ? 'banner banner-stop' : 'banner';
  el.innerHTML = '<strong>' + (stop ? 'Problem:' : 'Note:')
    + '</strong><span>' + esc(msg) + '</span>';
  el.scrollIntoView({ block: 'nearest' });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

async function api(path, body) {
  const opt = body === undefined
    ? {}
    : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
  return data;
}

/* -------------------------------------------------------------- Status */

async function loadStatus() {
  const s = await api('/api/status');
  STATE.status = s;

  $('sysinfo').innerHTML = [
    '<span class="chip ' + (s.calibre ? 'good' : 'bad') + '">Calibre <b>'
      + (s.calibre ? 'ready' : 'missing') + '</b></span>',
    '<span class="chip">Images <b>' + esc(s.backend) + '</b></span>',
    '<span class="chip">Cores <b>' + s.cpus + '</b></span>',
  ].join('');

  $('calibreWarn').hidden = s.calibre;

  // Devices, grouped by brand
  const prof = $('profile');
  prof.innerHTML = s.deviceGroups.map((g) =>
    '<optgroup label="' + esc(g.brand) + '">'
    + g.devices.map((d) =>
      '<option value="' + d.key + '"'
      + (d.key === s.defaultProfile ? ' selected' : '') + '>'
      + esc(d.name) + ' - ' + d.width + '×' + d.height
      + (d.gray ? '' : ' - colour') + '</option>').join('')
    + '</optgroup>').join('');
  showProfileHint();

  // Quality targets
  $('presets').innerHTML = s.targets.map((t) =>
    '<button type="button" class="preset" data-key="' + t.key
    + '" data-budget="' + t.budget + '" data-quantize="' + t.quantize + '">'
    + '<span class="pname">' + esc(t.name)
    + ' <span class="pq">max ' + t.budget.toFixed(2) + ' %</span></span>'
    + '<span class="psum">' + esc(t.summary) + '</span>'
    + '<span class="pmeas">' + esc(t.measured) + '</span>'
    + '</button>').join('');
  Array.prototype.forEach.call(
    document.querySelectorAll('.preset'),
    (b) => { b.onclick = () => chooseTarget(b.dataset.key); });
  chooseTarget(s.defaultTarget);

  // Output formats
  const native = new Set(s.nativeFormats);
  $('format').innerHTML = '<option value="">Keep the original format</option>'
    + s.formats.map((f) =>
      '<option value="' + f + '">' + f.toUpperCase()
      + (native.has(f) ? '' : ' (needs Calibre)') + '</option>').join('');

  $('jobs').value = s.cpus;

  if (s.version !== NEEDS_VERSION) {
    notify('The server is running version ' + (s.version || 'unknown')
      + ' while this page expects ' + NEEDS_VERSION
      + '. Close the server window and start it again - '
      + 'otherwise some buttons will do nothing.', true);
  }
}

function showProfileHint() {
  const d = (STATE.status.deviceGroups
    .reduce((a, g) => a.concat(g.devices), []))
    .find((x) => x.key === $('profile').value);
  if (!d) return;
  $('profileHint').textContent = d.gray
    ? 'Images are scaled to ' + d.width + '×' + d.height
      + ' and converted to greyscale, because the panel shows nothing else.'
    : 'Images are scaled to ' + d.width + '×' + d.height
      + ' and keep their colour.';
}

function chooseTarget(key) {
  STATE.target = key;
  Array.prototype.forEach.call(document.querySelectorAll('.preset'), (b) => {
    const on = b.dataset.key === key;
    b.classList.toggle('on', on);
    if (on) $('noQuantize').checked = b.dataset.quantize !== 'true';
  });
}

/* ------------------------------------------------------------- Browser */

async function browse(path) {
  let d;
  try {
    d = await api('/api/browse', { path: path || '' });
  } catch (e) {
    $('dirList').innerHTML =
      '<li><span class="ic">!</span><span class="nm">' + esc(e.message)
      + '</span></li>';
    return;
  }
  STATE.cwd = d.path;
  $('pathInput').value = d.path;

  const c = $('crumbs');
  c.innerHTML = '';
  const root = document.createElement('button');
  root.textContent = d.rootLabel || 'Top';
  root.onclick = () => browse('');
  c.appendChild(root);
  if (d.path) {
    const parts = d.path.split(/[\\/]/).filter(Boolean);
    let acc = '';
    parts.forEach((p, i) => {
      acc += p + (d.sep || '\\');
      const here = acc;
      c.appendChild(document.createTextNode(' / '));
      const b = document.createElement('button');
      b.textContent = p;
      b.onclick = () => browse(here);
      c.appendChild(b);
    });
  }

  const ul = $('dirList');
  ul.innerHTML = '';
  if (d.parent !== null && d.parent !== undefined) {
    ul.appendChild(row('dir', '^', '..', '', () => browse(d.parent)));
  }
  d.dirs.forEach((x) => {
    ul.appendChild(row('dir', '>', x.name, '', () => browse(x.path)));
  });
  d.files.forEach((x) => {
    const li = row('file', '-', x.name, human(x.size),
      () => toggleFile(x, li));
    if (STATE.selection.some((s) => s.path === x.path)) {
      li.classList.add('picked');
    }
    ul.appendChild(li);
  });
  if (!d.dirs.length && !d.files.length) {
    ul.innerHTML = '<li><span class="ic">-</span>'
      + '<span class="nm dim">Nothing usable in this folder</span></li>';
  }
}

function row(kind, icon, name, size, onclick) {
  const li = document.createElement('li');
  li.className = kind;
  li.innerHTML = '<span class="ic">' + icon + '</span>'
    + '<span class="nm">' + esc(name) + '</span>'
    + (size ? '<span class="sz">' + size + '</span>' : '');
  li.onclick = onclick;
  return li;
}

function toggleFile(x, li) {
  const i = STATE.selection.findIndex((s) => s.path === x.path);
  if (i >= 0) {
    STATE.selection.splice(i, 1);
    li.classList.remove('picked');
  } else {
    STATE.selection.push(x);
    li.classList.add('picked');
  }
  renderSelection();
}

/* ----------------------------------------------------------- Selection */

async function useFolder() {
  if (!STATE.cwd) return;
  $('runInfo').textContent = 'Scanning folder...';
  try {
    const d = await api('/api/scan', {
      paths: [STATE.cwd], recursive: $('recursive').checked,
    });
    STATE.selection = d.files;
    renderSelection();
  } catch (e) {
    $('runInfo').textContent = 'Error: ' + e.message;
  }
}

function renderSelection() {
  const n = STATE.selection.length;
  const total = STATE.selection.reduce((a, b) => a + (b.size || 0), 0);
  $('selBox').hidden = n === 0;
  $('selCount').textContent = n === 1 ? '1 file' : n + ' files';
  $('selSize').textContent = human(total);
  $('selList').innerHTML = STATE.selection.slice(0, 400).map((f) =>
    '<li><span>' + esc(f.name) + '</span><span class="sz">'
    + human(f.size) + '</span></li>').join('')
    + (n > 400 ? '<li><span class="dim">and ' + (n - 400)
      + ' more</span></li>' : '');
  $('runBtn').disabled = n === 0;
  $('runInfo').textContent = n === 0
    ? 'Pick files or a folder first'
    : (n === 1 ? '1 file' : n + ' files') + ' - ' + human(total) + ' ready';
}

/* ----------------------------------------------------------------- Run */

function currentBudget() {
  const b = document.querySelector('.preset.on');
  return b ? Number(b.dataset.budget) : 0.10;
}

function collectOpts() {
  return {
    profile: $('profile').value,
    format: $('format').value,
    outDir: $('outDir').value.trim(),
    quality: $('fixedQuality').checked ? Number($('quality').value) : null,
    targetError: $('fixedQuality').checked ? null : currentBudget(),
    pngMode: $('pngMode').value,
    jobs: Number($('jobs').value),
    keepColor: $('keepColor').checked,
    keepFonts: $('keepFonts').checked,
    noQuantize: $('noQuantize').checked,
    manga: $('manga').checked,
    noProgressive: $('noProgressive').checked,
  };
}

async function run() {
  const opts = collectOpts();
  if (opts.format && !STATE.status.nativeFormats.includes(opts.format)
      && !STATE.status.calibre) {
    alert(opts.format.toUpperCase() + ' needs Calibre, which was not found.');
    return;
  }
  STATE.rendered = 0;
  $('runBtn').disabled = true;
  $('cancelBtn').hidden = false;
  $('resultPanel').hidden = false;
  $('results').innerHTML = '';
  $('totals').hidden = true;
  $('openOut').hidden = true;
  $('prog').style.width = '0%';
  $('statusLine').textContent = 'Starting...';

  try {
    const d = await api('/api/run', { files: STATE.selection, opts });
    STATE.jobId = d.id;
    STATE.poll = setInterval(pollJob, 450);
  } catch (e) {
    $('statusLine').textContent = 'Error: ' + e.message;
    $('runBtn').disabled = false;
    $('cancelBtn').hidden = true;
  }
}

async function pollJob() {
  if (!STATE.jobId) return;
  let j;
  try {
    j = await api('/api/job/' + STATE.jobId);
  } catch (e) {
    return;
  }

  const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
  $('prog').style.width = pct + '%';
  $('statusLine').textContent = j.state === 'running'
    ? j.done + ' of ' + j.total + ' - ' + (j.current || '')
    : j.state + ' - ' + j.done + ' of ' + j.total;

  renderResults(j.results);

  if (j.state !== 'running') {
    clearInterval(STATE.poll);
    STATE.poll = null;
    $('runBtn').disabled = false;
    $('cancelBtn').hidden = true;
    showTotals(j);
  }
}

function renderResults(list) {
  const ul = $('results');
  for (let i = STATE.rendered; i < list.length; i += 1) {
    const r = list[i];
    const li = document.createElement('li');
    if (r.error) {
      li.className = 'err';
      li.innerHTML = '<span class="nm">' + esc(r.name) + '</span>'
        + '<span class="dt">' + esc(r.error) + '</span>';
    } else {
      const win = !r.skipped && r.pct > 0.05;
      li.innerHTML = '<span class="nm">' + esc(r.name) + '</span>'
        + '<span class="sz">' + human(r.old) + ' → ' + human(r.new)
        + '</span>'
        + '<span class="pc ' + (win ? 'win' : 'none') + '">'
        + (win ? '-' + r.pct.toFixed(1) + '%' : 'unchanged') + '</span>'
        + (r.detail ? '<span class="dt">' + esc(r.detail) + '</span>' : '');
      if (r.out) STATE.lastOutDir = r.out.replace(/[\\/][^\\/]+$/, '');
    }
    ul.appendChild(li);
  }
  STATE.rendered = list.length;
}

function showTotals(j) {
  if (!j.totalOld) return;
  const saved = j.totalOld - j.totalNew;
  const pct = (saved / j.totalOld) * 100;
  $('totals').hidden = false;
  $('totals').innerHTML =
    '<div><span class="k">Before</span><span class="v">'
      + human(j.totalOld) + '</span></div>'
    + '<div><span class="k">After</span><span class="v">'
      + human(j.totalNew) + '</span></div>'
    + '<div><span class="k">Saved</span><span class="v hi">'
      + human(saved) + '</span></div>'
    + '<div><span class="k">Reduction</span><span class="v hi">'
      + pct.toFixed(1) + ' %</span></div>';
  if (STATE.lastOutDir) $('openOut').hidden = false;
}

/* ------------------------------------------------------------- Wiring */

async function pickWith(mode) {
  const btn = mode === 'files' ? $('pickFiles') : $('pickFolder');
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Waiting for the dialog...';
  try {
    const d = await api('/api/pick', { mode, initial: STATE.cwd });
    if (!d.paths.length) return;                 // cancelled
    if (mode === 'files') {
      const known = new Set(STATE.selection.map((f) => f.path));
      const found = await api('/api/scan', { paths: d.paths,
                                             recursive: false });
      found.files.forEach((f) => {
        if (!known.has(f.path)) STATE.selection.push(f);
      });
      renderSelection();
      if (d.paths.length) {
        await browse(d.paths[0].replace(/[\\/][^\\/]+$/, ''));
      }
    } else {
      await browse(d.paths[0]);
      await useFolder();
    }
  } catch (e) {
    notify('The file dialog could not be opened: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

$('pickFolder').onclick = () => pickWith('dir');
$('pickFiles').onclick = () => pickWith('files');
$('goPath').onclick = () => browse($('pathInput').value.trim());
$('pathInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') browse($('pathInput').value.trim());
});
$('useFolder').onclick = useFolder;
$('clearSel').onclick = () => {
  STATE.selection = [];
  renderSelection();
  Array.prototype.forEach.call(
    document.querySelectorAll('.filelist li.picked'),
    (li) => li.classList.remove('picked'));
};
$('profile').onchange = showProfileHint;
$('quality').oninput = (e) => { $('qOut').value = e.target.value; };
$('fixedQuality').onchange = (e) => {
  $('qualityRow').hidden = !e.target.checked;
};
$('runBtn').onclick = run;
$('cancelBtn').onclick = () => api('/api/cancel', { id: STATE.jobId });
$('openOut').onclick = async () => {
  try {
    await api('/api/reveal', { path: STATE.lastOutDir });
  } catch (e) {
    $('statusLine').textContent = e.message;
  }
};

loadStatus()
  .then(() => browse(''))
  .catch((e) => {
    document.body.insertAdjacentHTML('afterbegin',
      '<div class="banner"><strong>Error:</strong> ' + esc(e.message)
      + '</div>');
  });
