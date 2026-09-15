'use strict';

/**
 * What you publish vs what the AMR should return (Calling API v2).
 * Replace {hostname} with the robot hostname.
 */
function expectedFlows(hostname) {
  const h = hostname || '{hostname}';
  const phone = `reeman/calling/phone/${h}/v2`;
  const robot = `reeman/calling/robot/${h}/v2`;

  return [
    {
      name: 'Heartbeat',
      publish: {
        topic: `${phone}/heartbeat`,
        payload: { token: '<token>' },
        every: '3–5 seconds (must be <10s)',
      },
      expect: {
        topic: `${robot}/heartbeat`,
        every: '~5 seconds after robot wakes',
        payloadHint:
          'battery level, emergencyButton (0 pressed / 1 released), chargeState, isNavigating, currentTask, taskList',
      },
    },
    {
      name: 'Request normal points',
      publish: {
        topic: `${phone}/points/request/normal_model`,
        payload: { token: '<token>' },
      },
      expect: {
        topic: `${robot}/points/response/normal_model`,
        payloadHint:
          'code 0 = success (AES body → maps/points). code 1001/1002 = error plaintext in body',
      },
    },
    {
      name: 'Request calling / route / qrcode points',
      publish: {
        topic: `${phone}/points/request/<calling_model|route_model|qrcode_model>`,
        payload: { token: '<token>' },
      },
      expect: {
        topic: `${robot}/points/response/<same_model>`,
        payloadHint: 'Same code/body rules as normal points',
      },
    },
    {
      name: 'Normal task (go to point)',
      publish: {
        topic: `${phone}/task/normal_model`,
        payload: {
          token: '<token>',
          body: '<AES({ map: null, point: "PointA" })>',
        },
      },
      expect: {
        topic: `${robot}/task/response`,
        payloadHint:
          'code 0 = started. 2001–2002 data error. 2003 invalid state (e-stop/busy/low battery)',
      },
    },
    {
      name: 'Charge / Return task',
      publish: {
        topic: `${phone}/task/<charge_model|return_model>`,
        payload: { token: '<token>', body: null },
      },
      expect: {
        topic: `${robot}/task/response`,
        payloadHint: 'code 0 or 200x failure',
      },
    },
  ];
}

module.exports = { expectedFlows };
