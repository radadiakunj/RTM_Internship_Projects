'use strict';

const POINT_MODELS = ['calling_model', 'normal_model', 'route_model', 'qrcode_model'];
const TASK_MODELS = ['normal_model', 'route_model', 'qrcode_model', 'charge_model', 'return_model'];

function phoneBase(hostname) {
  return `reeman/calling/phone/${hostname}/v2`;
}

function robotBase(hostname) {
  return `reeman/calling/robot/${hostname}/v2`;
}

function topics(hostname) {
  const p = phoneBase(hostname);
  const r = robotBase(hostname);
  return {
    phone: {
      heartbeat: `${p}/heartbeat`,
      pointsRequest: (model) => `${p}/points/request/${model}`,
      task: (model) => `${p}/task/${model}`,
    },
    robot: {
      heartbeat: `${r}/heartbeat`,
      pointsResponse: (model) => `${r}/points/response/${model}`,
      taskResponse: `${r}/task/response`,
    },
    subscribeAll: [
      `${r}/heartbeat`,
      ...POINT_MODELS.map((m) => `${r}/points/response/${m}`),
      `${r}/task/response`,
    ],
  };
}

function tokenPayload(token) {
  return JSON.stringify({ token });
}

function taskPayload(token, bodyEncryptedOrNull) {
  return JSON.stringify({
    token,
    body: bodyEncryptedOrNull,
  });
}

/** Plaintext before AES for normal_model task */
function normalTaskPlain({ map = null, point }) {
  const obj = { point };
  if (map != null && map !== '') obj.map = map;
  else obj.map = null;
  return JSON.stringify(obj);
}

/** Plaintext before AES for route_model task — route name string */
function routeTaskPlain(routeName) {
  return JSON.stringify(routeName);
}

/**
 * Plaintext before AES for qrcode_model — list of first/second pairs
 * pairs: [{ first: { map, point }, second: { map, point } }, ...]
 */
function qrcodeTaskPlain(pairs) {
  return JSON.stringify(pairs);
}

const STATUS_CODES = {
  0: 'Success',
  1001: 'Failed to get points (data source issue)',
  1002: 'Failed to get points (elevator control error)',
  2001: 'Task failed (data source issue)',
  2002: 'Task failed (data source issue)',
  2003: 'Task failed (invalid state: e-stop, low battery, busy, lift not reset, etc.)',
};

function describeCode(code) {
  return STATUS_CODES[code] || `Unknown code ${code}`;
}

const CHARGE_STATES = {
  1: 'Not charging',
  2: 'Dock charging',
  3: 'Cable charging',
  8: 'Docking',
};

function describeChargeState(state) {
  if (state > 8) return 'Charge failed';
  return CHARGE_STATES[state] || `Unknown (${state})`;
}

const TASK_MODE_LABELS = {
  0: 'Normal',
  1: 'Route',
  2: 'QR Code',
  3: 'Charging',
  4: 'Returning',
  5: 'Calling',
};

module.exports = {
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
};
