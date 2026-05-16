/* ═══════════════════════════════════════════════════
   JARVIS v3 — Frontend Logic + Mode Editor
   ═══════════════════════════════════════════════════ */

// ── Globals ───────────────────────────────────────────────
const FALLBACK_ICONS = { trabalho:'💼', foco:'🎯', reuniao:'🎙️', vava:'🎮', modo_padrao:'⚡', default:'🔷' };
function iconFor(mode) {
  if (mode?.icon) return mode.icon;
  return FALLBACK_ICONS[mode?.id] || FALLBACK_ICONS.default;
}

// ── Hotkey display helpers ────────────────────────────────
const KEY_LABELS = {
  ' ': 'Space', 'space': 'Space', 'arrowup': '↑', 'arrowdown': '↓',
  'arrowleft': '←', 'arrowright': '→', 'escape': 'Esc', 'enter': 'Enter',
  'tab': 'Tab', 'backspace': 'Backspace', 'delete': 'Delete', 'home': 'Home',
  'end': 'End', 'pageup': 'PgUp', 'pagedown': 'PgDn',
  'control': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'meta': 'Win', 'win': 'Win',
  'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4', 'f5': 'F5', 'f6': 'F6',
  'f7': 'F7', 'f8': 'F8', 'f9': 'F9', 'f10': 'F10', 'f11': 'F11', 'f12': 'F12',
};
function formatHotkey(combo) {
  if (!combo) return 'Sem atalho';
  return combo.split('+')
    .map(p => p.trim().toLowerCase())
    .map(p => KEY_LABELS[p] || (p.length === 1 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(' + ');
}
let _actionTypes = [];
let _editingMode = null; // current mode being edited in modal
let _editingActions = []; // mutable copy of actions in the modal

// ── Utils ──────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }
function formatTime(iso) { try { return new Date(iso).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}); } catch { return '--:--'; } }

// ── Toast ──────────────────────────────────────────────────
function showToast(msg, type = '') {
  let c = document.querySelector('.toast-container');
  if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); }
  const t = document.createElement('div');
  t.className = `toast${type ? ' ' + type : ''}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3100);
}

// ── Clock ──────────────────────────────────────────────────
function startClock() {
  const el = $('clock');
  const tick = () => el.textContent = new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
  tick(); setInterval(tick, 10000);
}

// ── Tabs ───────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById(`panel-${tab}`);
      if (panel) panel.classList.add('active');

      if (tab === 'modes') refreshModesList();
      if (tab === 'settings') loadSettings();
      if (tab === 'stats') loadStats();
    });
  });
}

// ── Stats: render da aba ──────────────────────────────────
async function loadStats() {
  try {
    const raw = await window.pywebview.api.get_history_stats();
    const stats = JSON.parse(raw);

    $('stats-total').textContent = stats.total ?? 0;
    const top = (stats.top_modes && stats.top_modes[0]) ? stats.top_modes[0] : null;
    $('stats-top-mode').textContent = top ? top.mode_name : '—';

    const toggle = $('config-history-enabled');
    if (toggle) toggle.checked = !!stats.enabled;

    // Barras por hora — escala relativa ao máximo
    const bars = $('hour-bars');
    bars.innerHTML = '';
    const max = Math.max(1, ...stats.by_hour.map(h => h.count));
    stats.by_hour.forEach(h => {
      const bar = document.createElement('div');
      bar.className = 'hour-bar';
      bar.dataset.count = h.count;
      const pct = (h.count / max) * 100;
      bar.style.height = `${Math.max(4, pct)}%`;
      bar.title = `${String(h.hour).padStart(2,'0')}:00 — ${h.count} ativação(ões)`;
      bars.appendChild(bar);
    });

    // Atividade recente
    const recent = $('stats-recent');
    if (!stats.recent || !stats.recent.length) {
      recent.innerHTML = '<div class="actions-empty">Sem ativações ainda.</div>';
    } else {
      recent.innerHTML = stats.recent.map(r => {
        const t = r.started_at ? new Date(r.started_at).toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'}) : '--:--';
        const cls = r.errors > 0 ? 'has-error' : '';
        return `<div class="stats-recent-row ${cls}">
          <span class="stats-recent-time">${t}</span>
          <span class="stats-recent-name">${r.mode_name}</span>
          <span class="stats-recent-source">${r.source}</span>
        </div>`;
      }).join('');
    }
  } catch (e) {
    console.warn('loadStats', e);
  }
}

// ── Dashboard: Load Modes Grid ────────────────────────────
async function loadModes() {
  const raw = await window.pywebview.api.get_modes();
  const modes = JSON.parse(raw);
  const grid = $('modes-grid');
  const countEl = $('modes-count');
  grid.innerHTML = '';
  countEl.textContent = `${modes.length} modos`;

  modes.forEach(mode => {
    const icon = iconFor(mode);
    const card = document.createElement('div');
    card.className = 'mode-card';
    card.dataset.modeId = mode.id;
    card.innerHTML = `
      <div class="mode-icon">${icon}</div>
      <div class="mode-name">${mode.name}</div>
      <div class="mode-desc">${mode.description || ''}</div>
      <div class="mode-actions-count">${(mode.actions||[]).length} ações</div>
      <button class="mode-run-btn" data-mode-id="${mode.id}">▶ ATIVAR</button>
    `;
    grid.appendChild(card);
  });

  grid.querySelectorAll('.mode-run-btn').forEach(btn => btn.addEventListener('click', e => { e.stopPropagation(); activateMode(btn.dataset.modeId); }));
  return modes;
}

// ── Dashboard: Status Polling ─────────────────────────────
async function updateStatus() {
  try {
    const status = JSON.parse(await window.pywebview.api.get_status());
    $('status-label').textContent = status.last_status || 'Aguardando';

    const grid = $('modes-grid');
    const defaultCard = grid?.querySelector(`[data-mode-id="${status.default_mode_id}"]`);
    const defaultName = defaultCard?.querySelector('.mode-name')?.textContent || status.default_mode_id;
    $('activate-mode-label').textContent = defaultName;

    grid?.querySelectorAll('.mode-card').forEach(c => c.classList.remove('active-mode'));
    if (status.active_mode_id) grid?.querySelector(`[data-mode-id="${status.active_mode_id}"]`)?.classList.add('active-mode');

    if (status.last_started_at && status.active_mode_name && status.last_started_at !== window._lastLoggedEvent) {
      window._lastLoggedEvent = status.last_started_at;
      addLog(`${status.active_mode_name} ativado`, status.last_trigger_source || 'sistema', formatTime(status.last_started_at));
    }

    if (status.last_error_time && status.last_error_time !== window._lastErrorTime) {
      window._lastErrorTime = status.last_error_time;
      showToast(status.last_error, 'error');
    }
  } catch {}
}

// ── Log ────────────────────────────────────────────────────
const _logQueue = [];
function addLog(title, source, time) {
  const panel = $('log-panel');
  panel.querySelector('.log-empty')?.remove();
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<span class="log-entry-time">${time||new Date().toLocaleTimeString('pt-BR')}</span><div class="log-entry-content"><div class="log-entry-title">${title}</div><div class="log-entry-source">via ${source}</div></div>`;
  panel.prepend(entry);
  _logQueue.push(entry);
  while (_logQueue.length > 30) _logQueue.shift()?.remove();
}

// ── Activate Mode ─────────────────────────────────────────
async function activateMode(modeId) {
  const btn = $('btn-activate');
  btn.classList.add('activating');
  showToast('⚡ Ativando modo...');
  try {
    const r = JSON.parse(await window.pywebview.api.activate_mode(modeId));
    if (!r.ok) showToast(`Erro: ${r.error}`, 'error');
  } catch { showToast('Erro ao ativar modo', 'error'); }
  setTimeout(() => btn.classList.remove('activating'), 3000);
}

async function activateDefault() {
  try {
    const s = JSON.parse(await window.pywebview.api.get_status());
    activateMode(s.default_mode_id);
  } catch { activateMode('modo_padrao'); }
}

// ══════════════════════════════════════════════════════════
// MODES EDITOR
// ══════════════════════════════════════════════════════════

// ── Modes List (Editor Tab) ───────────────────────────────
async function refreshModesList() {
  const raw = await window.pywebview.api.get_modes();
  const modes = JSON.parse(raw);
  const list = $('modes-list');
  list.innerHTML = '';

  if (!modes.length) {
    list.innerHTML = `<div class="actions-empty">Nenhum modo criado. Clique em "Novo Modo".</div>`;
    return;
  }

  modes.forEach(mode => {
    const icon = iconFor(mode);
    const item = document.createElement('div');
    item.className = 'mode-list-item';
    item.innerHTML = `
      <span class="mode-list-icon">${icon}</span>
      <div class="mode-list-info">
        <div class="mode-list-name">${mode.name}</div>
        <div class="mode-list-meta">${(mode.actions||[]).length} ações · ${mode.description || 'Sem descrição'}</div>
      </div>
      <div class="mode-list-actions">
        <button class="btn-icon-sm edit-btn" data-mode-id="${mode.id}" title="Editar">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
        </button>
        <button class="btn-icon-sm duplicate-btn" data-mode-id="${mode.id}" title="Duplicar">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M7 9a2 2 0 012-2h6a2 2 0 012 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2V9z"/><path d="M5 3a2 2 0 00-2 2v6a2 2 0 002 2V5h8a2 2 0 00-2-2H5z"/></svg>
        </button>
        <button class="btn-icon-sm danger delete-btn" data-mode-id="${mode.id}" data-mode-name="${mode.name}" title="Excluir">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
        </button>
      </div>
    `;
    list.appendChild(item);
  });

  list.querySelectorAll('.edit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = modes.find(m => m.id === btn.dataset.modeId);
      if (mode) openModal(mode);
    });
  });

  list.querySelectorAll('.duplicate-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const original = modes.find(m => m.id === btn.dataset.modeId);
      if (!original) return;

      // Clone profundo, preparando pra novo modo: id em branco (backend gera),
      // nome com sufixo (cópia), hotkey vazia (atalho deve ser único).
      const clone = JSON.parse(JSON.stringify(original));
      clone.id = undefined;
      clone.name = `${original.name} (cópia)`;
      clone.hotkey = '';

      try {
        const r = JSON.parse(await window.pywebview.api.save_mode(JSON.stringify(clone)));
        if (r.ok) {
          showToast('📑 Modo duplicado', 'success');
          refreshModesList();
          loadModes();
        } else {
          const detail = (r.errors && r.errors.length) ? r.errors.join(' · ') : (r.error || 'desconhecido');
          showToast(`Erro ao duplicar: ${detail}`, 'error');
        }
      } catch (e) {
        showToast(`Erro: ${e}`, 'error');
      }
    });
  });

  list.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Excluir o modo "${btn.dataset.modeName}"?`)) return;
      await window.pywebview.api.delete_mode(btn.dataset.modeId);
      showToast('🗑️ Modo excluído', 'success');
      refreshModesList();
      loadModes(); // refresh grid too
    });
  });
}

// ── Modal ─────────────────────────────────────────────────
function openModal(mode = null) {
  _editingMode = mode;
  _editingActions = mode ? JSON.parse(JSON.stringify(mode.actions || [])) : [];

  $('modal-title').textContent = mode ? 'Editar Modo' : 'Novo Modo';
  $('edit-mode-id').value = mode?.id || '';
  $('edit-mode-name').value = mode?.name || '';
  $('edit-mode-icon').value = mode?.icon || '';
  $('edit-mode-description').value = mode?.description || '';
  const schedInput = $('edit-mode-schedule');
  if (schedInput) schedInput.value = mode?.schedule || '';
  // Hotkey: input hidden + display formatado
  const hkInput = $('edit-mode-hotkey');
  const hkDisplay = $('edit-mode-hotkey-display');
  const hkValue = mode?.hotkey || '';
  if (hkInput) hkInput.value = hkValue;
  if (hkDisplay) {
    hkDisplay.textContent = formatHotkey(hkValue);
    hkDisplay.classList.toggle('has-value', !!hkValue);
    hkDisplay.classList.remove('recording');
  }

  renderActionsList();
  $('modal-overlay').classList.add('open');
}

function closeModal() {
  $('modal-overlay').classList.remove('open');
  _editingMode = null;
  _editingActions = [];
}

// ── Render Actions in Modal ───────────────────────────────
function renderActionsList() {
  const container = $('actions-list');
  container.innerHTML = '';

  if (!_editingActions.length) {
    container.innerHTML = `<div class="actions-empty">Nenhuma ação. Clique em "Adicionar Ação".</div>`;
    return;
  }

  _editingActions.forEach((action, idx) => {
    const typeDef = _actionTypes.find(t => t.type === action.type) || { label: action.type, icon: '❓', fields: [], hint: '' };
    const item = document.createElement('div');
    item.className = 'action-item';

    const fieldsHtml = typeDef.fields.map(field => {
      const req = field.required ? ' <span style="color:#ff6b6b">*</span>' : '';
      return `
      <div class="form-group">
        <label class="form-label">${field.label}${req}</label>
        <div style="display:flex;gap:6px">
          <input class="form-input action-field" data-idx="${idx}" data-key="${field.key}"
            type="${field.type || 'text'}" placeholder="${field.placeholder || ''}"
            value="${action[field.key] || ''}" style="flex:1" />
          ${field.picker ? `<button class="btn-ghost btn-picker" data-picker="${field.picker}" data-idx="${idx}" data-key="${field.key}" style="padding:0 12px;font-size:11px">Procurar</button>` : ''}
        </div>
      </div>`;
    }).join('');

    const hintHtml = typeDef.hint
      ? `<div class="action-hint"><svg viewBox="0 0 20 20" fill="currentColor" width="13" height="13" style="flex-shrink:0;margin-top:1px"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg><span>${typeDef.hint}</span></div>`
      : '';

    item.dataset.idx = idx;
    item.draggable = true;
    item.innerHTML = `
      <div class="action-item-header">
        <span class="action-drag-handle" title="Arraste pra reordenar">⋮⋮</span>
        <span class="action-type-icon">${typeDef.icon}</span>
        <select class="form-select action-type-select" data-idx="${idx}" style="max-width:160px;padding:4px 28px 4px 8px;font-size:11px">
          ${_actionTypes.map(t => `<option value="${t.type}" ${t.type===action.type?'selected':''}>${t.label}</option>`).join('')}
        </select>
        <button class="action-remove-btn" data-idx="${idx}" title="Remover">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
        </button>
      </div>
      ${(hintHtml || fieldsHtml) ? `<div class="action-item-body">${hintHtml}${fieldsHtml}</div>` : ''}
    `;
    container.appendChild(item);
  });

  // Drag-and-drop nativo HTML5 — zero deps
  let _dragSrcIdx = null;
  container.querySelectorAll('.action-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      _dragSrcIdx = parseInt(item.dataset.idx, 10);
      item.classList.add('dragging');
      // Suprime drag visual no firefox/edge
      try { e.dataTransfer.setData('text/plain', String(_dragSrcIdx)); } catch {}
      e.dataTransfer.effectAllowed = 'move';
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      container.querySelectorAll('.action-item').forEach(i => i.classList.remove('drag-over'));
    });
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      item.classList.add('drag-over');
    });
    item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      const dstIdx = parseInt(item.dataset.idx, 10);
      if (_dragSrcIdx === null || isNaN(dstIdx) || _dragSrcIdx === dstIdx) return;
      const [moved] = _editingActions.splice(_dragSrcIdx, 1);
      _editingActions.splice(dstIdx, 0, moved);
      _dragSrcIdx = null;
      renderActionsList();
    });
  });


  // Bind: type change
  container.querySelectorAll('.action-type-select').forEach(sel => {
    sel.addEventListener('change', () => {
      const idx = +sel.dataset.idx;
      const newType = sel.value;
      _editingActions[idx] = { type: newType };
      renderActionsList();
    });
  });

  // Bind: field change
  container.querySelectorAll('.action-field').forEach(input => {
    input.addEventListener('input', () => {
      const idx = +input.dataset.idx;
      const key = input.dataset.key;
      _editingActions[idx][key] = input.value;
    });
  });

  // Bind: remove
  container.querySelectorAll('.action-remove-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _editingActions.splice(+btn.dataset.idx, 1);
      renderActionsList();
    });
  });

  // Bind: picker buttons
  container.querySelectorAll('.btn-picker').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pickerType = btn.dataset.picker;
      const idx = +btn.dataset.idx;
      const key = btn.dataset.key;
      
      let resRaw;
      btn.textContent = '...';
      try {
        if (pickerType === 'file') {
          resRaw = await window.pywebview.api.pick_file();
        } else if (pickerType === 'folder') {
          resRaw = await window.pywebview.api.pick_folder();
        }
        
        const res = JSON.parse(resRaw);
        if (res.ok && res.path) {
          _editingActions[idx][key] = res.path;
          renderActionsList();
        }
      } catch(e) { console.error('Picker error', e); }
      btn.textContent = 'Procurar';
    });
  });
}

// ── Save Mode ─────────────────────────────────────────────
function _frontendValidate(name, actions) {
  const errors = [];
  if (!name.trim()) errors.push('Digite um nome para o modo');
  if (!actions.length) errors.push('Adicione pelo menos 1 ação');

  actions.forEach((action, idx) => {
    const num = idx + 1;
    const def = _actionTypes.find(t => t.type === action.type);
    if (!def) {
      errors.push(`Ação #${num}: tipo "${action.type}" inválido`);
      return;
    }
    for (const field of def.fields || []) {
      if (!field.required) continue;
      const v = action[field.key];
      if (v === undefined || v === null || (typeof v === 'string' && !v.trim())) {
        errors.push(`Ação #${num} (${def.label}): preencha "${field.label}"`);
      }
    }
  });
  return errors;
}

async function saveMode() {
  const name = $('edit-mode-name').value.trim();

  // Validação client-side primeiro — feedback instantâneo
  const errs = _frontendValidate(name, _editingActions);
  if (errs.length) {
    // Toast com no máximo 2 primeiros erros — o resto vai pro log do console
    showToast(errs.slice(0, 2).join(' · '), 'error');
    if (errs.length > 2) console.warn('Mais erros:', errs.slice(2));
    return;
  }

  const mode = {
    id: $('edit-mode-id').value || undefined,
    name,
    icon: $('edit-mode-icon').value.trim(),
    description: $('edit-mode-description').value.trim(),
    hotkey: ($('edit-mode-hotkey')?.value || '').trim(),
    schedule: ($('edit-mode-schedule')?.value || '').trim(),
    actions: _editingActions,
    triggers: _editingMode?.triggers || {},
  };

  const r = JSON.parse(await window.pywebview.api.save_mode(JSON.stringify(mode)));
  if (r.ok) {
    showToast('✅ Modo salvo!', 'success');
    closeModal();
    refreshModesList();
    loadModes();
  } else {
    const detail = (r.errors && r.errors.length) ? r.errors.join(' · ') : (r.error || 'desconhecido');
    showToast(`Erro: ${detail}`, 'error');
  }
}

// ── Load Action Types from API ────────────────────────────
async function loadActionTypes() {
  const raw = await window.pywebview.api.get_action_types();
  _actionTypes = JSON.parse(raw);
}

// ════════════════════════════════════════════════════════════
// SETTINGS
// ════════════════════════════════════════════════════════════
async function loadSettings() {
  try {
    // 1. Popula os modos
    const modesRaw = await window.pywebview.api.get_modes();
    const modes = JSON.parse(modesRaw);
    const select = $('config-default-mode');
    select.innerHTML = '';
    modes.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      select.appendChild(opt);
    });

    // 2. Carrega a configuracao atual
    const configRaw = await window.pywebview.api.get_config();
    const config = JSON.parse(configRaw);
    
    // Modo padrao
    select.value = config.modes?.default_mode || 'modo_padrao';
    
    // Atalhos: sao objetos {enabled, combination} - exibe a combination no display
    const fmtHotkey = (hk) => {
      if (!hk) return '---';
      const c = typeof hk === 'object' ? (hk.combination || '') : hk;
      // Formata para humano: ctrl+alt+j => Ctrl + Alt + J
      return c.split('+').map(k => k.trim().replace(/^./, s => s.toUpperCase())).join(' + ');
    };
    const el_activate = $('display-hotkey-activate');
    const el_stop = $('display-hotkey-stop');
    const el_voice = $('display-hotkey-voice');
    if (el_activate) el_activate.textContent = fmtHotkey(config.hotkeys?.activate);
    if (el_stop)     el_stop.textContent     = fmtHotkey(config.hotkeys?.stop);
    if (el_voice)    el_voice.textContent     = fmtHotkey(config.hotkeys?.voice);

    // ── TTS (Voz neural) ──
    try {
      const voicesRaw = await window.pywebview.api.list_tts_voices();
      const voicesObj = JSON.parse(voicesRaw);
      const voiceSel = $('config-tts-voice');
      if (voiceSel) {
        voiceSel.innerHTML = '';
        const voices = (voicesObj.voices || []);
        if (voices.length === 0) {
          const opt = document.createElement('option');
          opt.value = '';
          opt.textContent = '(falha ao listar — sem internet?)';
          voiceSel.appendChild(opt);
        } else {
          voices.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.short_name;
            const gender = v.gender === 'Male' ? 'masc' : v.gender === 'Female' ? 'fem' : '';
            opt.textContent = gender ? `${v.friendly} (${gender})` : v.friendly;
            voiceSel.appendChild(opt);
          });
        }
        const currentVoice = config.tts?.voice || 'pt-BR-AntonioNeural';
        voiceSel.value = currentVoice;
        // Se a voz salva não existe na lista, mantém como opção solta
        if (voiceSel.value !== currentVoice) {
          const opt = document.createElement('option');
          opt.value = currentVoice;
          opt.textContent = currentVoice;
          voiceSel.appendChild(opt);
          voiceSel.value = currentVoice;
        }
      }
    } catch (e) { console.warn('list_tts_voices', e); }

    // ── Wake Word threshold ──
    const wakeSlider = $('config-wake-threshold');
    const wakeLabel = $('config-wake-threshold-label');
    if (wakeSlider) {
      const t = (typeof config.wake_word?.threshold === 'number') ? config.wake_word.threshold : 0.35;
      wakeSlider.value = t;
      if (wakeLabel) wakeLabel.textContent = formatThresholdLabel(t);
    }

    // Autostart — lê estado real do registry, não da config
    try {
      const asRaw = await window.pywebview.api.get_autostart_status();
      const asObj = JSON.parse(asRaw);
      const cb = $('config-autostart');
      if (cb) {
        cb.checked = !!asObj.enabled;
        const lbl = $('config-autostart-label');
        if (lbl) lbl.textContent = asObj.enabled ? 'On' : 'Off';
      }
    } catch (e) { console.warn('autostart status', e); }

    // API Key de voz + badge de status no onboarding
    const apiKey = config.voice_ai?.api_key || '';
    $('config-voice-api-key').value = apiKey;
    $('btn-voice').title = apiKey
      ? 'Clique para falar com JARVIS'
      : 'Configure a API Key em Configurações → Voz IA';
    const badge = $('voice-key-status');
    if (badge) {
      if (apiKey) {
        badge.textContent = '✓ conectado';
        badge.classList.add('connected');
      } else {
        badge.textContent = 'não configurado';
        badge.classList.remove('connected');
      }
    }
    
  } catch (e) {
    console.error('loadSettings error:', e);
    showToast('Erro ao carregar configuracoes', 'error');
  }
}

function formatThresholdLabel(t) {
  if (t <= 0.30) return `${t.toFixed(2)} — muito permissivo`;
  if (t <= 0.40) return `${t.toFixed(2)} — permissivo`;
  if (t <= 0.55) return `${t.toFixed(2)} — balanceado`;
  if (t <= 0.65) return `${t.toFixed(2)} — estrito`;
  return `${t.toFixed(2)} — muito estrito`;
}

async function saveSettings() {
  const defaultMode = $('config-default-mode').value;
  const apiKey = ($('config-voice-api-key').value || '').trim();
  const ttsVoice = ($('config-tts-voice')?.value || '').trim();
  const wakeThreshold = parseFloat($('config-wake-threshold')?.value || '0.35');

  // Manda apenas o que o formulario expoe — hotkeys sao preservados pelo backend
  const partialConfig = {
    modes: { default_mode: defaultMode },
    voice_ai: { api_key: apiKey },
    tts: ttsVoice ? { voice: ttsVoice, provider: 'edge' } : {},
    wake_word: { threshold: isNaN(wakeThreshold) ? 0.35 : wakeThreshold },
  };

  try {
    const resRaw = await window.pywebview.api.save_config(JSON.stringify(partialConfig));
    const res = JSON.parse(resRaw);
    if (res.ok) {
      showToast('Configuracoes salvas!', 'success');
      updateStatus();
      $('btn-voice').title = apiKey
        ? 'Clique para falar com JARVIS'
        : 'Configure a API Key em Configurações → Voz IA';
      const badge = $('voice-key-status');
      if (badge) {
        if (apiKey) { badge.textContent = '✓ conectado'; badge.classList.add('connected'); }
        else { badge.textContent = 'não configurado'; badge.classList.remove('connected'); }
      }
    } else {
      showToast('Erro: ' + (res.error || 'desconhecido'), 'error');
    }
  } catch (e) {
    console.error('saveSettings error:', e);
    showToast('Erro ao salvar', 'error');
  }
}


// ── Bind All Events ───────────────────────────────────────
function bindEvents() {
  $('btn-activate').addEventListener('click', activateDefault);
  $('btn-close').addEventListener('click', async () => {
    try { await window.pywebview.api.hide_panel(); } catch {}
  });

  // Tabs
  initTabs();

  // Onboarding wizard (mostrado apenas na 1ª execução)
  bindOnboarding();

  // Feedback modal
  bindFeedback();

  // Editor
  $('btn-new-mode').addEventListener('click', () => openModal(null));

  // Exportar modos pra arquivo JSON
  $('btn-export-modes').addEventListener('click', async () => {
    try {
      const r = JSON.parse(await window.pywebview.api.export_modes());
      if (r.ok) {
        showToast(`📦 ${r.count} modo(s) salvos em ${r.path}`, 'success');
      } else if (r.error !== 'Cancelado') {
        showToast(`Erro ao exportar: ${r.error}`, 'error');
      }
    } catch (e) {
      showToast(`Erro: ${e}`, 'error');
    }
  });

  // Importar modos de arquivo JSON
  $('btn-import-modes').addEventListener('click', async () => {
    const replace = confirm(
      'Como importar?\n\n' +
      'OK   = SUBSTITUIR todos os modos atuais pelos do arquivo\n' +
      'Cancelar = ADICIONAR aos modos existentes (gera ID novo se houver conflito)'
    );
    try {
      const r = JSON.parse(await window.pywebview.api.import_modes(replace));
      if (r.ok) {
        showToast(`📥 ${r.imported} modo(s) importados (total: ${r.total})`, 'success');
        refreshModesList();
        loadModes();
      } else if (r.error !== 'Cancelado') {
        const detail = (r.errors && r.errors.length) ? r.errors.slice(0, 3).join(' · ') : r.error;
        showToast(`Erro ao importar: ${detail}`, 'error');
      }
    } catch (e) {
      showToast(`Erro: ${e}`, 'error');
    }
  });
  $('modal-close').addEventListener('click', closeModal);
  $('btn-cancel-mode').addEventListener('click', closeModal);
  $('modal-overlay').addEventListener('click', e => { if (e.target === $('modal-overlay')) closeModal(); });

  $('btn-add-action').addEventListener('click', () => {
    const defaultType = _actionTypes[0]?.type || 'open_url';
    _editingActions.push({ type: defaultType });
    renderActionsList();
  });

  $('btn-save-mode').addEventListener('click', saveMode);

  // Hotkey recorder — captura de teclas pressionadas
  let _capturingHotkey = false;
  let _hotkeyHandler = null;
  const stopHotkeyCapture = () => {
    if (_hotkeyHandler) {
      document.removeEventListener('keydown', _hotkeyHandler, true);
      _hotkeyHandler = null;
    }
    _capturingHotkey = false;
    $('edit-mode-hotkey-display').classList.remove('recording');
  };
  $('btn-record-hotkey').addEventListener('click', () => {
    if (_capturingHotkey) { stopHotkeyCapture(); return; }
    _capturingHotkey = true;
    const display = $('edit-mode-hotkey-display');
    display.textContent = 'Pressione as teclas...';
    display.classList.add('recording');
    display.classList.remove('has-value');

    _hotkeyHandler = (e) => {
      const k = (e.key || '').toLowerCase();
      // Ignora se for SÓ um modificador (espera tecla "real")
      if (['control','alt','shift','meta','os','altgraph'].includes(k)) return;
      e.preventDefault();
      e.stopPropagation();

      const parts = [];
      if (e.ctrlKey)  parts.push('ctrl');
      if (e.altKey)   parts.push('alt');
      if (e.shiftKey) parts.push('shift');
      if (e.metaKey)  parts.push('win');

      // Normaliza key: arrows / espaço / etc, e letras maiúsculas
      let keyName = k;
      if (k === ' ') keyName = 'space';
      else if (k === 'arrowup') keyName = 'up';
      else if (k === 'arrowdown') keyName = 'down';
      else if (k === 'arrowleft') keyName = 'left';
      else if (k === 'arrowright') keyName = 'right';
      else if (k === 'escape') keyName = 'esc';
      parts.push(keyName);

      const combo = parts.join('+');
      $('edit-mode-hotkey').value = combo;
      const display = $('edit-mode-hotkey-display');
      display.textContent = formatHotkey(combo);
      display.classList.add('has-value');
      stopHotkeyCapture();
    };
    document.addEventListener('keydown', _hotkeyHandler, true);
  });

  $('btn-clear-hotkey').addEventListener('click', () => {
    stopHotkeyCapture();
    $('edit-mode-hotkey').value = '';
    const display = $('edit-mode-hotkey-display');
    display.textContent = 'Sem atalho';
    display.classList.remove('has-value');
  });
  
  // Settings
  $('btn-save-settings').addEventListener('click', saveSettings);

  // Show/Hide API key
  $('btn-toggle-key').addEventListener('click', () => {
    const inp = $('config-voice-api-key');
    inp.type = inp.type === 'password' ? 'text' : 'password';
  });

  // Wake-word threshold: atualiza label em tempo real
  const wakeSlider = $('config-wake-threshold');
  const wakeLabel = $('config-wake-threshold-label');
  if (wakeSlider && wakeLabel) {
    wakeSlider.addEventListener('input', () => {
      const t = parseFloat(wakeSlider.value);
      wakeLabel.textContent = formatThresholdLabel(t);
    });
  }

  // Botão "Testar voz" — sintetiza uma frase com a voz selecionada (sem salvar)
  const btnPreview = $('btn-preview-voice');
  if (btnPreview) {
    btnPreview.addEventListener('click', async () => {
      const voice = ($('config-tts-voice')?.value || '').trim();
      if (!voice) { showToast('Escolha uma voz primeiro', 'error'); return; }
      btnPreview.disabled = true;
      const orig = btnPreview.innerHTML;
      btnPreview.innerHTML = '<span style="font-size:11px;">tocando...</span>';
      try {
        const r = JSON.parse(await window.pywebview.api.preview_tts(voice, ''));
        if (!r.ok) showToast('Erro: ' + (r.error || 'falha'), 'error');
      } catch (e) {
        showToast('Erro: ' + e, 'error');
      } finally {
        btnPreview.disabled = false;
        btnPreview.innerHTML = orig;
      }
    });
  }

  // Autostart toggle (registry, não config)
  const cbAutostart = $('config-autostart');
  if (cbAutostart) {
    cbAutostart.addEventListener('change', async () => {
      const want = cbAutostart.checked;
      try {
        const r = JSON.parse(await window.pywebview.api.set_autostart(want));
        const lbl = $('config-autostart-label');
        if (lbl) lbl.textContent = r.enabled ? 'On' : 'Off';
        cbAutostart.checked = !!r.enabled;
        showToast(r.message || (r.enabled ? '🚀 Autostart ativado' : '⏸ Autostart desativado'), r.ok ? 'success' : 'error');
      } catch (e) {
        cbAutostart.checked = !want;  // reverte UI
        showToast('Erro: ' + e, 'error');
      }
    });
  }

  // Botão "Abrir Groq Console" — abre no NAVEGADOR DO SISTEMA, não dentro da webview
  const btnGroq = $('btn-open-groq');
  if (btnGroq) {
    btnGroq.addEventListener('click', async () => {
      try {
        await window.pywebview.api.open_external_url('https://console.groq.com/keys');
        showToast('🌐 Abrindo Groq no navegador...', 'success');
      } catch (e) {
        showToast('Erro ao abrir navegador: ' + e, 'error');
      }
    });
  }

  // Botão Falar — clique único: começa, ouve, detecta silêncio, responde, libera.
  // Segundo clique enquanto grava = parar manualmente.
  $('btn-voice').addEventListener('click', async () => {
    const btn = $('btn-voice');
    const label = $('voice-btn-label');

    // Já está em algum estágio do ciclo? Segundo clique enquanto grava = parar manualmente.
    // Não trocamos pra "Processando..." aqui — o polling vê o backend ir pra "transcribing"
    // em <400ms e atualiza o botão pra "Pensando..." direto.
    if (btn.classList.contains('recording')) {
      try { await window.pywebview.api.stop_voice_listen(); } catch {}
      return;
    }
    if (btn.classList.contains('processing')) {
      return; // já está em "Pensando..." — ignora cliques
    }

    // Verifica se a API key está setada antes de iniciar — falha visível, não silenciosa.
    try {
      const cfg = JSON.parse(await window.pywebview.api.get_config());
      if (!cfg.voice_ai?.api_key) {
        showToast('Configure a Groq API Key em Configurações → Voz IA', 'error');
        return;
      }
    } catch (e) {
      showToast('Erro ao ler configuração: ' + e, 'error');
      return;
    }

    // Início do ciclo
    btn.classList.add('recording');
    label.textContent = 'Ouvindo...';
    $('voice-transcript').style.display = 'none';
    try {
      await window.pywebview.api.start_voice_listen();
    } catch (e) {
      btn.classList.remove('recording');
      label.textContent = 'Falar';
      showToast('Erro ao iniciar gravação: ' + e, 'error');
      return;
    }
    pollVoiceStatus();  // já começa a observar status
  });

  // Logs
  $('btn-clear-logs').addEventListener('click', async () => {
    await window.pywebview.api.clear_logs();
    renderLogs([]);
  });

  // Stats
  const toggleHist = $('config-history-enabled');
  if (toggleHist) {
    toggleHist.addEventListener('change', async () => {
      try {
        const r = JSON.parse(await window.pywebview.api.set_history_enabled(toggleHist.checked));
        showToast(r.enabled ? '📊 Coleta ligada' : '🔒 Coleta desligada', 'success');
      } catch (e) {
        showToast('Erro: ' + e, 'error');
      }
    });
  }
  const btnClearHist = $('btn-clear-history');
  if (btnClearHist) {
    btnClearHist.addEventListener('click', async () => {
      if (!confirm('Apagar TODO o histórico de ativações? Não tem volta.')) return;
      try {
        const r = JSON.parse(await window.pywebview.api.clear_history());
        showToast(`🗑️ ${r.removed} entrada(s) apagadas`, 'success');
        loadStats();
      } catch (e) {
        showToast('Erro: ' + e, 'error');
      }
    });
  }
}

// ── Voice indicator (chip permanente no header) ──────────
// Reflete o estado atual da voz: idle (verde, ouvindo wake word), recording,
// transcribing, follow_up, error. Independe do botão Falar.
async function pollVoiceIndicator() {
  const chip = $('voice-chip');
  const label = $('voice-chip-label');
  if (!chip) return;
  try {
    const vs = JSON.parse(await window.pywebview.api.get_voice_status());

    // Sem chave Groq = voz desligada (off, mas o wake word ainda escuta).
    let state = 'idle', text = "ouvindo 'hey jarvis'";

    if (vs.recording) {
      state = 'recording';
      text = 'gravando';
    } else if (vs.processing || vs.status === 'transcribing') {
      state = 'transcribing';
      text = 'pensando';
    } else if (vs.follow_up_listening || vs.status === 'follow_up') {
      state = 'follow_up';
      text = 'continuando';
    } else if (vs.status === 'error' && vs.error) {
      state = 'error';
      text = 'erro';
    }

    if (chip.dataset.state !== state) chip.dataset.state = state;
    if (label.textContent !== text) label.textContent = text;
  } catch {
    // bridge não disponível ainda — mantém estado atual
  }
}

// ── Voice AI: Aura visual em tempo real ───────────────────
let _rmsPoll = null;
function startRmsPoll() {
  if (_rmsPoll) return;
  const auraA = $('voice-aura');
  const auraB = $('voice-aura-2');
  if (!auraA) return;
  _rmsPoll = setInterval(async () => {
    try {
      const raw = await window.pywebview.api.get_voice_rms();
      const rms = parseFloat(raw) || 0;
      // Mapeia RMS [50..2000+] → norm [0..1] com curva suave
      const norm = Math.min(1, Math.max(0, (rms - 50) / 1500));
      // Easing: deixa silêncio bem baixinho e voz alta vívida
      const eased = Math.pow(norm, 0.7);
      const scale = (0.6 + eased * 0.85).toFixed(3);  // 0.6 .. 1.45
      const alpha = (eased * 0.9).toFixed(3);          // 0   .. 0.9
      auraA.style.setProperty('--rms-scale', scale);
      auraA.style.setProperty('--rms-alpha', alpha);
      if (auraB) {
        auraB.style.setProperty('--rms-scale', scale);
        auraB.style.setProperty('--rms-alpha', alpha);
      }
    } catch {}
  }, 80);
}
function stopRmsPoll() {
  if (_rmsPoll) { clearInterval(_rmsPoll); _rmsPoll = null; }
  const auraA = $('voice-aura');
  const auraB = $('voice-aura-2');
  [auraA, auraB].forEach(a => {
    if (!a) return;
    a.style.setProperty('--rms-scale', '0.6');
    a.style.setProperty('--rms-alpha', '0');
  });
}

// ── Voice AI: Poll for Transcription Result ───────────────
function pollVoiceStatus() {
  if (window._voicePollActive) return;  // evita pollings paralelos
  window._voicePollActive = true;

  const maxTries = 90; // até 45s (gravação longa + transcribe + LLM)
  let tries = 0;
  const t = $('voice-transcript');
  const statusEl = $('voice-status-text');
  const textEl = $('voice-text');
  const modeEl = $('voice-mode-text');
  const btn = $('btn-voice');
  const label = $('voice-btn-label');

  t.style.display = 'flex';
  statusEl.textContent = '🎤 Ouvindo...';
  textEl.textContent = '';
  modeEl.textContent = '';

  const reset = () => {
    btn.classList.remove('recording', 'processing');
    label.textContent = 'Falar';
    window._voicePollActive = false;
    stopRmsPoll();
  };

  // Aura começa imediatamente — feedback visual antes mesmo do backend confirmar
  startRmsPoll();

  const poll = setInterval(async () => {
    tries++;
    try {
      const vs = JSON.parse(await window.pywebview.api.get_voice_status());

      // Transição automática: ao detectar silêncio, backend muda recording=false
      // e status vira "transcribing". Refletimos no botão.
      if (vs.status === 'recording') {
        statusEl.textContent = '🎤 Ouvindo...';
        if (!btn.classList.contains('recording')) {
          btn.classList.add('recording');
          label.textContent = 'Ouvindo...';
        }
        return;
      }

      if (vs.status === 'transcribing') {
        statusEl.textContent = '🧠 Pensando...';
        if (!btn.classList.contains('processing')) {
          btn.classList.remove('recording');
          btn.classList.add('processing');
          label.textContent = 'Pensando...';
          stopRmsPoll();  // já parou de gravar — aura some
        }
        return;
      }

      if (vs.status === 'follow_up') {
        statusEl.textContent = '🎤 Pode continuar...';
        if (!btn.classList.contains('recording')) {
          btn.classList.remove('processing');
          btn.classList.add('recording');
          label.textContent = 'Continuando...';
          startRmsPoll();  // aura volta a pulsar
        }
        return;
      }

      // done | error
      clearInterval(poll);
      reset();

      if (vs.status === 'done') {
        const isChat = vs.last_response_type === 'chat';
        statusEl.textContent = isChat ? '💬 Resposta' : '✅ Executado';
        textEl.textContent = vs.last_transcript ? `"${vs.last_transcript}"` : '';
        if (isChat && vs.last_response) {
          modeEl.textContent = `🤖 ${vs.last_response}`;
          showToast(`🤖 ${vs.last_response}`, 'success');
        } else {
          modeEl.textContent = `→ ${vs.last_matched_mode || 'modo'}`;
          showToast(`🎤 "${vs.last_transcript}"`, 'success');
        }
      } else if (vs.status === 'error') {
        statusEl.textContent = '⚠️ Erro';
        textEl.textContent = vs.error || 'Falha desconhecida';
        showToast(vs.error || 'Erro de voz', 'error');
      }
    } catch {
      if (tries >= maxTries) {
        clearInterval(poll);
        reset();
        showToast('Tempo esgotado aguardando resposta', 'error');
      }
    }
  }, 400);
}

// ── Bootstrap ─────────────────────────────────────────────
function waitForAPI(cb, n = 0) {
  if (window.pywebview?.api) cb();
  else if (n < 80) setTimeout(() => waitForAPI(cb, n+1), 100);
}

// ── Log Console ────────────────────────────────────────────
function renderLogs(entries) {
  const el = $('log-console');
  if (!entries || entries.length === 0) {
    el.innerHTML = '<div class="log-empty">Nenhuma ação executada ainda.</div>';
    return;
  }
  el.innerHTML = entries.map(e =>
    `<div class="log-entry ${e.level}">
      <span class="log-time">${e.time}</span>
      <span class="log-msg">${e.msg}</span>
    </div>`
  ).join('');
  // Auto-scroll para o final
  el.scrollTop = el.scrollHeight;
}

// Atualiza a barra de status sempre visível com a última entrada do log
function updateStatusBar(entry) {
  const bar = $('status-bar');
  const icon = $('status-bar-icon');
  const txt = $('status-bar-text');
  const time = $('status-bar-time');
  if (!bar) return;
  const level = entry.level || 'info';
  bar.classList.remove('success', 'error', 'warn', 'info');
  bar.classList.add(level);
  const icons = { success: '✔', error: '✖', warn: '⚠', info: '●' };
  icon.textContent = icons[level] || '●';
  txt.textContent = entry.msg || '';
  time.textContent = entry.time || '';
}

// Marcador do último log já visto, pra disparar toast só em entradas novas
window._lastLogKey = null;
async function pollLogs() {
  try {
    const raw = await window.pywebview.api.get_logs();
    const entries = JSON.parse(raw);
    renderLogs(entries);

    if (Array.isArray(entries) && entries.length) {
      // Sempre reflete a última entrada na barra de status (cor + texto)
      updateStatusBar(entries[entries.length - 1]);

      const last = entries[entries.length - 1];
      const key = `${last.time}|${last.msg}`;
      if (window._lastLogKey === null) {
        window._lastLogKey = key;
      } else if (key !== window._lastLogKey) {
        const idx = entries.findIndex(e => `${e.time}|${e.msg}` === window._lastLogKey);
        const fresh = idx >= 0 ? entries.slice(idx + 1) : entries;
        for (const e of fresh) {
          if (e.level === 'error') showToast(e.msg, 'error');
          else if (e.level === 'warn') showToast(e.msg, '');
          else if (e.level === 'success' && e.msg.startsWith('✔')) showToast(e.msg, 'success');
        }
        window._lastLogKey = key;
      }
    }
  } catch (err) {
    console.warn('pollLogs falhou:', err);
  }
}

// ── Feedback modal ────────────────────────────────────────
async function openFeedbackModal() {
  const overlay = $('feedback-overlay');
  const warn = $('fb-disabled-warning');
  $('fb-text').value = '';
  $('fb-name').value = '';
  warn.style.display = 'none';

  // Verifica se o canal está configurado — UI deixa claro se não estiver
  try {
    const r = JSON.parse(await window.pywebview.api.get_feedback_status());
    if (!r.configured) {
      warn.style.display = 'block';
    }
  } catch {}

  overlay.classList.add('open');
  setTimeout(() => $('fb-text').focus(), 50);
}

function closeFeedbackModal() {
  $('feedback-overlay').classList.remove('open');
}

async function sendFeedback() {
  const text = $('fb-text').value.trim();
  const name = $('fb-name').value.trim();
  if (!text) {
    showToast('Digite uma mensagem antes de enviar', 'error');
    $('fb-text').focus();
    return;
  }
  if (text.length < 3) {
    showToast('Mensagem muito curta', 'error');
    return;
  }

  const btn = $('fb-send');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = 'Enviando...';

  try {
    const r = JSON.parse(await window.pywebview.api.send_feedback(text, name));
    if (r.ok) {
      showToast('📬 Feedback enviado, valeu!', 'success');
      closeFeedbackModal();
    } else {
      showToast(`Erro: ${r.message || 'desconhecido'}`, 'error');
    }
  } catch (e) {
    showToast(`Erro: ${e}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function bindFeedback() {
  $('btn-feedback').addEventListener('click', openFeedbackModal);
  $('fb-close').addEventListener('click', closeFeedbackModal);
  $('fb-cancel').addEventListener('click', closeFeedbackModal);
  $('fb-send').addEventListener('click', sendFeedback);
  $('feedback-overlay').addEventListener('click', e => {
    if (e.target === $('feedback-overlay')) closeFeedbackModal();
  });
  // Ctrl+Enter envia (atalho de power user)
  $('fb-text').addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      sendFeedback();
    }
  });
}

// ── Onboarding wizard ─────────────────────────────────────
let _obStep = 1;
const OB_TOTAL_STEPS = 4;

function obShow() {
  $('onboarding-overlay').classList.add('active');
  obGoTo(1);
}
function obHide() {
  $('onboarding-overlay').classList.remove('active');
}

function obGoTo(step) {
  _obStep = Math.max(1, Math.min(OB_TOTAL_STEPS, step));
  document.querySelectorAll('.ob-screen').forEach(s => {
    s.classList.toggle('active', parseInt(s.dataset.screen, 10) === _obStep);
  });
  document.querySelectorAll('.ob-dot').forEach((d, i) => {
    d.classList.toggle('active', i === _obStep - 1);
  });
  $('ob-back').style.display = _obStep > 1 ? 'inline-flex' : 'none';
  $('ob-next').textContent = _obStep === OB_TOTAL_STEPS ? 'Finalizar ✓' : 'Próximo →';
  if (_obStep === 3) obLoadModes();
}

async function obLoadModes() {
  try {
    const raw = await window.pywebview.api.get_modes();
    const modes = JSON.parse(raw);
    const list = $('ob-modes-list');
    if (!modes.length) {
      list.innerHTML = '<div class="actions-empty">Nenhum modo. Você pode criar depois.</div>';
      return;
    }
    list.innerHTML = modes.map(m => {
      const hk = m.hotkey ? formatHotkey(m.hotkey) : '';
      return `<div class="ob-mode-row">
        <span class="ob-mode-icon">${iconFor(m)}</span>
        <span class="ob-mode-name">${m.name}</span>
        ${hk ? `<span class="ob-mode-hotkey">${hk}</span>` : ''}
      </div>`;
    }).join('');
  } catch {}
}

async function obFinish() {
  // Salva a key se o user preencheu na tela 2
  const apiKey = ($('ob-api-key')?.value || '').trim();
  if (apiKey) {
    try {
      await window.pywebview.api.save_config(JSON.stringify({ voice_ai: { api_key: apiKey } }));
      showToast('🎙️ Voz IA conectada!', 'success');
    } catch {}
  }
  try { await window.pywebview.api.mark_onboarding_done(); } catch {}
  obHide();
}

function bindOnboarding() {
  $('ob-next').addEventListener('click', () => {
    if (_obStep === OB_TOTAL_STEPS) obFinish();
    else obGoTo(_obStep + 1);
  });
  $('ob-back').addEventListener('click', () => obGoTo(_obStep - 1));
  $('ob-skip').addEventListener('click', obFinish);
  $('ob-open-groq').addEventListener('click', async () => {
    try {
      await window.pywebview.api.open_external_url('https://console.groq.com/keys');
      showToast('🌐 Abrindo Groq no navegador...', 'success');
    } catch {}
  });
}

async function maybeShowOnboarding() {
  try {
    const r = JSON.parse(await window.pywebview.api.get_onboarding_status());
    if (!r.done) obShow();
  } catch {}
}

async function applySystemTheme() {
  try {
    const r = JSON.parse(await window.pywebview.api.get_system_theme());
    document.body.dataset.theme = r.theme || 'dark';
  } catch {
    document.body.dataset.theme = 'dark';
  }
}

async function init() {
  startClock();
  bindEvents();
  await applySystemTheme();
  await loadActionTypes();
  await loadModes();
  await updateStatus();
  setInterval(updateStatus, 2000);
  setInterval(pollLogs, 1500); // Atualiza o log a cada 1.5s
  setInterval(pollVoiceIndicator, 700);  // Chip de estado da voz no header
  pollVoiceIndicator();  // primeira leitura imediata

  // Mostra wizard se for a primeira vez (depois de tudo carregado)
  maybeShowOnboarding();
  // Tooltip: indica se ainda falta configurar — mas o botão NUNCA fica disabled
  // (validação acontece no clique, com toast claro).
  try {
    const cfg = JSON.parse(await window.pywebview.api.get_config());
    const hasKey = !!(cfg.voice_ai?.api_key);
    $('btn-voice').title = hasKey
      ? 'Clique para falar com JARVIS'
      : 'Configure a API Key em Configurações → Voz IA';
  } catch {}
}

window.addEventListener('pywebviewready', init);
if (document.readyState !== 'loading') waitForAPI(init);
