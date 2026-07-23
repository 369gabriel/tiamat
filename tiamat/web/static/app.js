/* ═══════════════════════════════════════════════════════════════════════════
   Tiamat Web — SPA Application Logic
   ═══════════════════════════════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────────────────────────────

const state = {
  features: [],
  connected: false,
  account: 'Connecting...',
  selectedFeature: null,
  viewingDetail: false,
  profileData: null,
};

// ── WebSocket ──────────────────────────────────────────────────────────────

let ws = null;
let wsReconnectTimer = null;

function connectWebSocket() {
  if (ws) try { ws.close(); } catch {}
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('[WS] Connected');
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  };

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === 'connection') {
        state.connected = data.connected;
        state.account = data.account;
        updateConnectionUI();
      }
    } catch {}
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected, reconnecting...');
    wsReconnectTimer = setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => ws && ws.close();
}

// ── Connection UI ──────────────────────────────────────────────────────────

function updateConnectionUI() {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  dot.className = 'status-dot' + (state.connected ? ' connected' : '');
  text.textContent = state.connected ? state.account : 'League Client not detected';
}

// ── HTTP helpers ───────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  return res.json();
}

function apiGet(path) { return api('GET', path); }
function apiPost(path, body) { return api('POST', path, body); }

// ── Toast notifications ────────────────────────────────────────────────────

function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
}

// ── Modal ──────────────────────────────────────────────────────────────────

function openModal(html) {
  document.getElementById('modal-body').innerHTML = html;
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('modal-content').classList.remove('background-picker-modal');
}

// ── Build sidebar ──────────────────────────────────────────────────────────

function buildSidebar(features) {
  const list = document.getElementById('feature-list');
  list.innerHTML = '';

  let category = null;
  for (const f of features) {
    if (f.category !== category) {
      category = f.category;
      const cat = document.createElement('div');
      cat.className = 'category-label';
      cat.textContent = category;
      list.appendChild(cat);
    }

    const item = document.createElement('div');
    item.className = 'feature-item';
    item.dataset.number = f.number;

    const numSpan = document.createElement('span');
    numSpan.className = 'feature-number';
    numSpan.textContent = f.number;

    const titleSpan = document.createElement('span');
    titleSpan.className = 'feature-title';
    titleSpan.textContent = f.title;

    const kindTag = document.createElement('span');
    kindTag.className = `feature-kind-tag ${f.kind}`;
    kindTag.textContent = f.kind === 'toggle' ? 'TOGGLE'
      : f.kind === 'configure' ? 'CONFIG'
      : 'RUN';

    const stateSpan = document.createElement('span');
    stateSpan.className = 'feature-state-indicator';
    stateSpan.id = `fs-${f.number}`;
    stateSpan.textContent = '';

    item.appendChild(numSpan);
    item.appendChild(titleSpan);
    item.appendChild(kindTag);
    item.appendChild(stateSpan);

    item.addEventListener('click', () => selectFeature(f.number));
    list.appendChild(item);
  }
}

// ── Select feature ─────────────────────────────────────────────────────────

function selectFeature(number) {
  state.selectedFeature = number;
  state.viewingDetail = true;
  document.querySelectorAll('.feature-item').forEach(el => el.classList.remove('active'));
  const item = document.querySelector(`.feature-item[data-number="${number}"]`);
  if (item) item.classList.add('active');
  document.getElementById('profile-panel').classList.add('hidden');
  document.getElementById('detail-panel').classList.remove('hidden');
  showDetail(number);
}

// ── Show profile (back to home) ────────────────────────────────────────────

function showProfile() {
  state.viewingDetail = false;
  state.selectedFeature = null;
  document.querySelectorAll('.feature-item').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-panel').classList.add('hidden');
  document.getElementById('profile-panel').classList.remove('hidden');
}

// ── Load profile data ──────────────────────────────────────────────────────

async function loadProfile() {
  const data = await apiGet('/api/profile');
  if (data.error) return;
  state.profileData = data;
  renderProfile(data);
}

function renderProfile(data) {
  // Icon
  const iconId = data.profileIconId || 0;
  document.getElementById('profile-icon').src =
    `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/${iconId}.jpg`;
  document.getElementById('profile-icon').alt = `${data.gameName || 'Summoner'} profile icon`;
  document.getElementById('profile-icon').onerror = function() {
    this.onerror = null;
    this.src = `https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/${iconId}.png`;
  };

  // Current profile splash art
  const backdrop = document.getElementById('profile-backdrop');
  if (data.backgroundUrl) {
    backdrop.style.backgroundImage = `url("${data.backgroundUrl}")`;
  } else {
    backdrop.style.removeProperty('background-image');
  }
  renderProfileRegalia(data.regalia || {});

  // Name & tag
  document.getElementById('profile-name').textContent = data.gameName || '--';
  document.getElementById('profile-riotid').textContent = `#${data.tagLine || '---'}`;
  const profileStats = data.profileStats || {};
  const titleEl = document.getElementById('profile-title');
  titleEl.textContent = profileStats.title || '';
  titleEl.style.display = profileStats.title ? '' : 'none';

  // Region
  const regionEl = document.getElementById('profile-region');
  if (data.region) {
    regionEl.textContent = data.region;
    regionEl.style.display = '';
  } else {
    regionEl.style.display = 'none';
  }

  // Summoner level
  const level = data.summonerLevel || 0;
  document.getElementById('profile-level').textContent = level;

  // Ranked
  const rankedContainer = document.getElementById('profile-ranked');
  rankedContainer.innerHTML = '';
  const queues = data.ranked || [];
  const queueOrder = ['Ranked Solo/Duo', 'Ranked Flex', 'TFT'];
  for (const label of queueOrder) {
    const queue = queues.find(q => q.queue === label) || { queue: label, tier: 'UNRANKED' };
    rankedContainer.appendChild(createRankedCard(queue));
  }
  rankedContainer.appendChild(createProfileStatCard(
    'Honor',
    profileStats.honorLevel ? `Level ${profileStats.honorLevel}` : '--',
    '◇',
  ));
  rankedContainer.appendChild(createProfileStatCard(
    'Mastery score',
    profileStats.masteryScore || '--',
    '✦',
  ));
}

function renderProfileRegalia(regalia) {
  const identityCard = document.querySelector('.profile-identity-card');
  const iconButton = document.querySelector('.profile-icon-button');
  const crest = document.getElementById('profile-crest');
  const banner = document.getElementById('profile-banner-skin');

  identityCard.classList.remove('has-banner');
  iconButton.classList.remove('has-regalia');

  setProfileAsset(crest, regalia.crestUrl, () => {
    iconButton.classList.add('has-regalia');
  });
  setProfileAsset(banner, regalia.bannerUrl, () => {
    identityCard.classList.add('has-banner');
  });
}

function setProfileAsset(image, url, onReady) {
  if (!url) {
    image.removeAttribute('src');
    image.style.display = 'none';
    return;
  }
  image.style.display = '';
  image.onload = onReady;
  image.onerror = () => {
    image.style.display = 'none';
  };
  if (image.getAttribute('src') !== url) image.src = url;
  else if (image.complete && image.naturalWidth > 0) onReady();
}

function createRankedCard(q) {
  const card = document.createElement('div');
  card.className = 'ranked-card';

  const isRanked = q.tier && q.tier !== 'UNRANKED' && q.tier !== '';
  const emblemFrame = document.createElement('span');
  emblemFrame.className = 'ranked-card-emblem-frame';
  if (isRanked) {
    const emblem = document.createElement('img');
    emblem.className = 'ranked-card-emblem';
    emblem.src = `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/ranked-emblem/emblem-${q.tier.toLowerCase()}.png`;
    emblem.alt = `${q.tier} ranked emblem`;
    emblemFrame.appendChild(emblem);
  } else {
    const emblem = document.createElement('span');
    emblem.className = 'ranked-card-emblem ranked-card-emblem-empty';
    emblem.textContent = '—';
    emblemFrame.appendChild(emblem);
  }
  card.appendChild(emblemFrame);

  const copy = document.createElement('div');
  copy.className = 'ranked-card-copy';

  const header = document.createElement('div');
  header.className = 'ranked-card-header';
  header.textContent = q.queue;

  const tier = document.createElement('div');
  if (isRanked) {
    tier.className = 'ranked-card-tier';
    tier.textContent = `${q.tier} ${q.rank}`;
  } else {
    tier.className = 'ranked-card-tier unranked';
    tier.textContent = 'UNRANKED';
  }

  copy.appendChild(header);
  copy.appendChild(tier);

  if (isRanked) {
    const wr = document.createElement('div');
    wr.className = 'ranked-card-wr';
    const total = (q.wins || 0) + (q.losses || 0);
    const pct = total > 0 ? Math.round((q.wins / total) * 100) : 0;

    // Mini series (promo)
    if (q.miniSeries) {
      const seriesProgress = typeof q.miniSeries === 'string'
        ? q.miniSeries
        : (q.miniSeries.progress || '');
      const progress = seriesProgress.split('').map(c =>
        c === 'W' ? '<span class="green">✓</span>'
          : c === 'L' ? '<span class="red">✗</span>'
          : '<span style="color:var(--text-muted)">—</span>'
      ).join(' ');
      wr.innerHTML = `${q.leaguePoints} LP · ${pct}% WR · ${progress}`;
    } else {
      wr.textContent = `${q.leaguePoints} LP · ${pct}% WR`;
    }
    copy.appendChild(wr);
  }

  card.appendChild(copy);

  return card;
}

function createProfileStatCard(label, value, symbol) {
  const card = document.createElement('div');
  card.className = 'ranked-card profile-stat-card';

  const icon = document.createElement('span');
  icon.className = 'profile-stat-symbol';
  icon.textContent = symbol;

  const copy = document.createElement('div');
  copy.className = 'ranked-card-copy';

  const header = document.createElement('div');
  header.className = 'ranked-card-header';
  header.textContent = label;

  const statValue = document.createElement('div');
  statValue.className = 'ranked-card-tier';
  statValue.textContent = value;

  copy.appendChild(header);
  copy.appendChild(statValue);
  card.appendChild(icon);
  card.appendChild(copy);
  return card;
}

// ── Show detail panel ──────────────────────────────────────────────────────

function showDetail(number) {
  const f = state.features.find(x => x.number === number);
  if (!f) return;

  document.getElementById('detail-title').textContent = f.title.toUpperCase();
  document.getElementById('detail-description').textContent = f.description;

  const badge = document.getElementById('detail-state');
  const st = getFeatureState(number);
  badge.textContent = st || 'READY';
  badge.className = 'state-badge' + (st && st !== 'OFF' && st !== '--' ? ' on' : '');

  // Build action buttons
  const actions = document.getElementById('detail-actions');
  actions.innerHTML = '';

  if (f.kind === 'toggle') {
    const btn = document.createElement('button');
    btn.className = 'primary';
    btn.textContent = st === 'ON' || st === 'LIVE' ? 'Turn OFF' : 'Turn ON';
    btn.onclick = () => toggleFeature(f.number);
    actions.appendChild(btn);
  }

  if (f.kind === 'configure') {
    if (f.number === 2) {
      const btn = document.createElement('button');
      btn.className = 'primary';
      btn.textContent = st !== 'OFF' ? 'Change Champion' : 'Configure';
      btn.onclick = () => openInstalockModal();
      actions.appendChild(btn);
      if (st !== 'OFF') {
        const toggle = document.createElement('button');
        toggle.textContent = 'Disable';
        toggle.onclick = () => apiPost('/api/toggle/instalock').then(refresh);
        actions.appendChild(toggle);
      }
    } else if (f.number === 3) {
      const btn = document.createElement('button');
      btn.className = 'primary';
      btn.textContent = st !== 'OFF' ? 'Change Champion' : 'Configure';
      btn.onclick = () => openAutoBanModal();
      actions.appendChild(btn);
      if (st !== 'OFF') {
        const toggle = document.createElement('button');
        toggle.textContent = 'Disable';
        toggle.onclick = () => apiPost('/api/toggle/autoban').then(refresh);
        actions.appendChild(toggle);
      }
    } else if (f.number === 4) {
      const btn = document.createElement('button');
      btn.className = 'primary';
      btn.textContent = st !== 'OFF' ? 'Reconfigure' : 'Configure';
      btn.onclick = () => openRagequeueModal();
      actions.appendChild(btn);
      if (st !== 'OFF') {
        const toggle = document.createElement('button');
        toggle.textContent = 'Disable';
        toggle.onclick = () => apiPost('/api/toggle/ragequeue').then(refresh);
        actions.appendChild(toggle);
      }
    } else if (f.number === 5) openIconModal(actions, 'profile');
    else if (f.number === 6) openIconModal(actions, 'client');
    else if (f.number === 7) openBackgroundModal(actions);
    else if (f.number === 8) openRiotIdModal(actions);
    else if (f.number === 9) openBadgesModal(actions);
    else if (f.number === 10) openStatusModal(actions);
  }

  if (f.kind === 'action') {
    if (f.number === 11) {
      const btn = document.createElement('button');
      btn.className = 'primary';
      btn.textContent = '🔍 Reveal Lobby';
      btn.onclick = () => runAction('/api/action/lobby-reveal');
      actions.appendChild(btn);
    } else if (f.number === 12) {
      const btn = document.createElement('button');
      btn.className = 'danger';
      btn.textContent = '⚠️ Dodge';
      btn.onclick = () => confirmAction('Dodge', 'Are you sure you want to dodge champion select?', '/api/action/dodge');
      actions.appendChild(btn);
    } else if (f.number === 13) {
      const btn = document.createElement('button');
      btn.className = 'danger';
      btn.textContent = '🔄 Restart UX';
      btn.onclick = () => confirmAction('Restart Client UX', 'Are you sure you want to restart the client UX?', '/api/action/restart-ux');
      actions.appendChild(btn);
    } else if (f.number === 15) {
      const btn = document.createElement('button');
      btn.className = 'danger';
      btn.textContent = '🗑️ Remove All Friends';
      btn.onclick = () => confirmAction('Remove All Friends', 'This will permanently remove ALL friends from your account. Are you sure?', '/api/action/remove-friends');
      actions.appendChild(btn);
    }
  }
}

// ── Get feature state ──────────────────────────────────────────────────────

function getFeatureState(number) {
  const f = state.features.find(x => x.number === number);
  return f ? f.state : '';
}

function updateFeatureStates() {
  for (const f of state.features) {
    const el = document.getElementById(`fs-${f.number}`);
    if (el) {
      const st = f.state || '';
      el.textContent = st;
      el.className = 'feature-state-indicator';
      if (st && st !== 'OFF' && st !== '--') {
        if (st === 'LIVE') el.classList.add('live');
        else if (st === 'OFFLINE') el.classList.add('offline');
        else el.classList.add('on');
      }
    }
  }
  if (state.selectedFeature) showDetail(state.selectedFeature);
}

// ── Toggle features ────────────────────────────────────────────────────────

async function toggleFeature(number) {
  let path;
  if (number === 1) path = '/api/toggle/auto-accept';
  else if (number === 14) path = '/api/toggle/chat';
  else return;
  const res = await apiPost(path);
  if (res.state !== undefined) {
    const f = state.features.find(x => x.number === number);
    if (f) f.state = res.state;
    updateFeatureStates();
  } else if (res.error) {
    toast(res.error, 'error');
  }
}

// ── Run action ─────────────────────────────────────────────────────────────

async function runAction(path) {
  const res = await apiPost(path);
  if (res.success !== undefined) {
    toast(res.success ? 'Done!' : 'Failed', res.success ? 'success' : 'error');
    await refresh();
  } else if (res.error) {
    toast(res.error, 'error');
  }
}

function confirmAction(title, message, path) {
  openModal(`
    <h3>${title}</h3>
    <p>${message}</p>
    <div class="form-actions">
      <button onclick="closeModal()">Cancel</button>
      <button class="danger" onclick="closeModal(); runAction('${path}')">Confirm</button>
    </div>
  `);
}

// ── Modal: Instalock ───────────────────────────────────────────────────────

async function openInstalockModal() {
  openModal('<h3>Instalock Champion</h3><p>Loading champion list...</p>');
  const data = await apiGet('/api/champions');
  if (data.error) { document.querySelector('#modal-body p').textContent = data.error; return; }
  const champs = data.champions;
  renderChampionSearch('Instalock Champion', champs, true, async (champion) => {
    const res = await apiPost('/api/configure/instalock', { champion });
    if (res.state !== undefined) {
      const f = state.features.find(x => x.number === 2);
      if (f) f.state = res.state;
      closeModal();
      updateFeatureStates();
      toast(`Instalock set to ${champion}`, 'success');
    } else if (res.error) { toast(res.error, 'error'); }
  });
}

async function openAutoBanModal() {
  openModal('<h3>AutoBan Champion</h3><p>Loading champion list...</p>');
  const data = await apiGet('/api/champions');
  if (data.error) { document.querySelector('#modal-body p').textContent = data.error; return; }
  renderChampionSearch('AutoBan Champion', data.champions, false, async (champion) => {
    const res = await apiPost('/api/configure/autoban', { champion });
    if (res.state !== undefined) {
      const f = state.features.find(x => x.number === 3);
      if (f) f.state = res.state;
      closeModal();
      updateFeatureStates();
      toast(`AutoBan set to ${champion}`, 'success');
    } else if (res.error) { toast(res.error, 'error'); }
  });
}

function renderChampionSearch(title, champions, showRandom, onSelect) {
  let html = `<h3>${title}</h3>
    <div class="search-input-wrapper">
      <span class="search-icon">🔍</span>
      <input type="text" id="champ-search" placeholder="Search champions..." oninput="filterChampions()" autofocus>
    </div>
    <div class="champion-grid" id="champ-grid">`;
  const all = showRandom ? ['Random', ...champions] : champions;
  for (const c of all) {
    html += `<div class="champion-option" data-name="${c.toLowerCase()}" onclick="selectChampion(this, '${c}')">${c}</div>`;
  }
  html += `</div>`;
  document.getElementById('modal-body').innerHTML = html;
  window._champCallback = onSelect;
}

function filterChampions() {
  const q = document.getElementById('champ-search').value.toLowerCase();
  document.querySelectorAll('.champion-option').forEach(el => {
    el.style.display = el.dataset.name.includes(q) ? '' : 'none';
  });
}

function selectChampion(el, name) {
  document.querySelectorAll('.champion-option').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  if (window._champCallback) window._champCallback(name);
}

// ── Modal: Ragequeue ───────────────────────────────────────────────────────

let rageQueues = [], ragePositions = [];

async function openRagequeueModal() {
  openModal('<h3>Configure Ragequeue</h3><p>Loading...</p>');
  const data = await apiGet('/api/ragequeue/queues');
  rageQueues = data.queues;
  ragePositions = data.positions;

  let html = `<h3>Configure Ragequeue</h3><p>Select lobby type and preferred positions.</p>`;

  html += `<div class="form-group"><label>Lobby Type</label><select id="rq-queue">`;
  for (const q of rageQueues) {
    html += `<option value="${q.id}">${q.name}</option>`;
  }
  html += `</select></div>`;

  html += `<div class="form-group"><label>Primary Role</label><select id="rq-pos1">`;
  html += `<option value="">-- None --</option>`;
  for (const p of ragePositions) {
    html += `<option value="${p.id}">${p.name}</option>`;
  }
  html += `</select></div>`;

  html += `<div class="form-group"><label>Secondary Role</label><select id="rq-pos2">`;
  html += `<option value="">-- None --</option>`;
  for (const p of ragePositions) {
    html += `<option value="${p.id}">${p.name}</option>`;
  }
  html += `</select></div>`;

  html += `<div class="form-actions">
    <button onclick="closeModal()">Cancel</button>
    <button class="primary" onclick="saveRagequeue()">Save & Enable</button>
  </div>`;

  document.getElementById('modal-body').innerHTML = html;
}

async function saveRagequeue() {
  const queueId = parseInt(document.getElementById('rq-queue').value);
  const pos1 = document.getElementById('rq-pos1').value || null;
  const pos2 = document.getElementById('rq-pos2').value || null;
  const res = await apiPost('/api/configure/ragequeue', { queue_id: queueId, first_position: pos1, second_position: pos2 });
  if (res.state !== undefined) {
    const f = state.features.find(x => x.number === 4);
    if (f) f.state = res.state;
    closeModal();
    updateFeatureStates();
    toast('Ragequeue configured!', 'success');
  } else if (res.error) {
    toast(res.error, 'error');
  }
}

// ── Modal: Profile Icon / Client Icon ──────────────────────────────────────

function openIconModal(actions, type) {
  const title = type === 'profile' ? 'Profile Icon' : 'Client Icon';
  const endpoint = type === 'profile' ? '/api/configure/profile-icon' : '/api/configure/client-icon';

  const btn = document.createElement('button');
  btn.className = 'primary';
  btn.textContent = `Change ${title}`;
  btn.onclick = () => showIconPicker(title, endpoint);
  actions.appendChild(btn);
}

function openProfileIconPicker() {
  showIconPicker('Profile Icon', '/api/configure/profile-icon');
}

function showIconPicker(title, endpoint) {
  openModal(`
    <h3>${title}</h3>
    <p>Enter the icon ID number.</p>
    <div class="form-group">
      <label>Icon ID</label>
      <input type="number" id="icon-id" min="1" placeholder="e.g. 28" autofocus>
    </div>
    <div class="form-actions">
      <button onclick="closeModal()">Cancel</button>
      <button class="primary" onclick="saveIcon('${endpoint}')">Apply</button>
    </div>
  `);
}

async function saveIcon(endpoint) {
  const iconId = parseInt(document.getElementById('icon-id').value);
  if (!iconId || iconId < 1) { toast('Enter a valid icon ID', 'error'); return; }
  const res = await apiPost(endpoint, { icon_id: iconId });
  if (res.success) {
    closeModal();
    toast('Icon changed!', 'success');
    if (endpoint === '/api/configure/profile-icon') await loadProfile();
  }
  else if (res.error) toast(res.error, 'error');
}

// ── Modal: Background Search ───────────────────────────────────────────────

let skinSearchTimer = null;
let selectedBackgroundSkinId = null;
let selectedBackgroundSkinName = '';

function openBackgroundModal(actions) {
  const btn = document.createElement('button');
  btn.className = 'primary';
  btn.textContent = 'Search Background';
  btn.onclick = openProfileBackgroundPicker;
  actions.appendChild(btn);
}

function openProfileBackgroundPicker() {
  selectedBackgroundSkinId = state.profileData?.backgroundSkinId || null;
  selectedBackgroundSkinName = '';
  openModal(`
    <div class="background-picker">
      <div class="background-picker-header">
        <div>
          <span class="background-picker-eyebrow">Profile customization</span>
          <h3>Set profile background</h3>
        </div>
      </div>

      <div class="background-picker-controls">
        <div class="search-input-wrapper background-picker-search">
          <span class="search-icon">⌕</span>
          <input type="text" id="bg-search" placeholder="Search champion or skin..." oninput="debounceSkinSearch()" autofocus>
        </div>
      </div>

      <div id="skin-results" class="background-skin-results">
        <div class="skin-gallery-message">Loading your collection...</div>
      </div>

      <div class="background-picker-footer">
        <button type="button" class="background-restore-button" onclick="restoreProfileBackground()">Restore default</button>
        <div>
          <button type="button" onclick="closeModal()">Cancel</button>
          <button type="button" id="save-background" class="primary" onclick="saveSelectedBackground()" disabled>Save background</button>
        </div>
      </div>
    </div>
  `);
  document.getElementById('modal-content').classList.add('background-picker-modal');
  doSkinSearch();
}

function debounceSkinSearch() {
  clearTimeout(skinSearchTimer);
  skinSearchTimer = setTimeout(doSkinSearch, 300);
}

async function doSkinSearch() {
  const q = document.getElementById('bg-search').value.trim();
  const collection = 'all';
  const sort = 'name';
  const container = document.getElementById('skin-results');
  container.innerHTML = '<div class="skin-gallery-message">Loading skins...</div>';
  const data = await apiGet(
    `/api/skins?query=${encodeURIComponent(q)}&collection=${encodeURIComponent(collection)}&sort=${encodeURIComponent(sort)}`
  );
  if (data.error) {
    container.innerHTML = `<div class="skin-gallery-message error">${escapeHtml(data.error)}</div>`;
    return;
  }
  if (!data.skins.length) {
    container.innerHTML = '<div class="skin-gallery-message">No skins found for these filters.</div>';
    return;
  }

  const groups = [];
  if (collection === 'owned' && sort !== 'name') {
    const byYear = new Map();
    for (const skin of data.skins) {
      const year = skin.acquiredYear || 'Earlier';
      if (!byYear.has(year)) byYear.set(year, []);
      byYear.get(year).push(skin);
    }
    for (const [year, skins] of byYear) {
      groups.push({ title: year === 'Earlier' ? 'Previously acquired' : `Acquired in ${year}`, skins });
    }
  } else {
    groups.push({
      title: collection === 'owned' ? 'My collection' : `All skins · ${data.total}`,
      skins: data.skins,
    });
  }

  container.innerHTML = groups.map(group => `
    <section class="skin-gallery-group">
      <h4>${escapeHtml(group.title)}</h4>
      <div class="skin-gallery-grid">
        ${group.skins.map(renderSkinGalleryCard).join('')}
      </div>
    </section>
  `).join('');
  updateSelectedSkinCard();
}

function renderSkinGalleryCard(skin) {
  const imageUrl = skin.splashUrl || skin.tileUrl || '';
  const image = imageUrl
    ? `<img src="${imageUrl}" alt="" loading="lazy">`
    : '<span class="skin-gallery-placeholder"></span>';
  const skinLabel = skin.name === 'Default' ? skin.champion : skin.name;
  return `
    <button class="skin-gallery-card" type="button"
      data-skin-id="${skin.id}"
      data-skin-name="${encodeURIComponent(skinLabel)}"
      onclick="selectBackgroundSkin(this)">
      <span class="skin-gallery-art">${image}<span class="skin-selected-check">✓</span></span>
      <strong>${escapeHtml(skinLabel)}</strong>
      <small>${escapeHtml(skin.champion)}</small>
    </button>
  `;
}

function selectBackgroundSkin(card) {
  selectedBackgroundSkinId = parseInt(card.dataset.skinId);
  selectedBackgroundSkinName = decodeURIComponent(card.dataset.skinName);
  updateSelectedSkinCard();
  const saveButton = document.getElementById('save-background');
  saveButton.disabled = false;
  saveButton.textContent = 'Save background';
}

function updateSelectedSkinCard() {
  document.querySelectorAll('.skin-gallery-card').forEach(card => {
    card.classList.toggle('selected', parseInt(card.dataset.skinId) === selectedBackgroundSkinId);
  });
}

async function saveSelectedBackground() {
  if (selectedBackgroundSkinId === null) return;
  await applySkin(selectedBackgroundSkinId, selectedBackgroundSkinName || 'Selected skin');
}

function restoreProfileBackground() {
  selectedBackgroundSkinId = 0;
  selectedBackgroundSkinName = 'Default';
  updateSelectedSkinCard();
  const saveButton = document.getElementById('save-background');
  saveButton.disabled = false;
  saveButton.textContent = 'Restore default';
}

async function applySkin(skinId, skinName) {
  const res = await apiPost('/api/configure/background', { skin_id: parseInt(skinId) });
  if (res.success) {
    if (res.backgroundUrl) {
      document.getElementById('profile-backdrop').style.backgroundImage = `url("${res.backgroundUrl}")`;
    } else {
      document.getElementById('profile-backdrop').style.removeProperty('background-image');
    }
    closeModal();
    toast(`Background set to ${skinName}`, 'success');
    await loadProfile();
  }
  else if (res.error) toast(res.error, 'error');
}

// ── Modal: Riot ID ─────────────────────────────────────────────────────────

function openRiotIdModal(actions) {
  const btn = document.createElement('button');
  btn.className = 'primary';
  btn.textContent = 'Change Riot ID';
  btn.onclick = () => {
    openModal(`
      <h3>Riot ID</h3>
      <p>Change your displayed name and tag.</p>
      <div class="form-group"><label>Game Name</label><input type="text" id="ri-id" placeholder="Game Name" maxlength="16" autofocus></div>
      <div class="form-group"><label>Tag</label><input type="text" id="ri-tag" placeholder="TAG" maxlength="5" style="max-width:120px;"></div>
      <div class="form-actions">
        <button onclick="closeModal()">Cancel</button>
        <button class="primary" onclick="saveRiotId()">Save</button>
      </div>
    `);
  };
  actions.appendChild(btn);
}

async function saveRiotId() {
  const name = document.getElementById('ri-id').value.trim();
  const tag = document.getElementById('ri-tag').value.trim();
  if (!name || !tag) { toast('Fill in both fields', 'error'); return; }
  const res = await apiPost('/api/configure/riotid', { name, tag });
  if (res.success) { closeModal(); toast(`Riot ID changed to ${res.riotid}`, 'success'); }
  else if (res.error) toast(res.error, 'error');
}

// ── Modal: Status ──────────────────────────────────────────────────────────

function openStatusModal(actions) {
  const btn = document.createElement('button');
  btn.className = 'primary';
  btn.textContent = 'Change Status';
  btn.onclick = () => {
    openModal(`
      <h3>Status Message</h3>
      <p>Set your online status message.</p>
      <div class="form-group">
        <label>Message</label>
        <textarea id="st-msg" placeholder="Enter your status message..." rows="3" autofocus></textarea>
      </div>
      <div class="form-actions">
        <button onclick="closeModal()">Cancel</button>
        <button class="primary" onclick="saveStatus()">Save</button>
      </div>
    `);
  };
  actions.appendChild(btn);
}

async function saveStatus() {
  const status = document.getElementById('st-msg').value;
  const res = await apiPost('/api/configure/status', { status });
  if (res.success) { closeModal(); toast('Status updated!', 'success'); }
  else if (res.error) toast(res.error, 'error');
}

// ── Modal: Badges ──────────────────────────────────────────────────────────

function openBadgesModal(actions) {
  const btn = document.createElement('button');
  btn.className = 'primary';
  btn.textContent = 'Change Badges';
  btn.onclick = () => {
    openModal(`
      <h3>Profile Badges</h3>
      <p>Choose a badge mode.</p>
      <div class="badge-mode-group">
        <button class="badge-mode-btn selected" data-mode="empty" onclick="selectBadgeMode(this)">Empty</button>
        <button class="badge-mode-btn" data-mode="copy" onclick="selectBadgeMode(this)">Copy First</button>
        <button class="badge-mode-btn" data-mode="glitched" onclick="selectBadgeMode(this)">Glitched</button>
      </div>
      <div id="badge-glitched-field" class="form-group" style="display:none;margin-top:10px;">
        <label>Glitched ID (0-5)</label>
        <input type="number" id="badge-glitched-id" min="0" max="5" value="0">
      </div>
      <div class="form-actions">
        <button onclick="closeModal()">Cancel</button>
        <button class="primary" onclick="saveBadges()">Apply</button>
      </div>
    `);
  };
  actions.appendChild(btn);
}

function selectBadgeMode(el) {
  document.querySelectorAll('.badge-mode-btn').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  const field = document.getElementById('badge-glitched-field');
  field.style.display = el.dataset.mode === 'glitched' ? 'block' : 'none';
}

async function saveBadges() {
  const mode = document.querySelector('.badge-mode-btn.selected')?.dataset.mode || 'empty';
  const glitchedId = mode === 'glitched' ? parseInt(document.getElementById('badge-glitched-id').value) : null;
  const res = await apiPost('/api/configure/badges', { mode, glitched_id: glitchedId });
  if (res.success) { closeModal(); toast('Badges updated!', 'success'); }
  else if (res.error) toast(res.error, 'error');
}

// ── Refresh ────────────────────────────────────────────────────────────────

async function refresh() {
  const [statusData, featuresData] = await Promise.all([
    apiGet('/api/status'),
    apiGet('/api/features'),
  ]);

  state.connected = statusData.connected;
  state.account = statusData.account;
  updateConnectionUI();

  state.features = featuresData;

  // Merge in current states from status endpoint
  if (statusData.features) {
    for (const sf of statusData.features) {
      const f = state.features.find(x => x.number === sf.number);
      if (f) f.state = sf.state;
    }
  }

  // Also add feature 14 and 15 state
  const f14 = state.features.find(x => x.number === 14);
  if (f14 && !f14.state) f14.state = statusData.features?.find(x => x.number === 14)?.state || '--';

  const f15 = state.features.find(x => x.number === 15);
  if (f15) f15.state = '';

  buildSidebar(state.features);
  updateFeatureStates();

  // Select first feature if none selected
  if (!state.selectedFeature && state.features.length > 0) {
    // Don't auto-select, show profile instead
  } else if (state.viewingDetail && state.selectedFeature) {
    selectFeature(state.selectedFeature);
  }

  // Activity log
  const log = document.getElementById('activity-log');
  log.innerHTML = '';
  if (statusData.activity) {
    for (const entry of statusData.activity.reverse()) {
      const el = document.createElement('div');
      el.className = 'activity-entry';
      el.innerHTML = `
        <span class="activity-time">${entry.timestamp}</span>
        <span class="activity-level ${entry.level}">${entry.level.padEnd(7)}</span>
        <span class="activity-message">${escapeHtml(entry.message)}</span>
      `;
      log.appendChild(el);
    }
    log.scrollTop = log.scrollHeight;
  }

  // Load profile (always, to keep up to date)
  loadProfile();
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

// ── Init ───────────────────────────────────────────────────────────────────

connectWebSocket();

// Wire back button
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('detail-back')?.addEventListener('click', showProfile);
});

refresh();
setInterval(refresh, 5000);
