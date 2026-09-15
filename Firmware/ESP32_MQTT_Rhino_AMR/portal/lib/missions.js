'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_TOPIC = 'callstation/mission/record';
const DEFAULT_MAX = 500;

function normalizeRecord(raw, receivedAt = Date.now()) {
  const missionId = Number(raw.missionId);
  if (!Number.isFinite(missionId) || missionId <= 0) {
    throw new Error('missionId must be a positive number');
  }
  const phase = raw.phase != null ? String(raw.phase) : 'unknown';
  const workflow = raw.workflow != null ? String(raw.workflow) : 'unknown';
  const statusRaw = raw.status != null ? raw.status : raw.result;
  const status = statusRaw != null ? String(statusRaw) : 'stored';
  const result = raw.result != null ? String(raw.result) : status;
  return {
    id: `${missionId}-${receivedAt}-${Math.random().toString(36).slice(2, 8)}`,
    missionId,
    receivedAt,
    createdAt: receivedAt,
    updatedAt: receivedAt,
    stationId: raw.stationId != null ? String(raw.stationId) : 'esp-direct',
    hostname: raw.hostname != null ? String(raw.hostname) : '',
    key: raw.key != null ? String(raw.key) : '',
    action: raw.action != null ? String(raw.action) : 'store',
    workflow,
    phase,
    status,
    pick: raw.pick != null ? String(raw.pick) : '',
    drop: raw.drop != null ? String(raw.drop) : '',
    home: raw.home != null ? String(raw.home) : '',
    charge: raw.charge != null ? String(raw.charge) : '',
    batteryPct: raw.batteryPct != null ? Number(raw.batteryPct) : null,
    uptimeMs: raw.uptimeMs != null ? Number(raw.uptimeMs) : null,
    startedAtMs: raw.startedAtMs != null ? Number(raw.startedAtMs) : null,
    result,
    notes: raw.notes != null ? String(raw.notes) : '',
    raw,
  };
}

class MissionStore {
  constructor(options = {}) {
    this.storagePath = options.storagePath || path.join(__dirname, '..', 'data', 'missions.json');
    this.maxRecords = Number(options.maxRecords) > 0 ? Number(options.maxRecords) : DEFAULT_MAX;
    this.records = [];
    this._load();
  }

  _load() {
    try {
      if (!fs.existsSync(this.storagePath)) {
        this._save();
        return;
      }
      const parsed = JSON.parse(fs.readFileSync(this.storagePath, 'utf8'));
      this.records = Array.isArray(parsed.records) ? parsed.records : [];
    } catch (err) {
      console.warn(`Mission history load failed: ${err.message}`);
      this.records = [];
    }
  }

  _save() {
    const dir = path.dirname(this.storagePath);
    fs.mkdirSync(dir, { recursive: true });
    const payload = {
      updatedAt: Date.now(),
      records: this.records.slice(0, this.maxRecords),
      stats: this.getStats(),
    };
    fs.writeFileSync(this.storagePath, JSON.stringify(payload, null, 2));
    return payload;
  }

  _findIndex(missionId, stationId) {
    return this.records.findIndex(
      (r) => Number(r.missionId) === Number(missionId) && String(r.stationId) === String(stationId)
    );
  }

  /** Insert or update one mission row (same missionId+stationId). */
  upsert(raw) {
    const incoming = normalizeRecord(raw);
    const idx = this._findIndex(incoming.missionId, incoming.stationId);
    if (idx >= 0) {
      const prev = this.records[idx];
      incoming.id = prev.id;
      incoming.createdAt = prev.createdAt || prev.receivedAt || incoming.receivedAt;
      incoming.updatedAt = incoming.receivedAt;
      this.records.splice(idx, 1);
    }
    this.records.unshift(incoming);
    if (this.records.length > this.maxRecords) {
      this.records.length = this.maxRecords;
    }
    const saved = this._save();
    return { record: incoming, saved, updated: idx >= 0 };
  }

  add(raw) {
    return this.upsert(raw);
  }

  list(limit = 100) {
    const n = Math.min(Math.max(Number(limit) || 100, 1), this.maxRecords);
    return {
      records: this.records.slice(0, n),
      stats: this.getStats(),
    };
  }

  getStats() {
    const total = this.records.length;
    const byStatus = {};
    const byResult = {};
    for (const row of this.records) {
      const statusKey = row.status || row.result || 'unknown';
      byStatus[statusKey] = (byStatus[statusKey] || 0) + 1;
      const resultKey = row.result || statusKey;
      byResult[resultKey] = (byResult[resultKey] || 0) + 1;
    }
    const latest = this.records[0] || null;
    return {
      total,
      byStatus,
      byResult,
      latestMissionId: latest ? latest.missionId : null,
      latestStatus: latest ? latest.status || latest.result : null,
      latestReceivedAt: latest ? latest.updatedAt || latest.receivedAt : null,
      activeCount: this.records.filter((r) => {
        const s = r.status || r.result;
        return s === 'running' || s === 'pausing';
      }).length,
    };
  }
}

module.exports = {
  DEFAULT_TOPIC,
  MissionStore,
  normalizeRecord,
};
