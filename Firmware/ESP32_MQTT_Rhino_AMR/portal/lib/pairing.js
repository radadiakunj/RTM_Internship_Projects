'use strict';

const dgram = require('dgram');
const os = require('os');

const MULTICAST_ADDR = '239.0.0.1';
const MULTICAST_PORT = 7979;

/**
 * Listen for Reeman pairing multicast JSON:
 * { hostname, alias, key, token, robotType }
 */
class PairingListener {
  constructor() {
    this.socket = null;
    this.listening = false;
    this.lastPacket = null;
    this.listeners = new Set();
  }

  onPacket(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _emit(packet) {
    this.lastPacket = packet;
    for (const fn of this.listeners) {
      try {
        fn(packet);
      } catch (_) {
        /* ignore listener errors */
      }
    }
  }

  start(ifaceAddress) {
    if (this.listening) {
      return { ok: true, already: true };
    }

    const socket = dgram.createSocket({ type: 'udp4', reuseAddr: true });
    this.socket = socket;

    socket.on('error', (err) => {
      this._emit({ type: 'error', error: err.message, ts: Date.now() });
    });

    socket.on('message', (msg, rinfo) => {
      const raw = msg.toString('utf8').trim();
      let data = null;
      try {
        data = JSON.parse(raw);
      } catch {
        this._emit({
          type: 'raw',
          raw,
          from: `${rinfo.address}:${rinfo.port}`,
          ts: Date.now(),
        });
        return;
      }
      this._emit({
        type: 'pairing',
        hostname: data.hostname,
        alias: data.alias,
        key: data.key || data.encryptKey,
        token: data.token,
        robotType: data.robotType,
        raw: data,
        from: `${rinfo.address}:${rinfo.port}`,
        ts: Date.now(),
      });
    });

    return new Promise((resolve, reject) => {
      socket.bind(MULTICAST_PORT, () => {
        try {
          socket.setBroadcast(true);
          socket.setMulticastTTL(128);
          const ifaces = ifaceAddress ? [ifaceAddress] : listIpv4Addresses();
          if (ifaces.length === 0) {
            socket.addMembership(MULTICAST_ADDR);
          } else {
            for (const addr of ifaces) {
              try {
                socket.addMembership(MULTICAST_ADDR, addr);
              } catch (_) {
                /* some interfaces reject membership */
              }
            }
          }
          this.listening = true;
          resolve({
            ok: true,
            address: MULTICAST_ADDR,
            port: MULTICAST_PORT,
            interfaces: ifaces,
          });
        } catch (err) {
          reject(err);
        }
      });
    });
  }

  stop() {
    if (!this.socket) {
      this.listening = false;
      return { ok: true };
    }
    try {
      this.socket.dropMembership(MULTICAST_ADDR);
    } catch (_) {
      /* ignore */
    }
    this.socket.close();
    this.socket = null;
    this.listening = false;
    return { ok: true };
  }

  status() {
    return {
      listening: this.listening,
      address: MULTICAST_ADDR,
      port: MULTICAST_PORT,
      lastPacket: this.lastPacket,
    };
  }
}

function listIpv4Addresses() {
  const nets = os.networkInterfaces();
  const out = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family === 'IPv4' && !net.internal) {
        out.push(net.address);
      }
    }
  }
  return out;
}

module.exports = { PairingListener, MULTICAST_ADDR, MULTICAST_PORT, listIpv4Addresses };
