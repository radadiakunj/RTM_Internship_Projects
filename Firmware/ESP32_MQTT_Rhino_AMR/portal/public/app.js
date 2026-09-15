/* Reeman Calling Portal frontend */

const $ = (id) => document.getElementById(id);

/** Draft values per profile so switching profiles does not wipe edits */
const drafts = {
  amr: {},
  embedded: {},
  cloud: {},
  local: {},
  custom: {},
};

let lastBrokers = {};
let suppressFormOverwrite = false;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(friendlyError(data.error || res.statusText || 'Request failed'));
  }
  return data;
}

/** Turn MQTT jargon into clear UI text */
function friendlyError(msg) {
  const raw = String(msg || '');
  const m = raw.toLowerCase();
  if (m.includes('connack timeout') || m.includes('connect timeout')) {
    return 'Broker connection timeout — no reply from Host:Port. For Local Embedded use 127.0.0.1 and port 2883. For Cloud use mqtt.rmbot.cn:1883.';
  }
  if (m.includes('econnrefused')) {
    return 'Connection refused — nothing is listening on that Host:Port. Start the portal (embedded broker) or check Mosquitto.';
  }
  if (m.includes('enotfound') || m.includes('getaddrinfo')) {
    return 'Host not found — check the Host spelling / DNS / internet.';
  }
  if (m.includes('eacces')) {
    return 'Permission denied for that port — try another Port (e.g. 2883).';
  }
  if (m.includes('connack')) {
    return raw.replace(/connack/gi, 'broker handshake');
  }
  return raw;
}

function setBadge(el, text, cls) {
  el.textContent = text;
  el.className = `badge ${cls}`;
}

function readForm() {
  return {
    profile: $('profile').value,
    host: $('host').value.trim(),
    port: Number($('port').value) || 1883,
    clientId: $('clientId').value.trim(),
    hostname: $('hostname').value.trim(),
    token: $('token').value.trim(),
    encryptKey: $('encryptKey').value.trim(),
    mqttUsername: $('mqttUsername').value.trim(),
    mqttPassword: $('mqttPassword').value,
  };
}

function writeForm(values, { onlyBroker = false } = {}) {
  if (values.profile) $('profile').value = values.profile;
  if (values.host != null) $('host').value = values.host;
  if (values.port != null) $('port').value = values.port;
  if (!onlyBroker) {
    if (values.clientId != null) $('clientId').value = values.clientId;
    if (values.hostname != null) $('hostname').value = values.hostname;
    if (values.token != null) $('token').value = values.token;
    if (values.encryptKey != null) $('encryptKey').value = values.encryptKey;
    if (values.mqttUsername != null) $('mqttUsername').value = values.mqttUsername;
    if (values.mqttPassword != null) $('mqttPassword').value = values.mqttPassword;
  }
}

function saveDraft() {
  const f = readForm();
  drafts[f.profile] = { ...drafts[f.profile], ...f };
}

function profileDefaults(profile, brokers) {
  const b = brokers && brokers[profile];
  if (profile === 'amr') {
    return {
      host: (b && b.host) || '192.168.5.75',
      port: (b && b.port) || 1883,
      mqttUsername: (b && b.username) || '',
      mqttPassword: (b && b.password) || '',
    };
  }
  if (profile === 'embedded') {
    return {
      host: (b && b.host) || '127.0.0.1',
      port: (b && b.port) || 2883,
    };
  }
  if (profile === 'cloud') {
    return {
      host: (b && b.host) || 'mqtt.rmbot.cn',
      port: (b && b.port) || 1883,
    };
  }
  if (profile === 'local') {
    return {
      host: (b && b.host) || '127.0.0.1',
      port: (b && b.port) || 1883,
    };
  }
  return { host: '192.168.5.75', port: 1883 };
}

/** Status badges only — never overwrite editable fields */
function updateStatusBadges(state) {
  const c = state.connection || {};
  const err = c.error ? friendlyError(c.error) : null;

  if (c.connected) {
    setBadge($('connBadge'), `Connected · ${c.host}:${c.port}`, 'on');
    $('connError').hidden = true;
  } else {
    setBadge($('connBadge'), err ? `Error · ${shortBadge(err)}` : 'Disconnected', err ? 'warn' : 'off');
    if (err) {
      $('connError').hidden = false;
      $('connError').textContent = err;
    }
  }

  const hb = state.heartbeat || {};
  if (hb.enabled) {
    setBadge($('hbBadge'), hb.warning ? 'Heartbeat WARN' : 'Heartbeat on', hb.warning ? 'warn' : 'on');
  } else {
    setBadge($('hbBadge'), 'Heartbeat off', 'off');
  }
  const last = hb.lastPhoneHeartbeatAt
    ? new Date(hb.lastPhoneHeartbeatAt).toLocaleTimeString()
    : '—';
  $('hbInfo').textContent = `Enabled: ${!!hb.enabled} | Last phone HB: ${last}${hb.warning ? ' | ' + hb.warning : ''}`;
}

function shortBadge(err) {
  if (/timeout/i.test(err)) return 'Broker connection timeout';
  if (/refused/i.test(err)) return 'Connection refused';
  if (/not found/i.test(err)) return 'Host not found';
  return err.length > 48 ? `${err.slice(0, 48)}…` : err;
}

function loadFormFromState(state, { force = false } = {}) {
  if (suppressFormOverwrite && !force) return;
  const c = state.connection || {};
  const brokers = state.brokers || lastBrokers;
  lastBrokers = brokers;

  const profileSelect = $('profile');
  const profile =
    c.profile && profileSelect.querySelector(`option[value="${c.profile}"]`)
      ? c.profile
      : profileSelect.value || 'embedded';

  const defaults = profileDefaults(profile, brokers);
  const draft = drafts[profile] || {};

  writeForm({
    profile,
    host: draft.host || c.host || defaults.host,
    port: draft.port || c.port || defaults.port,
    clientId: draft.clientId != null ? draft.clientId : c.clientId || '',
    hostname: draft.hostname || c.hostname || '',
    token: draft.token != null ? draft.token : c.token || '',
    encryptKey: draft.encryptKey != null ? draft.encryptKey : c.encryptKey || '',
    mqttUsername: draft.mqttUsername != null ? draft.mqttUsername : defaults.mqttUsername || '',
    mqttPassword: draft.mqttPassword != null ? draft.mqttPassword : defaults.mqttPassword || '',
  });
}

function renderRobot(status) {
  if (!status) return;
  $('stBattery').textContent = status.level != null ? `${status.level}%` : '—';
  $('stEstop').textContent =
    status.emergencyButton === 0 ? 'PRESSED' : status.emergencyButton === 1 ? 'Released' : '—';
  $('stCharge').textContent = status.chargeStateLabel || status.chargeState || '—';
  $('stNav').textContent = status.isNavigating == null ? '—' : String(status.isNavigating);
  $('stTaskExec').textContent = status.taskExecuting == null ? '—' : String(status.taskExecuting);
  const ct = status.currentTask;
  $('stCurrent').textContent = ct
    ? `${ct.taskModeLabel || ct.taskMode || ''} → ${ct.targetPoint || '—'}`
    : 'none';
  $('robotRaw').textContent = JSON.stringify(status, null, 2);
}

function renderPoints(model, data) {
  if (!data) return;
  $('pointsOut').textContent = JSON.stringify(
    {
      model,
      code: data.code,
      codeLabel: data.codeLabel,
      decryptError: data.decryptError || null,
      bodyDecrypted: data.bodyDecrypted,
      rawBody: data.body,
    },
    null,
    2
  );
}

function renderTask(resp) {
  if (!resp) return;
  $('taskOut').textContent = JSON.stringify(resp, null, 2);
}

function formatRoute(record) {
  const parts = [];
  if (record.workflow === 'ReverseJob') {
    if (record.drop) parts.push(record.drop);
    if (record.pick) parts.push(record.pick);
    if (record.home) parts.push(record.home);
  } else {
    if (record.home) parts.push(record.home);
    if (record.pick) parts.push(record.pick);
    if (record.drop) parts.push(record.drop);
  }
  return parts.length ? parts.join(' → ') : '—';
}

function statusBadge(status) {
  const s = String(status || 'unknown').toLowerCase();
  return `<span class="mission-status status-${escapeHtml(s)}">${escapeHtml(s)}</span>`;
}

function renderMissionStats(stats) {
  if (!stats) return;
  $('msTotal').textContent = stats.total != null ? String(stats.total) : '0';
  if ($('msActive')) {
    $('msActive').textContent = stats.activeCount != null ? String(stats.activeCount) : '0';
  }
  $('msLatestId').textContent = stats.latestMissionId != null ? `#${stats.latestMissionId}` : '—';
  $('msLatestResult').textContent = stats.latestStatus || '—';
}

function renderMissionTable(records) {
  const body = $('missionRows');
  if (!records || records.length === 0) {
    body.innerHTML =
      '<tr><td colspan="9" class="muted">No missions yet — press A or B on the ESP32 (portal must be running).</td></tr>';
    return;
  }
  body.innerHTML = records
    .map((row) => {
      const when = row.updatedAt || row.receivedAt
        ? new Date(row.updatedAt || row.receivedAt).toLocaleString()
        : '—';
      const bat = row.batteryPct != null ? `${row.batteryPct}%` : '—';
      const status = row.status || row.result || '—';
      return `<tr>
        <td>${escapeHtml(String(row.missionId))}</td>
        <td>${escapeHtml(when)}</td>
        <td>${escapeHtml(row.key || row.action || '—')}</td>
        <td>${statusBadge(status)}</td>
        <td>${escapeHtml(row.phase || '—')}</td>
        <td>${escapeHtml(row.workflow || '—')}</td>
        <td>${escapeHtml(formatRoute(row))}</td>
        <td>${escapeHtml(bat)}</td>
        <td>${escapeHtml(row.notes || '')}</td>
      </tr>`;
    })
    .join('');
}

async function loadMissions() {
  const data = await api('/api/missions?limit=50');
  renderMissionStats(data.stats);
  renderMissionTable(data.records);
}

function prependLog(entry) {
  const log = $('log');
  const div = document.createElement('div');
  div.className = 'log-entry';
  const time = new Date(entry.ts).toLocaleTimeString();
  const dir = entry.direction || 'info';
  let payload =
    entry.error != null
      ? { error: friendlyError(entry.error), ...(entry.payload || {}) }
      : entry.payload;
  if (payload && typeof payload === 'object' && payload.error) {
    payload = { ...payload, error: friendlyError(payload.error) };
  }
  div.innerHTML = `
    <span>${time}</span>
    <span class="dir ${dir}">${dir}</span>
    <span class="topic">${escapeHtml(entry.topic || entry.kind || '')}</span>
    <span class="payload">${escapeHtml(typeof payload === 'string' ? payload : JSON.stringify(payload))}</span>
  `;
  log.prepend(div);
  while (log.children.length > 300) log.removeChild(log.lastChild);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function isPrivateHost(host) {
  const h = String(host || '').trim();
  return (
    /^192\.168\./.test(h) ||
    /^10\./.test(h) ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(h) ||
    h === '127.0.0.1' ||
    h === 'localhost'
  );
}

function onProfileChange() {
  saveDraft();
  const profile = $('profile').value;
  const defaults = profileDefaults(profile, lastBrokers);
  const draft = drafts[profile] || {};

  let host = draft.host || defaults.host;
  let port = draft.port || defaults.port;

  // Cloud Calling must never keep a leftover AMR LAN IP in Host
  if (profile === 'cloud') {
    host = (lastBrokers.cloud && lastBrokers.cloud.host) || 'mqtt.rmbot.cn';
    port = (lastBrokers.cloud && lastBrokers.cloud.port) || 1883;
    drafts.cloud = { ...(drafts.cloud || {}), host, port };
  }

  writeForm({
    profile,
    host,
    port,
    clientId: draft.clientId || $('clientId').value,
    hostname: draft.hostname || $('hostname').value,
    token: draft.token != null ? draft.token : $('token').value,
    encryptKey: draft.encryptKey != null ? draft.encryptKey : $('encryptKey').value,
    mqttUsername:
      profile === 'cloud'
        ? ''
        : draft.mqttUsername != null
          ? draft.mqttUsername
          : defaults.mqttUsername || $('mqttUsername').value,
    mqttPassword:
      profile === 'cloud'
        ? ''
        : draft.mqttPassword != null
          ? draft.mqttPassword
          : defaults.mqttPassword || $('mqttPassword').value,
  });
  $('connHint').textContent =
    profile === 'amr'
      ? 'AMR Local MQTT: Host=Nav IP, Port=1883. Often needs broker user/pass (not Calling token). Official Calling uses Cloud profile instead.'
      : profile === 'embedded'
        ? 'Local Embedded: Host 127.0.0.1 + built-in broker port. Offline mock only.'
        : profile === 'cloud'
          ? 'Cloud Calling: Host MUST be mqtt.rmbot.cn (not AMR IP 192.168.x.x). Leave MQTT Username/Password empty. Needs internet.'
          : profile === 'local'
            ? 'Local Floor Mosquitto on your PC/LAN.'
            : 'Custom: type any Host, Port, auth, hostname, token, key.';
}

async function init() {
  const state = await api('/api/state');
  lastBrokers = state.brokers || {};
  loadFormFromState(state, { force: true });
  if (!state.connection?.connected) {
    $('profile').value = lastBrokers.amr ? 'amr' : lastBrokers.embedded ? 'embedded' : 'cloud';
    onProfileChange();
    if (state.connection?.hostname) $('hostname').value = state.connection.hostname;
    if (state.connection?.token) $('token').value = state.connection.token;
    if (state.connection?.encryptKey != null) $('encryptKey').value = state.connection.encryptKey;
  }
  updateStatusBadges(state);
  await loadTopicGuide();
  if (state.robotStatus) renderRobot(state.robotStatus);
  if (state.taskResponse) renderTask(state.taskResponse);
  await loadMissions();
  (state.log || []).slice().reverse().forEach(prependLog);
  if (state.pairing) {
    $('pairStatus').textContent = JSON.stringify(state.pairing, null, 2);
  }

  // While typing, do not let live events overwrite the form
  ['host', 'port', 'clientId', 'hostname', 'token', 'encryptKey', 'mqttUsername', 'mqttPassword'].forEach((id) => {
    $(id).addEventListener('input', () => {
      suppressFormOverwrite = true;
      saveDraft();
    });
    $(id).addEventListener('focus', () => {
      suppressFormOverwrite = true;
    });
  });

  const es = new EventSource('/api/events');
  es.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    switch (msg.type) {
      case 'hello':
        lastBrokers = (msg.state && msg.state.brokers) || lastBrokers;
        updateStatusBadges(msg.state);
        break;
      case 'connection':
        updateStatusBadges({ connection: msg.connection, heartbeat: { enabled: false } });
        api('/api/state').then((s) => {
          lastBrokers = s.brokers || lastBrokers;
          updateStatusBadges(s);
        });
        break;
      case 'heartbeat':
        api('/api/state').then(updateStatusBadges);
        break;
      case 'robotStatus':
        renderRobot(msg.status);
        break;
      case 'points':
        renderPoints(msg.model, msg.data);
        break;
      case 'taskResponse':
        renderTask(msg.response);
        break;
      case 'log':
        prependLog(msg.entry);
        break;
      case 'logCleared':
        $('log').innerHTML = '';
        break;
      case 'missionRecord':
        renderMissionStats(msg.stats);
        loadMissions().catch(() => {});
        break;
      case 'pairing':
        $('pairStatus').textContent = JSON.stringify(msg.packet, null, 2);
        if (msg.connection) {
          if (msg.connection.hostname) $('hostname').value = msg.connection.hostname;
          if (msg.connection.token) $('token').value = msg.connection.token;
          if (msg.connection.encryptKey) $('encryptKey').value = msg.connection.encryptKey;
          saveDraft();
        }
        break;
      default:
        break;
    }
  };
}

$('profile').addEventListener('change', onProfileChange);

$('btnConnect').addEventListener('click', async () => {
  try {
    $('connError').hidden = true;
    saveDraft();
    const f = readForm();
    if (!f.host) throw new Error('Host is required');
    if (!f.port) throw new Error('Port is required');

    // Guard: Cloud profile + AMR LAN IP is the common mistake
    if (f.profile === 'cloud' && isPrivateHost(f.host)) {
      f.host = 'mqtt.rmbot.cn';
      f.port = 1883;
      f.mqttUsername = '';
      f.mqttPassword = '';
      writeForm(f);
      $('connHint').textContent =
        'Corrected Host to mqtt.rmbot.cn for Cloud Calling. Do not use AMR Nav IP here.';
    }

    setBadge($('connBadge'), `Connecting · ${f.host}:${f.port}`, 'warn');
    const state = await api('/api/connect', {
      method: 'POST',
      body: JSON.stringify({
        profile: f.profile,
        host: f.host,
        port: f.port,
        clientId: f.clientId || undefined,
        hostname: f.hostname,
        token: f.token,
        encryptKey: f.encryptKey,
        mqttUsername: f.mqttUsername,
        mqttPassword: f.mqttPassword,
      }),
    });
    suppressFormOverwrite = false;
    updateStatusBadges(state);
    await loadTopicGuide();
  } catch (err) {
    const msg = friendlyError(err.message);
    $('connError').hidden = false;
    $('connError').textContent = msg;
    setBadge($('connBadge'), `Error · ${shortBadge(msg)}`, 'warn');
  }
});

$('btnDisconnect').addEventListener('click', async () => {
  const state = await api('/api/disconnect', { method: 'POST', body: '{}' });
  updateStatusBadges({ ...state, heartbeat: { enabled: false } });
  setBadge($('hbBadge'), 'Heartbeat off', 'off');
});

$('btnSaveCreds').addEventListener('click', async () => {
  saveDraft();
  const f = readForm();
  await api('/api/credentials', {
    method: 'POST',
    body: JSON.stringify({
      hostname: f.hostname,
      token: f.token,
      encryptKey: f.encryptKey,
    }),
  });
  // Also remember host/port for this profile in config via connect payload shape — credentials endpoint is hostname/token/key only
  alert('Hostname, Token, and encryptKey saved to config.json');
});

$('btnHbStart').addEventListener('click', async () => {
  try {
    await api('/api/heartbeat/start', { method: 'POST', body: '{}' });
    const state = await api('/api/state');
    updateStatusBadges(state);
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnHbStop').addEventListener('click', async () => {
  await api('/api/heartbeat/stop', { method: 'POST', body: '{}' });
  const state = await api('/api/state');
  updateStatusBadges(state);
});

$('btnPairStart').addEventListener('click', async () => {
  try {
    const r = await api('/api/pairing/start', { method: 'POST', body: '{}' });
    $('pairStatus').textContent = JSON.stringify(r, null, 2);
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnPairStop').addEventListener('click', async () => {
  const r = await api('/api/pairing/stop', { method: 'POST', body: '{}' });
  $('pairStatus').textContent = JSON.stringify(r, null, 2);
});

document.querySelectorAll('[data-points]').forEach((btn) => {
  btn.addEventListener('click', async () => {
    try {
      await api('/api/points/request', {
        method: 'POST',
        body: JSON.stringify({ model: btn.getAttribute('data-points') }),
      });
    } catch (err) {
      alert(friendlyError(err.message));
    }
  });
});

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.add('hidden'));
    $(`tab-${tab.dataset.tab}`).classList.remove('hidden');
  });
});

$('btnTaskNormal').addEventListener('click', async () => {
  try {
    await api('/api/task', {
      method: 'POST',
      body: JSON.stringify({
        model: 'normal_model',
        map: $('normalMap').value.trim() || null,
        point: $('normalPoint').value.trim(),
      }),
    });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnTaskRoute').addEventListener('click', async () => {
  try {
    await api('/api/task', {
      method: 'POST',
      body: JSON.stringify({ model: 'route_model', routeName: $('routeName').value.trim() }),
    });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnTaskQr').addEventListener('click', async () => {
  try {
    await api('/api/task', {
      method: 'POST',
      body: JSON.stringify({
        model: 'qrcode_model',
        pairs: [
          {
            first: { map: null, point: $('qrFirst').value.trim() },
            second: { map: null, point: $('qrSecond').value.trim() },
          },
        ],
      }),
    });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnTaskCharge').addEventListener('click', async () => {
  try {
    await api('/api/task', { method: 'POST', body: JSON.stringify({ model: 'charge_model' }) });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnTaskReturn').addEventListener('click', async () => {
  try {
    await api('/api/task', { method: 'POST', body: JSON.stringify({ model: 'return_model' }) });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnSubscribe').addEventListener('click', async () => {
  try {
    await api('/api/subscribe', {
      method: 'POST',
      body: JSON.stringify({ topic: $('subTopic').value.trim() }),
    });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnPublish').addEventListener('click', async () => {
  try {
    await api('/api/publish', {
      method: 'POST',
      body: JSON.stringify({
        topic: $('pubTopic').value.trim(),
        payload: $('pubPayload').value,
      }),
    });
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

$('btnClearLog').addEventListener('click', async () => {
  await api('/api/log/clear', { method: 'POST', body: '{}' });
  $('log').innerHTML = '';
});

$('btnRefreshMissions').addEventListener('click', async () => {
  try {
    await loadMissions();
  } catch (err) {
    alert(friendlyError(err.message));
  }
});

async function httpCheck(path) {
  $('httpOut').hidden = false;
  $('httpOut').textContent = 'Loading…';
  try {
    const r = await fetch(`/api/rhino/${path}`);
    const data = await r.json();
    $('httpOut').textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    $('httpOut').textContent = err.message;
  }
}

$('btnHttpHostname').addEventListener('click', () => httpCheck('reeman/hostname'));
$('btnHttpPose').addEventListener('click', () => httpCheck('reeman/pose'));
$('btnHttpBase').addEventListener('click', () => httpCheck('reeman/base_encode'));
$('btnHttpNav').addEventListener('click', () => httpCheck('reeman/nav_status'));

async function loadTopicGuide() {
  try {
    const data = await api('/api/topics');
    $('topicGuide').textContent = data.flows
      .map(
        (f) =>
          `${f.name}\n  PUB  ${f.publish.topic}\n       ${JSON.stringify(f.publish.payload)}\n  EXP  ${f.expect.topic}\n       ${f.expect.payloadHint}\n`
      )
      .join('\n');

    const hostName = data.hostname;
    const presets = [
      {
        label: 'Fill: heartbeat',
        topic: data.publish.heartbeat,
        payload: JSON.stringify({ token: $('token').value || '<token>' }, null, 2),
      },
      {
        label: 'Fill: points normal',
        topic: data.publish.pointsRequest.normal_model,
        payload: JSON.stringify({ token: $('token').value || '<token>' }, null, 2),
      },
      {
        label: 'Fill: task charge',
        topic: data.publish.task.charge_model,
        payload: JSON.stringify({ token: $('token').value || '<token>', body: null }, null, 2),
      },
      {
        label: 'Sub: robot #',
        sub: `reeman/calling/robot/${hostName}/v2/#`,
      },
    ];
    const box = $('topicPresets');
    box.innerHTML = '';
    for (const p of presets) {
      const btn = document.createElement('button');
      btn.textContent = p.label;
      btn.addEventListener('click', () => {
        if (p.sub) $('subTopic').value = p.sub;
        if (p.topic) $('pubTopic').value = p.topic;
        if (p.payload) $('pubPayload').value = p.payload;
      });
      box.appendChild(btn);
    }
  } catch (err) {
    $('topicGuide').textContent = `Could not load topic guide: ${err.message}`;
  }
}

init().catch((err) => {
  $('connError').hidden = false;
  $('connError').textContent = `Failed to load portal state: ${friendlyError(err.message)}`;
});
