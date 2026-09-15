#!/usr/bin/env node
'use strict';

/**
 * Terminal MQTT client for AMR local broker or any broker.
 *
 * Examples:
 *   node cli/mqtt-term.js listen
 *   node cli/mqtt-term.js hb
 *   node cli/mqtt-term.js points normal
 *   node cli/mqtt-term.js task normal PointA
 *   node cli/mqtt-term.js pub reeman/calling/phone/HOST/v2/heartbeat "{\"token\":\"...\"}"
 *
 * Config defaults come from ../config.json (host/port/hostname/token/user/pass).
 */

const fs = require('fs');
const path = require('path');
const mqtt = require('mqtt');
const { topics, tokenPayload, taskPayload, normalTaskPlain, describeCode } = require('../lib/calling');
const { encrypt, tryDecryptBody } = require('../lib/aes');
const { expectedFlows } = require('../lib/topicGuide');

const CONFIG_PATH = path.join(__dirname, '..', 'config.json');
const EXAMPLE_PATH = path.join(__dirname, '..', 'config.example.json');

function loadConfig() {
  const src = fs.existsSync(CONFIG_PATH) ? CONFIG_PATH : EXAMPLE_PATH;
  return JSON.parse(fs.readFileSync(src, 'utf8'));
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--host') args.host = argv[++i];
    else if (a === '--port') args.port = Number(argv[++i]);
    else if (a === '--hostname') args.hostname = argv[++i];
    else if (a === '--token') args.token = argv[++i];
    else if (a === '--key') args.key = argv[++i];
    else if (a === '--user') args.user = argv[++i];
    else if (a === '--pass') args.pass = argv[++i];
    else if (a === '--help' || a === '-h') args.help = true;
    else args._.push(a);
  }
  return args;
}

function usage() {
  console.log(`
AMR MQTT terminal helper
========================

Usage:
  npm run mqtt -- listen
  npm run mqtt -- guide
  npm run mqtt -- hb
  npm run mqtt -- points [normal|calling|route|qrcode]
  npm run mqtt -- task normal <PointName>
  npm run mqtt -- task charge
  npm run mqtt -- task return
  npm run mqtt -- pub <topic> <jsonPayload>

Options (override config.json):
  --host 192.168.5.75
  --port 1883
  --hostname rbot55f-260114-003-001
  --token <token>
  --key <encryptKey>
  --user <mqttUsername>     (if broker needs auth)
  --pass <mqttPassword>

What comes back:
  listen     → prints ALL messages (see robot replies live)
  hb         → publish phone heartbeat; expect robot/.../heartbeat
  points     → publish points request; expect robot/.../points/response/...
  task       → publish task; expect robot/.../task/response
`);
}

function connect(cfg) {
  const host = cfg.host;
  const port = cfg.port;
  const opts = {
    clientId: `mqtt-term-${Math.random().toString(16).slice(2, 8)}`,
    clean: true,
    reconnectPeriod: 0,
    connectTimeout: 12000,
  };
  if (cfg.user) {
    opts.username = cfg.user;
    opts.password = cfg.pass || '';
  }

  const url = `mqtt://${host}:${port}`;
  console.log(`Connecting ${url} ...`);
  return new Promise((resolve, reject) => {
    const client = mqtt.connect(url, opts);
    const onErr = (err) => {
      cleanup();
      reject(err);
    };
    const onConnect = () => {
      cleanup();
      console.log('Connected.');
      resolve(client);
    };
    const cleanup = () => {
      client.off('connect', onConnect);
      client.off('error', onErr);
    };
    client.once('connect', onConnect);
    client.once('error', onErr);
  });
}

function printIncoming(cfg, topic, buf) {
  const text = buf.toString('utf8');
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    parsed = text;
  }

  console.log('\n---------- MQTT IN ----------');
  console.log('topic :', topic);
  console.log('raw   :', text);

  const t = topics(cfg.hostname);
  if (topic === t.robot.heartbeat) {
    console.log('expect: robot heartbeat (battery / e-stop / nav / task)');
  } else if (topic === t.robot.taskResponse) {
    const code = parsed && parsed.code;
    console.log('expect: task response →', describeCode(code));
    const dec = tryDecryptBody(parsed && parsed.body, code, cfg.key);
    if (dec.decrypted != null) console.log('body  :', dec.decrypted);
    if (dec.error) console.log('decrypt error:', dec.error);
  } else {
    for (const model of ['calling_model', 'normal_model', 'route_model', 'qrcode_model']) {
      if (topic === t.robot.pointsResponse(model)) {
        const code = parsed && parsed.code;
        console.log(`expect: points response (${model}) →`, describeCode(code));
        const dec = tryDecryptBody(parsed && parsed.body, code, cfg.key);
        if (dec.decrypted != null) console.log('body  :', JSON.stringify(dec.decrypted, null, 2));
        if (dec.error) console.log('decrypt error:', dec.error);
      }
    }
  }
  console.log('-----------------------------\n');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args._.length === 0) {
    usage();
    process.exit(args.help ? 0 : 1);
  }

  const fileCfg = loadConfig();
  const amr = fileCfg.brokers.amr || {};
  const cfg = {
    host: args.host || amr.host || fileCfg.navIp || '192.168.5.75',
    port: Number(args.port || amr.port || 1883),
    hostname: args.hostname || fileCfg.hostname,
    token: args.token != null ? args.token : fileCfg.token,
    key: args.key != null ? args.key : fileCfg.encryptKey,
    user: args.user != null ? args.user : fileCfg.mqttUsername || amr.username || '',
    pass: args.pass != null ? args.pass : fileCfg.mqttPassword || amr.password || '',
  };

  const cmd = args._[0];

  if (cmd === 'guide') {
    console.log(JSON.stringify(expectedFlows(cfg.hostname), null, 2));
    return;
  }

  const client = await connect(cfg);
  client.on('error', (err) => console.error('MQTT error:', err.message));
  client.on('message', (topic, buf) => printIncoming(cfg, topic, buf));

  const t = topics(cfg.hostname);

  const subscribeRobot = () =>
    new Promise((resolve, reject) => {
      const subs = ['#', ...t.subscribeAll];
      client.subscribe(subs, (err) => (err ? reject(err) : resolve(subs)));
    });

  if (cmd === 'listen') {
    const subs = await subscribeRobot();
    console.log('Listening. Subscribed:', subs.join(', '));
    console.log('Publish from another terminal, or run: npm run mqtt -- hb');
    console.log('Ctrl+C to stop.\n');
    console.log('Expected robot topics:');
    for (const s of t.subscribeAll) console.log('  ', s);
    return; // keep process alive
  }

  await subscribeRobot();

  if (cmd === 'hb') {
    const topic = t.phone.heartbeat;
    const payload = tokenPayload(cfg.token);
    client.publish(topic, payload);
    console.log('PUB', topic, payload);
    console.log('Expect IN on', t.robot.heartbeat, '(within a few seconds if robot is awake)');
    setTimeout(() => process.exit(0), 8000);
    return;
  }

  if (cmd === 'points') {
    const modelMap = {
      normal: 'normal_model',
      calling: 'calling_model',
      route: 'route_model',
      qrcode: 'qrcode_model',
    };
    const key = (args._[1] || 'normal').toLowerCase();
    const model = modelMap[key] || `${key}_model`;
    const topic = t.phone.pointsRequest(model);
    const payload = tokenPayload(cfg.token);
    client.publish(topic, payload);
    console.log('PUB', topic, payload);
    console.log('Expect IN on', t.robot.pointsResponse(model));
    setTimeout(() => process.exit(0), 10000);
    return;
  }

  if (cmd === 'task') {
    const kind = (args._[1] || 'normal').toLowerCase();
    let model;
    let body = null;
    if (kind === 'charge') {
      model = 'charge_model';
    } else if (kind === 'return') {
      model = 'return_model';
    } else {
      model = 'normal_model';
      const point = args._[2];
      if (!point) {
        console.error('Need point name: npm run mqtt -- task normal PointA');
        process.exit(1);
      }
      if (!cfg.key) {
        console.error('encryptKey required for task body. Set in config.json or --key');
        process.exit(1);
      }
      body = encrypt(normalTaskPlain({ map: null, point }), cfg.key);
    }
    const topic = t.phone.task(model);
    const payload = taskPayload(cfg.token, body);
    client.publish(topic, payload);
    console.log('PUB', topic, payload);
    console.log('Expect IN on', t.robot.taskResponse);
    setTimeout(() => process.exit(0), 10000);
    return;
  }

  if (cmd === 'pub') {
    const topic = args._[1];
    const payload = args._[2] || '';
    if (!topic) {
      console.error('Need topic');
      process.exit(1);
    }
    client.publish(topic, payload);
    console.log('PUB', topic, payload);
    setTimeout(() => process.exit(0), 5000);
    return;
  }

  console.error('Unknown command:', cmd);
  usage();
  process.exit(1);
}

main().catch((err) => {
  console.error('Failed:', err.message);
  if (/username|password|Not authorized|Bad user|not authorised/i.test(err.message)) {
    console.error('\nMQTT broker rejected this login (CONNACK not authorized / bad credentials).');
    console.error('Checklist:');
    console.error('  1) On AMR MQTT page, confirm Username/Password were SAVED and MQTT service restarted');
    console.error('  2) Use the exact same spelling/case (MQTT_KNJ / 1234)');
    console.error('  3) If there is an "Allow anonymous" or ACL list, enable your user or allow all clients');
    console.error('  4) Try without auth: npm run mqtt -- listen --host 192.168.5.75 --port 1883');
    console.error('  5) Calling Token is NOT the MQTT password unless the AMR screen says so');
    console.error('  6) If Wi-Fi drops every ~5 min, fix that first — MQTT will fail while offline');
  }
  process.exit(1);
});
