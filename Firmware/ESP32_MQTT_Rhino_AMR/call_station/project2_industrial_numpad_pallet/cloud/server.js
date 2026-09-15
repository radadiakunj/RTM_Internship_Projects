'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const cors = require('cors');
const { PalletStore } = require('./lib/pallets');
const { startPalletListener } = require('./lib/palletListener');

const root = __dirname;
const configPath = path.join(root, 'config.json');
const examplePath = path.join(root, 'config.example.json');

if (!fs.existsSync(configPath)) {
  fs.copyFileSync(examplePath, configPath);
  console.log('Created config.json from example — edit adminPassword and mqtt.host');
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const httpPort = Number(config.httpPort) || 3081;
const adminPassword = String(config.adminPassword || 'CHANGE_ME_ADMIN');

const store = new PalletStore({
  storagePath: path.join(root, 'data', 'pallets.json'),
  maxRecords: (config.palletHistory && config.palletHistory.maxRecords) || 1000,
});

/** @type {Map<string, { user: string, expires: number }>} */
const sessions = new Map();
const SESSION_TTL_MS = 8 * 60 * 60 * 1000;

function issueToken(user) {
  const token = crypto.randomBytes(24).toString('hex');
  sessions.set(token, { user, expires: Date.now() + SESSION_TTL_MS });
  return token;
}

function requireAdmin(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : req.query.token;
  const sess = token ? sessions.get(String(token)) : null;
  if (!sess || sess.expires < Date.now()) {
    return res.status(401).json({ ok: false, error: 'admin login required' });
  }
  req.adminUser = sess.user;
  return next();
}

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(root, 'public')));

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, project: 2, stats: store.getStats() });
});

app.get('/api/pallets', (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 100, 1000);
  res.json({ ok: true, ...store.list(limit) });
});

app.get('/api/pallets/export.csv', (_req, res) => {
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="warehouse_pallets.csv"');
  res.send(store.toCsv());
});

app.get('/api/pallets/export.xls', (_req, res) => {
  res.setHeader('Content-Type', 'application/vnd.ms-excel; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="warehouse_pallets.xls"');
  res.send(store.toExcelXml());
});

app.get('/api/pallets/export.json', (_req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="warehouse_pallets.json"');
  res.json({ ok: true, purpose: 'Warehouse placement validated', ...store.list(1000) });
});

app.post('/api/admin/login', (req, res) => {
  const password = req.body && req.body.password;
  if (String(password) !== adminPassword) {
    return res.status(403).json({ ok: false, error: 'bad password' });
  }
  if (adminPassword === 'CHANGE_ME_ADMIN') {
    console.warn('[security] Change adminPassword in config.json');
  }
  const token = issueToken('admin');
  res.json({ ok: true, token, expiresInMs: SESSION_TTL_MS });
});

app.post('/api/pallets/:palletId/void', requireAdmin, (req, res) => {
  const count = store.voidPallet(req.params.palletId, req.adminUser);
  if (!count) {
    return res.status(404).json({ ok: false, error: 'no active pallet found' });
  }
  res.json({ ok: true, voided: count, stats: store.getStats() });
});

const mqttClient = startPalletListener(config, store, () => {});

app.listen(httpPort, () => {
  console.log(`Project 2 pallet cloud http://127.0.0.1:${httpPort}`);
  console.log(`MQTT broker ${(config.mqtt && config.mqtt.host) || '127.0.0.1'}:${(config.mqtt && config.mqtt.port) || 1883}`);
});

process.on('SIGINT', () => {
  try {
    mqttClient.end(true);
  } catch (_) {}
  process.exit(0);
});
