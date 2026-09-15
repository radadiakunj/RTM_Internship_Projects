'use strict';

const path = require('path');
const fs = require('fs');
const express = require('express');
const cors = require('cors');
const mqtt = require('mqtt');
const { encrypt, tryDecryptBody } = require('./lib/aes');
const {
  POINT_MODELS,
  TASK_MODELS,
  topics,
  tokenPayload,
  taskPayload,
  normalTaskPlain,
  routeTaskPlain,
  qrcodeTaskPlain,
  describeCode,
  describeChargeState,
  TASK_MODE_LABELS,
} = require('./lib/calling');
const { PairingListener } = require('./lib/pairing');
const { startEmbeddedBroker } = require('./lib/embeddedBroker');
const { expectedFlows } = require('./lib/topicGuide');
const { MissionStore } = require('./lib/missions');
const { startMissionListener } = require('./lib/missionListener');

const CONFIG_PATH = path.join(__dirname, 'config.json');
const EXAMPLE_PATH = path.join(__dirname, 'config.example.json');

function loadConfig() {
  const src = fs.existsSync(CONFIG_PATH) ? CONFIG_PATH : EXAMPLE_PATH;
  return JSON.parse(fs.readFileSync(src, 'utf8'));
}

let config = loadConfig();
const pairing = new PairingListener();

/** @type {import('mqtt').MqttClient | null} */
let client = null;
let connection = {
  connected: false,
  profile: null,
  host: null,
  port: null,
  clientId: null,
  hostname: config.hostname || '',
  token: config.token || '',
  encryptKey: config.encryptKey || '',
  error: null,
  connectedAt: null,
};

let heartbeatTimer = null;
let heartbeatEnabled = false;
let lastPhoneHeartbeatAt = null;
let lastRobotHeartbeat = null;
let lastPoints = {};
let lastTaskResponse = null;
const messageLog = [];
const MAX_LOG = 500;
const sseClients = new Set();

const missionStore = new MissionStore({
  storagePath: path.join(__dirname, 'data', 'missions.json'),
  maxRecords: (config.missionHistory && config.missionHistory.maxRecords) || 500,
});
/** @type {ReturnType<typeof startMissionListener> | null} */
let missionListener = null;

function pushLog(entry) {
  const row = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, ts: Date.now(), ...entry };
  messageLog.unshift(row);
  if (messageLog.length > MAX_LOG) messageLog.length = MAX_LOG;
  broadcast({ type: 'log', entry: row });
  return row;
}

function broadcast(event) {
  const data = `data: ${JSON.stringify(event)}\n\n`;
  for (const res of sseClients) {
    try {
      res.write(data);
    } catch (_) {
      sseClients.delete(res);
    }
  }
}

function getState() {
  return {
    connection: {
      ...connection,
      // do not strip secrets from local API — UI needs them; served only on localhost
    },
    heartbeat: {
      enabled: heartbeatEnabled,
      intervalMs: config.heartbeatIntervalMs || 4000,
      lastPhoneHeartbeatAt,
      warning:
        heartbeatEnabled && lastPhoneHeartbeatAt && Date.now() - lastPhoneHeartbeatAt > 10000
          ? 'No phone heartbeat sent in >10s — robot may ignore commands'
          : null,
    },
    robotStatus: lastRobotHeartbeat,
    points: lastPoints,
    taskResponse: lastTaskResponse,
    pairing: pairing.status(),
    brokers: config.brokers,
    navIp: config.navIp,
    pointModels: POINT_MODELS,
    taskModels: TASK_MODELS,
    chargeLabels: describeChargeState,
    taskModeLabels: TASK_MODE_LABELS,
    missions: missionStore.getStats(),
  };
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  heartbeatEnabled = false;
}

function publishPhoneHeartbeat() {
  if (!client || !client.connected) return;
  const t = topics(connection.hostname);
  const payload = tokenPayload(connection.token);
  client.publish(t.phone.heartbeat, payload, { qos: 0 }, (err) => {
    if (err) {
      pushLog({ direction: 'error', topic: t.phone.heartbeat, payload, error: err.message });
      return;
    }
    lastPhoneHeartbeatAt = Date.now();
    pushLog({ direction: 'pub', topic: t.phone.heartbeat, payload: JSON.parse(payload), kind: 'heartbeat' });
    broadcast({ type: 'heartbeat', at: lastPhoneHeartbeatAt });
  });
}

function startHeartbeat() {
  stopHeartbeat();
  if (!client || !client.connected) {
    throw new Error('Not connected to MQTT');
  }
  heartbeatEnabled = true;
  publishPhoneHeartbeat();
  heartbeatTimer = setInterval(publishPhoneHeartbeat, config.heartbeatIntervalMs || 4000);
}

function handleIncoming(topic, payloadBuf) {
  const text = payloadBuf.toString('utf8');
  let parsed = text;
  try {
    parsed = JSON.parse(text);
  } catch {
    /* keep string */
  }

  const t = topics(connection.hostname);
  let kind = 'message';
  let enriched = parsed;

  if (topic === t.robot.heartbeat) {
    kind = 'robot_heartbeat';
    lastRobotHeartbeat = typeof parsed === 'object' ? { ...parsed, receivedAt: Date.now() } : { raw: parsed, receivedAt: Date.now() };
    if (lastRobotHeartbeat.chargeState != null) {
      lastRobotHeartbeat.chargeStateLabel = describeChargeState(lastRobotHeartbeat.chargeState);
    }
    if (lastRobotHeartbeat.currentTask && lastRobotHeartbeat.currentTask.taskMode != null) {
      lastRobotHeartbeat.currentTask.taskModeLabel =
        TASK_MODE_LABELS[lastRobotHeartbeat.currentTask.taskMode] || String(lastRobotHeartbeat.currentTask.taskMode);
    }
    broadcast({ type: 'robotStatus', status: lastRobotHeartbeat });
  } else if (topic === t.robot.taskResponse) {
    kind = 'task_response';
    const code = parsed && parsed.code;
    const decryptResult = tryDecryptBody(parsed && parsed.body, code, connection.encryptKey);
    lastTaskResponse = {
      ...parsed,
      codeLabel: describeCode(code),
      bodyDecrypted: decryptResult.decrypted,
      decryptError: decryptResult.error,
      receivedAt: Date.now(),
    };
    enriched = lastTaskResponse;
    broadcast({ type: 'taskResponse', response: lastTaskResponse });
  } else {
    for (const model of POINT_MODELS) {
      if (topic === t.robot.pointsResponse(model)) {
        kind = `points_response:${model}`;
        const code = parsed && parsed.code;
        const decryptResult = tryDecryptBody(parsed && parsed.body, code, connection.encryptKey);
        lastPoints[model] = {
          ...parsed,
          model,
          codeLabel: describeCode(code),
          bodyDecrypted: decryptResult.decrypted,
          decryptError: decryptResult.error,
          receivedAt: Date.now(),
        };
        enriched = lastPoints[model];
        broadcast({ type: 'points', model, data: lastPoints[model] });
        break;
      }
    }
  }

  pushLog({ direction: 'sub', topic, payload: enriched, kind });
}

function disconnectMqtt() {
  stopHeartbeat();
  if (client) {
    const old = client;
    client = null;
    try {
      // Keep a noop error listener so late connack timeouts cannot crash the process
      old.removeAllListeners();
      old.on('error', () => {});
      old.end(true);
    } catch (_) {
      /* ignore */
    }
  }
  connection.connected = false;
  connection.connectedAt = null;
  connection.error = null;
  broadcast({ type: 'connection', connection });
}

function friendlyMqttError(msg) {
  const raw = String(msg || '');
  const m = raw.toLowerCase();
  if (m.includes('bad username') || m.includes('not authorized') || m.includes('not authorised')) {
    if (String(connection && connection.profile) === 'cloud' || /rmbot\.cn/i.test(raw)) {
      return 'Reeman cloud MQTT rejected this client (Not authorized). Official phone app auth is not fully documented; token/key alone are not MQTT broker login. Use HTTP to AMR for control, or ask Reeman/your mentor for cloud MQTT credentials / SDK.';
    }
    return 'MQTT auth failed (bad username/password). For AMR local broker, use broker Username/Password from AMR MQTT settings (NOT the Calling token). For Cloud Calling leave user/pass empty only if the cloud allows anonymous (currently it may reject).';
  }
  if (m.includes('connack timeout') || m.includes('connect timeout')) {
    return 'Broker connection timeout — no reply from Host:Port. For Local Embedded use 127.0.0.1:2883. For Cloud use mqtt.rmbot.cn:1883.';
  }
  if (m.includes('econnrefused')) {
    return 'Connection refused — nothing is listening on that Host:Port.';
  }
  if (m.includes('enotfound') || m.includes('getaddrinfo')) {
    return 'Host not found — check Host spelling / DNS / internet.';
  }
  if (m.includes('eacces')) {
    return 'Permission denied for that port — try Port 2883.';
  }
  if (m.includes('connack')) {
    return raw.replace(/connack/gi, 'broker handshake');
  }
  return raw;
}

function connectMqtt({ profile, host, port, clientId, hostname, token, encryptKey, mqttUsername, mqttPassword }) {
  disconnectMqtt();

  const broker = profile && config.brokers[profile] ? config.brokers[profile] : null;
  // Always prefer values typed in the UI when provided
  let finalHost = (host && String(host).trim()) || (broker && broker.host) || '127.0.0.1';
  let finalPort = Number(port) > 0 ? Number(port) : Number((broker && broker.port) || 2883);
  // Cloud Calling must hit Reeman cloud, never the AMR Nav IP
  if (profile === 'cloud') {
    const privateIp =
      /^192\.168\./.test(finalHost) ||
      /^10\./.test(finalHost) ||
      /^172\.(1[6-9]|2\d|3[0-1])\./.test(finalHost) ||
      finalHost === '127.0.0.1';
    if (privateIp || !finalHost.includes('rmbot')) {
      finalHost = (config.brokers.cloud && config.brokers.cloud.host) || 'mqtt.rmbot.cn';
      finalPort = (config.brokers.cloud && config.brokers.cloud.port) || 1883;
    }
  }
  const finalClientId =
    (clientId && String(clientId).trim()) || `calling-portal-${Math.random().toString(16).slice(2, 10)}`;
  const user =
    mqttUsername != null && String(mqttUsername).length
      ? String(mqttUsername)
      : (broker && broker.username) || config.mqttUsername || '';
  const pass =
    mqttPassword != null
      ? String(mqttPassword)
      : (broker && broker.password) || config.mqttPassword || '';

  connection = {
    connected: false,
    profile: profile || 'custom',
    host: finalHost,
    port: finalPort,
    clientId: finalClientId,
    hostname: hostname || config.hostname,
    token: token != null ? token : config.token,
    encryptKey: encryptKey != null ? encryptKey : config.encryptKey,
    mqttUsername: user,
    mqttPassword: pass ? '***' : '',
    error: null,
    connectedAt: null,
  };

  // persist credentials for convenience
  config.hostname = connection.hostname;
  if (token) config.token = token;
  if (encryptKey != null) config.encryptKey = encryptKey;
  config.mqttUsername = user;
  config.mqttPassword = pass;
  if (profile && config.brokers[profile]) {
    config.brokers[profile].host = finalHost;
    config.brokers[profile].port = finalPort;
    config.brokers[profile].username = user;
    config.brokers[profile].password = pass;
  } else if (profile === 'custom') {
    config.brokers.custom = {
      label: 'Custom (type any Host/Port)',
      host: finalHost,
      port: finalPort,
      username: user,
      password: pass,
    };
  }

  const url = `mqtt://${finalHost}:${finalPort}`;
  pushLog({
    direction: 'info',
    topic: url,
    payload: {
      clientId: finalClientId,
      profile: connection.profile,
      auth: user ? `user=${user}` : 'anonymous',
    },
    kind: 'connecting',
  });

  return new Promise((resolve, reject) => {
    let settled = false;
    const mqttOpts = {
      clientId: finalClientId,
      clean: true,
      reconnectPeriod: 0,
      connectTimeout: 12000,
    };
    if (user) {
      mqttOpts.username = user;
      mqttOpts.password = pass;
    }
    const c = mqtt.connect(url, mqttOpts);
    client = c;

    const settleReject = (err) => {
      if (settled) return;
      settled = true;
      const nice = friendlyMqttError(err.message);
      connection.error = nice;
      connection.connected = false;
      pushLog({ direction: 'error', topic: url, payload: null, error: nice, kind: 'connect_error' });
      broadcast({ type: 'connection', connection });
      try {
        c.end(true);
      } catch (_) {
        /* ignore */
      }
      const wrapped = new Error(nice);
      reject(wrapped);
    };

    const settleResolve = (state) => {
      if (settled) return;
      settled = true;
      resolve(state);
    };

    // Always attached — mqtt emits unhandled 'error' crashes the Node process otherwise
    c.on('error', (err) => {
      if (!settled) {
        settleReject(err);
        return;
      }
      const nice = friendlyMqttError(err.message);
      connection.error = nice;
      connection.connected = false;
      pushLog({ direction: 'error', topic: url, error: nice });
      broadcast({ type: 'connection', connection });
    });

    c.on('close', () => {
      if (client !== c) return;
      connection.connected = false;
      stopHeartbeat();
      if (!settled) {
        settleReject(new Error('Broker connection timeout — connection closed before broker replied.'));
        return;
      }
      pushLog({ direction: 'info', topic: url, payload: { closed: true }, kind: 'disconnected' });
      broadcast({ type: 'connection', connection });
    });

    c.on('connect', () => {
      connection.connected = true;
      connection.connectedAt = Date.now();
      connection.error = null;
      pushLog({ direction: 'info', topic: url, payload: { connected: true }, kind: 'connected' });

      // Broad subscribe so you can see whatever the AMR returns
      const subs =
        connection.profile === 'cloud'
          ? topics(connection.hostname).subscribeAll
          : ['#', ...topics(connection.hostname).subscribeAll];

      c.subscribe(subs, { qos: 0 }, (err, granted) => {
        if (err) {
          pushLog({ direction: 'error', topic: String(subs), error: err.message, kind: 'subscribe_error' });
        } else {
          pushLog({ direction: 'info', topic: 'subscribe', payload: granted, kind: 'subscribed' });
        }
        broadcast({ type: 'connection', connection });
        settleResolve(getState());
      });
    });

    c.on('message', handleIncoming);
  });
}

function requireConnected(res) {
  if (!client || !client.connected) {
    res.status(400).json({ ok: false, error: 'Not connected to MQTT broker' });
    return false;
  }
  return true;
}

function publishRaw(topic, payloadObj) {
  const payload = typeof payloadObj === 'string' ? payloadObj : JSON.stringify(payloadObj);
  return new Promise((resolve, reject) => {
    client.publish(topic, payload, { qos: 0 }, (err) => {
      if (err) {
        pushLog({ direction: 'error', topic, payload: payloadObj, error: err.message });
        reject(err);
        return;
      }
      pushLog({ direction: 'pub', topic, payload: payloadObj });
      resolve({ topic, payload: payloadObj });
    });
  });
}

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/state', (_req, res) => {
  res.json({ ok: true, ...getState(), log: messageLog.slice(0, 100) });
});

app.get('/api/topics', (_req, res) => {
  const hostname = connection.hostname || config.hostname;
  const t = topics(hostname);
  res.json({
    ok: true,
    hostname,
    publish: {
      heartbeat: t.phone.heartbeat,
      pointsRequest: Object.fromEntries(POINT_MODELS.map((m) => [m, t.phone.pointsRequest(m)])),
      task: Object.fromEntries(TASK_MODELS.map((m) => [m, t.phone.task(m)])),
    },
    expectSubscribe: t.subscribeAll,
    flows: expectedFlows(hostname),
  });
});

app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  res.write(`data: ${JSON.stringify({ type: 'hello', state: getState() })}\n\n`);
  sseClients.add(res);
  req.on('close', () => sseClients.delete(res));
});

app.get('/api/log', (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 200, MAX_LOG);
  res.json({ ok: true, log: messageLog.slice(0, limit) });
});

app.get('/api/missions', (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 100, missionStore.maxRecords);
  res.json({ ok: true, ...missionStore.list(limit) });
});

app.get('/api/missions/stats', (_req, res) => {
  res.json({ ok: true, stats: missionStore.getStats() });
});

app.post('/api/log/clear', (_req, res) => {
  messageLog.length = 0;
  broadcast({ type: 'logCleared' });
  res.json({ ok: true });
});

app.post('/api/connect', async (req, res) => {
  try {
    const state = await connectMqtt(req.body || {});
    res.json({ ok: true, ...state });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message, connection });
  }
});

app.post('/api/disconnect', (_req, res) => {
  disconnectMqtt();
  res.json({ ok: true, connection });
});

app.post('/api/heartbeat/start', (_req, res) => {
  try {
    if (!requireConnected(res)) return;
    startHeartbeat();
    res.json({ ok: true, heartbeat: getState().heartbeat });
  } catch (err) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

app.post('/api/heartbeat/stop', (_req, res) => {
  stopHeartbeat();
  res.json({ ok: true, heartbeat: getState().heartbeat });
});

app.post('/api/points/request', async (req, res) => {
  try {
    if (!requireConnected(res)) return;
    const model = req.body.model;
    if (!POINT_MODELS.includes(model)) {
      return res.status(400).json({ ok: false, error: `Invalid model. Use: ${POINT_MODELS.join(', ')}` });
    }
    const topic = topics(connection.hostname).phone.pointsRequest(model);
    const payload = { token: connection.token };
    await publishRaw(topic, payload);
    res.json({ ok: true, topic, payload });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post('/api/task', async (req, res) => {
  try {
    if (!requireConnected(res)) return;
    const { model } = req.body;
    if (!TASK_MODELS.includes(model)) {
      return res.status(400).json({ ok: false, error: `Invalid model. Use: ${TASK_MODELS.join(', ')}` });
    }

    const topic = topics(connection.hostname).phone.task(model);
    let bodyField = null;
    let plaintext = null;

    if (model === 'charge_model' || model === 'return_model') {
      bodyField = null;
    } else {
      if (!connection.encryptKey) {
        return res.status(400).json({
          ok: false,
          error: 'encryptKey required for this task. Pair via UDP or paste the pairing key.',
        });
      }
      if (model === 'normal_model') {
        plaintext = normalTaskPlain({ map: req.body.map ?? null, point: req.body.point });
        if (!req.body.point) {
          return res.status(400).json({ ok: false, error: 'point is required for normal_model' });
        }
      } else if (model === 'route_model') {
        if (!req.body.routeName) {
          return res.status(400).json({ ok: false, error: 'routeName is required for route_model' });
        }
        plaintext = routeTaskPlain(req.body.routeName);
      } else if (model === 'qrcode_model') {
        if (!Array.isArray(req.body.pairs) || req.body.pairs.length === 0) {
          return res.status(400).json({ ok: false, error: 'pairs[] required for qrcode_model' });
        }
        plaintext = qrcodeTaskPlain(req.body.pairs);
      }
      bodyField = encrypt(plaintext, connection.encryptKey);
    }

    const payload = JSON.parse(taskPayload(connection.token, bodyField));
    await publishRaw(topic, payload);
    res.json({ ok: true, topic, payload, plaintext });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post('/api/publish', async (req, res) => {
  try {
    if (!requireConnected(res)) return;
    const { topic, payload } = req.body;
    if (!topic) return res.status(400).json({ ok: false, error: 'topic required' });
    let body = payload;
    if (typeof payload === 'string') {
      try {
        body = JSON.parse(payload);
      } catch {
        body = payload;
      }
    }
    await publishRaw(topic, body);
    res.json({ ok: true, topic, payload: body });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post('/api/subscribe', (req, res) => {
  if (!requireConnected(res)) return;
  const { topic } = req.body;
  if (!topic) return res.status(400).json({ ok: false, error: 'topic required' });
  client.subscribe(topic, { qos: 0 }, (err, granted) => {
    if (err) return res.status(500).json({ ok: false, error: err.message });
    pushLog({ direction: 'info', topic, payload: granted, kind: 'subscribed' });
    res.json({ ok: true, granted });
  });
});

app.get('/api/esp/credentials', (_req, res) => {
  res.json({
    ok: true,
    hostname: config.hostname || '',
    token: config.token || '',
    encryptKey: config.encryptKey || '',
  });
});

app.post('/api/credentials', (req, res) => {
  const { hostname, token, encryptKey } = req.body || {};
  if (hostname != null) {
    connection.hostname = hostname;
    config.hostname = hostname;
  }
  if (token != null) {
    connection.token = token;
    config.token = token;
  }
  if (encryptKey != null) {
    connection.encryptKey = encryptKey;
    config.encryptKey = encryptKey;
  }
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ...config }, null, 2));
  } catch (_) {
    /* non-fatal */
  }
  broadcast({ type: 'connection', connection });
  res.json({ ok: true, connection });
});

app.post('/api/pairing/start', async (req, res) => {
  try {
    const result = await pairing.start(req.body && req.body.iface);
    pushLog({ direction: 'info', topic: 'udp://239.0.0.1:7979', payload: result, kind: 'pairing_listen' });
    res.json({ ok: true, ...result, status: pairing.status() });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post('/api/pairing/stop', (_req, res) => {
  const result = pairing.stop();
  pushLog({ direction: 'info', topic: 'udp://239.0.0.1:7979', payload: { stopped: true }, kind: 'pairing_stop' });
  res.json({ ok: true, ...result });
});

app.get('/api/pairing/status', (_req, res) => {
  res.json({ ok: true, ...pairing.status() });
});

app.get(/^\/api\/rhino\/(.*)/, async (req, res) => {
  const navIp = config.navIp || '192.168.5.75';
  const sub = req.params[0] || 'reeman/hostname';
  const url = `http://${navIp}/${sub}`;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const r = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    const text = await r.text();
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      json = { raw: text };
    }
    res.json({ ok: r.ok, status: r.status, url, data: json });
  } catch (err) {
    res.status(502).json({ ok: false, error: err.message, url });
  }
});

pairing.onPacket((packet) => {
  pushLog({ direction: 'sub', topic: 'udp://239.0.0.1:7979', payload: packet, kind: 'pairing' });
  if (packet.type === 'pairing') {
    if (packet.hostname) {
      connection.hostname = packet.hostname;
      config.hostname = packet.hostname;
    }
    if (packet.token) {
      connection.token = packet.token;
      config.token = packet.token;
    }
    if (packet.key) {
      connection.encryptKey = packet.key;
      config.encryptKey = packet.key;
    }
    try {
      fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
    } catch (_) {
      /* ignore */
    }
    broadcast({ type: 'pairing', packet, connection });
  } else {
    broadcast({ type: 'pairing', packet });
  }
});

const PORT = Number(process.env.PORT || config.httpPort || 3080);

async function boot() {
  const emb = config.embeddedBroker || { enabled: true, host: '127.0.0.1', port: 1883, mockRobot: true };
  if (emb.enabled !== false) {
    const host = emb.host || '127.0.0.1';
    const preferred = Number(emb.port || 2883);
    const portsToTry = [...new Set([preferred, 2883, 1884, 1885, 2983])];
    let started = null;
    let lastErr = null;
    for (const port of portsToTry) {
      try {
        started = await startEmbeddedBroker({
          host,
          port,
          mockRobot: emb.mockRobot !== false,
          demo: {
            hostname: config.hostname,
            token: config.token || 'demo-token',
            encryptKey: config.encryptKey || '1234567890123456',
          },
        });
        break;
      } catch (err) {
        lastErr = err;
        if (err.code !== 'EADDRINUSE' && err.code !== 'EACCES') break;
        console.warn(`MQTT port ${port} unavailable (${err.code}), trying next…`);
      }
    }
    if (started) {
      console.log(`Embedded MQTT broker → ${started.url} (mock robot: ${started.mockRobot})`);
      config.brokers.embedded = {
        label: 'Local Embedded (no Wi-Fi)',
        host: started.host,
        port: started.port,
      };
    } else {
      console.warn(`Embedded broker failed to start: ${lastErr && lastErr.message}`);
    }
  }

  const httpPorts = [PORT, PORT + 1, PORT + 2, 3090];
  let listening = false;
  for (const httpPort of httpPorts) {
    try {
      await new Promise((resolve, reject) => {
        const server = app.listen(httpPort, () => {
          console.log(`Reeman Calling Portal → http://localhost:${httpPort}`);
          console.log('Offline: profile "Local Embedded" → Connect → Start heartbeat');
          console.log(`Robot hostname: ${config.hostname}`);
          listening = true;
          resolve();
        });
        server.on('error', reject);
      });
      break;
    } catch (err) {
      if (err.code !== 'EADDRINUSE') throw err;
      console.warn(`HTTP port ${httpPort} busy, trying next…`);
    }
  }
  if (!listening) {
    console.error('Could not bind an HTTP port. Close other portal instances and retry.');
    process.exit(1);
  }

  try {
    missionListener = startMissionListener(config, missionStore, (record) => {
      pushLog({
        direction: 'sub',
        topic: (config.missionHistory && config.missionHistory.topic) || 'callstation/mission/record',
        payload: record,
        kind: 'mission_record',
      });
      broadcast({ type: 'missionRecord', record, stats: missionStore.getStats() });
    });
  } catch (err) {
    console.warn(`Mission listener not started: ${err.message}`);
  }
}

boot().catch((err) => {
  console.error(err);
  process.exit(1);
});
