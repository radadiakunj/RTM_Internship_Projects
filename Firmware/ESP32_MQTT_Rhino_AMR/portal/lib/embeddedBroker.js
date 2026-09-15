'use strict';

const net = require('net');
const { Aedes } = require('aedes');
const { encrypt } = require('./aes');
const { topics, describeChargeState } = require('./calling');

/**
 * In-process MQTT broker so you can practice with zero Wi-Fi / Mosquitto.
 * Aedes v1 requires createBroker() (calls listen internally) or CONNACK never arrives.
 */
async function startEmbeddedBroker({ host = '127.0.0.1', port = 2883, mockRobot = true, demo }) {
  const broker = await Aedes.createBroker();
  const server = net.createServer(broker.handle.bind(broker));

  const demoCfg = {
    hostname: (demo && demo.hostname) || 'rbot55f-260114-003-001',
    token: (demo && demo.token) || 'demo-token',
    encryptKey: (demo && demo.encryptKey) || '1234567890123456',
  };

  if (mockRobot) {
    attachMockRobot(broker, demoCfg);
  }

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, resolve);
  });

  return {
    broker,
    server,
    host,
    port,
    mockRobot,
    demo: demoCfg,
    url: `mqtt://${host}:${port}`,
  };
}

function attachMockRobot(broker, demo) {
  const t = topics(demo.hostname);

  broker.on('publish', (packet, client) => {
    if (!client) return; // ignore broker-internal
    const topic = packet.topic;
    const payloadText = packet.payload.toString('utf8');
    let payload = payloadText;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      /* keep string */
    }

    if (topic === t.phone.heartbeat) {
      publish(broker, t.robot.heartbeat, {
        hostname: demo.hostname,
        token: demo.token,
        alias: 'offline-demo-amr',
        level: 87,
        lowPower: false,
        emergencyButton: 1,
        chargeState: 1,
        chargeStateLabel: describeChargeState(1),
        isNavigating: false,
        isElevatorMode: false,
        robotType: 9,
        liftModelState: 0,
        isLifting: false,
        isMapping: false,
        taskExecuting: false,
        currentTask: null,
        taskList: [],
        offlineDemo: true,
      });
      return;
    }

    const pointModels = ['calling_model', 'normal_model', 'route_model', 'qrcode_model'];
    for (const model of pointModels) {
      if (topic === t.phone.pointsRequest(model)) {
        let plain;
        if (model === 'route_model') {
          plain = JSON.stringify(['route_demo_1', 'route_demo_2']);
        } else {
          plain = JSON.stringify({
            elevatorModeSwitch: false,
            model: {
              demo_map: ['PointA', 'PointB', 'Charge'],
            },
          });
        }
        let body;
        try {
          body = encrypt(plain, demo.encryptKey);
        } catch {
          body = plain;
        }
        publish(broker, t.robot.pointsResponse(model), {
          token: demo.token,
          code: 0,
          body,
        });
        return;
      }
    }

    const taskModels = ['normal_model', 'route_model', 'qrcode_model', 'charge_model', 'return_model'];
    for (const model of taskModels) {
      if (topic === t.phone.task(model)) {
        let body;
        try {
          body = encrypt('Task started (offline demo)', demo.encryptKey);
        } catch {
          body = 'Task started (offline demo)';
        }
        publish(broker, t.robot.taskResponse, {
          token: demo.token,
          code: 0,
          body,
        });
        return;
      }
    }
  });
}

function publish(broker, topic, obj) {
  broker.publish(
    {
      cmd: 'publish',
      qos: 0,
      retain: false,
      topic,
      payload: Buffer.from(JSON.stringify(obj)),
    },
    () => {}
  );
}

module.exports = { startEmbeddedBroker };
