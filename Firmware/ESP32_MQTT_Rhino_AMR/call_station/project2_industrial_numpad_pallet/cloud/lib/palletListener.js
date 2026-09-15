'use strict';

const mqtt = require('mqtt');
const { DEFAULT_TOPIC } = require('./pallets');

function startPalletListener(config, store, onRecord) {
  const ph = config.palletHistory || {};
  const topic = ph.topic || DEFAULT_TOPIC;
  const host = (config.mqtt && config.mqtt.host) || '127.0.0.1';
  const port = (config.mqtt && config.mqtt.port) || 1883;
  const username = (config.mqtt && config.mqtt.username) || '';
  const password = (config.mqtt && config.mqtt.password) || '';

  const url = `mqtt://${host}:${port}`;
  const client = mqtt.connect(url, {
    clientId: `pallet-cloud-${Math.random().toString(16).slice(2, 10)}`,
    username: username || undefined,
    password: password || undefined,
    reconnectPeriod: 3000,
  });

  client.on('connect', () => {
    console.log(`[pallet] MQTT connected ${url}, subscribe ${topic}`);
    client.subscribe(topic, (err) => {
      if (err) console.error('[pallet] subscribe failed', err.message);
    });
  });

  client.on('message', (t, buf) => {
    if (t !== topic) return;
    let parsed;
    try {
      parsed = JSON.parse(buf.toString('utf8'));
    } catch (err) {
      console.warn('[pallet] bad JSON', err.message);
      return;
    }
    try {
      const { record, updated } = store.upsert(parsed);
      console.log(
        `[pallet] ${updated ? 'updated' : 'created'} ${record.palletId} status=${record.status}`
      );
      if (typeof onRecord === 'function') onRecord(record, updated);
    } catch (err) {
      console.warn('[pallet] upsert failed', err.message);
    }
  });

  client.on('error', (err) => console.error('[pallet] MQTT error', err.message));

  return client;
}

module.exports = { startPalletListener };
