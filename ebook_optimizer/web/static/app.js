/* Ebook Optimizer - Oberflaechenlogik.
   Kein Framework: der Server liefert JSON, hier wird es angezeigt. */

'use strict';

const $ = (id) => document.getElementById(id);

let STATE = {
  cwd: '',
  selection: [],      // {path,name,size}
  status: null,
  jobId: null,
  poll: null,
  lastOutDir: '',
};

/* ------------------------------------------------------------- Helfer */

function human(n) {
  if (n === null || n === undefined) return '';
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0, v = Number(n);
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + ' ' + u[i];
}

async function api(path, body) {
  const opt = body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
  return data;
}

/* ------------------------------------------------------------- Status */

async function loadStatus() {
  const s = await api('/api/status');
  STATE.status = s;

  $('sysinfo').innerHTML = [
    `<span class="chip ${s.calibre ? 'good' : 'bad'}">CALIBRE <b>${
      s.calibre ? 'bereit' : 'fehlt'}</b></span>`,
    `<span class="chip">BILD <b>${s.backend}</b></span>`,
    `<span class="chip">KERNE <b>${s.cpus}</b></span>`,
  ].join('');

  $('calibreWarn').hidden = s.calibre;

  const prof = $('profile');
  prof.innerHTML = s.profiles.map((p) =>
    `<option value="${p.key}"${p.key === s.defaultProfile ? ' selected' : ''}>${
      p.name} · ${p.size}${p.gray ? '' : ' · Farbe'}</option>`).join('');

  const fmt = $('format');
  const native = new Set(s.nativeFormats);
  fmt.innerHTML = '<option value="">Format beibehalten</option>' +
    s.formats.map((f) => {
      const needs = native.has(f) ? '' : ' (Calibre)';
      const sel = f === 'epub' ? '' : '';
      return `<option value="${f}"${sel}>${f.toUpperCase()}${needs}</option>`;
    }).join('');

  $('jobs').value = s.cpus;
}

/* ------------------------------------------------------- Ordnerbrowser */

async function browse(path) {
  let d;
  try {
    d = await api('/api/browse', { path: path || '' });
  } catch (e) {
    $('dirList').innerHTML =
      `<li class="file"><span class="ic">!</span><span>${e.message}</span></li>`;
    return;
  }
  STATE.cwd = d.path;
  $('pathInput').value = d.path;

  // Brotkrumen
  const c = $('crumbs');
  c.innerHTML = '';
  const root = document.createElement('button');
  root.textContent = 'Laufwerke';
  root.onclick = () => browse('');
  c.appendChild(root);
  if (d.path) {
    const parts = d.path.split(/[\\/]/).filter(Boolean);
    let acc = '';
    parts.forEach((p, i) => {
      acc += (i === 0 ? p + '\\' : p + '\\');
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
    ul.appendChild(row('dir', '↰', '..', '', () => browse(d.parent)));
  }
  d.dirs.forEach((x) => {
    ul.appendChild(row('dir', '▸', x.name, '', () => browse(x.path)));
  });
  d.files.forEach((x) => {
    const li = row('file', '·', x.name, human(x.size), () => toggleFile(x, li));
    if (STATE.selection.some((s) => s.path === x.path)) li.classList.add('picked');
    ul.appendChild(li);
  });
  if (!d.dirs.length && !d.files.length) {
    ul.innerHTML = '<li class="file"><span class="ic">·</span>' +
      '<span class="dim">Nichts Verwertbares in diesem Ordner</span></li>';
  }
}

function row(kind, icon, name, size, onclick) {
  const li = document.createElement('li');
  li.className = kind;
  li.innerHTML = `<span class="ic">${icon}</span><span>${escapeHtml(name)}</span>` +
    (size ? `<span class="sz">${size}</span>` : '');
  li.onclick = onclick;
  return li;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

function toggleFile(x, li) {
  const i = STATE.selection.findIndex((s) => s.path === x.path);
  if (i >= 0) { STATE.selection.splice(i, 1); li.classList.remove('picked'); }
  else { STATE.selection.push(x); li.classList.add('picked'); }
  renderSelection();
}

/* ----------------------------------------------------------- Auswahl */

async function useFolder() {
  if (!STATE.cwd) return;
  $('runInfo').textContent = 'Durchsuche Ordner …';
  try {
    const d = await api('/api/scan', {
      paths: [STATE.cwd], recursive: $('recursive').checked });
    STATE.selection = d.files;
    renderSelection();
  } catch (e) {
    $('runInfo').textContent = 'Fehler: ' + e.message;
  }
}

function renderSelection() {
  const n = STATE.selection.length;
  const total = STATE.selection.reduce((a, b) => a + (b.size || 0), 0);
  $('selBox').hidden = n === 0;
  $('selCount').textContent = n === 1 ? '1 Datei' : n + ' Dateien';
  $('selSize').textContent = human(total);
  $('selList').innerHTML = STATE.selection.slice(0, 400).map((f) =>
    `<li><span>${escapeHtml(f.name)}</span><span class="sz">${
      human(f.size)}</span></li>`).join('') +
    (n > 400 ? `<li><span class="dim">… und ${n - 400} weitere</span></li>` : '');
  $('runBtn').disabled = n === 0;
  $('runInfo').textContent = n === 0
    ? 'Zuerst Dateien auswählen'
    : `${n === 1 ? '1 Datei' : n + ' Dateien'} · ${human(total)} bereit`;
}

/* -------------------------------------------------------------- Lauf */

function collectOpts() {
  return {
    profile: $('profile').value,
    format: $('format').value,
    outDir: $('outDir').value.trim(),
    quality: Number($('quality').value),
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
  const fmt = opts.format;
  if (fmt && !STATE.status.nativeFormats.includes(fmt) && !STATE.status.calibre) {
    alert('Für ' + fmt.toUpperCase() + ' wird Calibre benötigt.');
    return;
  }
  $('runBtn').disabled = true;
  $('cancelBtn').hidden = false;
  $('resultPanel').hidden = false;
  $('results').innerHTML = '';
  $('totals').hidden = true;
  $('openOut').hidden = true;
  $('prog').style.width = '0%';
  $('statusLine').textContent = 'Start …';

  try {
    const d = await api('/api/run', { files: STATE.selection, opts });
    STATE.jobId = d.id;
    STATE.poll = setInterval(pollJob, 450);
  } catch (e) {
    $('statusLine').textContent = 'Fehler: ' + e.message;
    $('runBtn').disabled = false;
    $('cancelBtn').hidden = true;
  }
}

async function pollJob() {
  if (!STATE.jobId) return;
  let j;
  try { j = await api('/api/job/' + STATE.jobId); }
  catch { return; }

  const pct = j.total ? Math.round(j.done / j.total * 100) : 0;
  $('prog').style.width = pct + '%';
  $('statusLine').textContent = j.state === 'laeuft'
    ? `${j.done}/${j.total} · ${j.current || ''}`
    : `${j.state} · ${j.done}/${j.total}`;

  renderResults(j.results);

  if (j.state !== 'laeuft') {
    clearInterval(STATE.poll);
    STATE.poll = null;
    $('runBtn').disabled = false;
    $('cancelBtn').hidden = true;
    showTotals(j);
  }
}

let rendered = 0;
function renderResults(list) {
  const ul = $('results');
  for (let i = rendered; i < list.length; i++) {
    const r = list[i];
    const li = document.createElement('li');
    if (r.error) {
      li.className = 'err';
      li.innerHTML = `<span class="nm">${escapeHtml(r.name)}</span>` +
        `<span class="dt">${escapeHtml(r.error)}</span>`;
    } else {
      const win = !r.skipped && r.pct > 0.05;
      li.innerHTML =
        `<span class="nm">${escapeHtml(r.name)}</span>` +
        `<span class="sz">${human(r.old)} → ${human(r.new)}</span>` +
        `<span class="pc ${win ? 'win' : 'none'}">${
          win ? '-' + r.pct.toFixed(1) + '%' : '—'}</span>` +
        (r.detail ? `<span class="dt">${escapeHtml(r.detail)}</span>` : '');
      if (r.out) STATE.lastOutDir = r.out.replace(/[\\/][^\\/]+$/, '');
    }
    ul.appendChild(li);
  }
  rendered = list.length;
}

function showTotals(j) {
  if (!j.totalOld) return;
  const saved = j.totalOld - j.totalNew;
  const pct = j.totalOld ? saved / j.totalOld * 100 : 0;
  $('totals').hidden = false;
  $('totals').innerHTML = `
    <div><span class="k">vorher</span><span class="v">${human(j.totalOld)}</span></div>
    <div><span class="k">nachher</span><span class="v">${human(j.totalNew)}</span></div>
    <div><span class="k">gespart</span><span class="v hi">${human(saved)}</span></div>
    <div><span class="k">Ersparnis</span><span class="v hi">${pct.toFixed(1)} %</span></div>`;
  if (STATE.lastOutDir) $('openOut').hidden = false;
}

/* ------------------------------------------------------------- Anbindung */

$('goPath').onclick = () => browse($('pathInput').value.trim());
$('pathInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') browse($('pathInput').value.trim());
});
$('useFolder').onclick = useFolder;
$('clearSel').onclick = () => {
  STATE.selection = [];
  renderSelection();
  document.querySelectorAll('.filelist li.picked')
    .forEach((li) => li.classList.remove('picked'));
};
$('toggleAdv').onclick = () => {
  const a = $('adv');
  a.hidden = !a.hidden;
  $('toggleAdv').textContent = a.hidden ? 'Erweitert' : 'Weniger';
};
$('quality').oninput = (e) => { $('qOut').value = e.target.value; };
$('runBtn').onclick = () => { rendered = 0; run(); };
$('cancelBtn').onclick = () => api('/api/cancel', { id: STATE.jobId });
$('openOut').onclick = () => api('/api/reveal', { path: STATE.lastOutDir });

loadStatus().then(() => browse('')).catch((e) => {
  document.body.insertAdjacentHTML('afterbegin',
    `<div class="banner banner-warn"><strong>Fehler:</strong> ${e.message}</div>`);
});
