'use strict';

const mqtt = require('mqtt');
const { DEFAULT_TOPIC, MissionStore } = require('./missions');

function resolveBroker(config) {
  const mh = config.missionHistory || {};
  const profile = mh.brokerProfile || 'callMode';
  const broker = (config.brokers && config.brokers[profile]) || config.brokers?.local;
  const host =
    mh.host ||
    (broker && broker.host) ||
    config.mqttHost ||
    '127.0.0.1';
  const port = Number(mh.port || (broker && broker.port) || config.mqttPort || 1883);
  const username = mh.username != null ? mh.username : (broker && broker.username) || config.mqttUsername || '';
  const password = mh.password != null ? mh.password : (broker && broker.password) || config.mqttPassword || '';
  const topic = mh.topic || DEFAULT_TOPIC;
  return { host, port, username, password, topic };
}

function startMissionListener(config, store, onRecord) {
  const { host, port, username, password, topic } = resolveBroker(config);
  const url = `mqtt://${host}:${port}`;
  const opts = {
    clientId: `mission-portal-${Math.random().toString(16).slice(2, 10)}`,
    clean: true,
    reconnectPeriod: 5000,
    connectTimeout: 10000,
  };
  if (username) {
    opts.username = username;
    opts.password = password;
  }

  let connected = false;
  const client = mqtt.connect(url, opts);

  client.on('connect', () => {
    connected = true;
    client.subscribe(topic, { qos: 1 }, (err) => {
      if (err) {
        console.warn(`Mission listener subscribe failed: ${err.message}`);
        return;
      }
      console.log(`Mission listener subscribed → ${topic} on ${host}:${port}`);
    });
  });

  client.on('message', (msgTopic, payloadBuf) => {
    if (msgTopic !== topic) return;
    let parsed;
    try {
      parsed = JSON.parse(payloadBuf.toString('utf8'));
    } catch (err) {
      console.warn(`Mission record JSON invalid: ${err.message}`);
      return;
    }
    try {
      const { record, updated } = store.upsert(parsed);
      console.log(
        `Mission #${record.missionId} ${updated ? 'updated' : 'created'}: ${record.status || record.result}`
      );
      if (onRecord) onRecord(record);
    } catch (err) {
      console.warn(`Mission record rejected: ${err.message}`);
    }
  });

  client.on('error', (err) => {
    console.warn(`Mission listener error: ${err.message}`);
  });

  client.on('close', () => {
    connected = false;
  });

  return {
    client,
    topic,
    broker: { host, port },
    isConnected: () => connected,
    stop() {
      try {
        client.end(true);
      } catch (_) {
        /* ignore */
      }
    },
  };
}

module.exports = {
  startMissionListener,
  resolveBroker,
};
