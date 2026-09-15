'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_MAX = 1000;

function normalize(raw, receivedAt = Date.now()) {
  const palletId = raw.palletId != null ? String(raw.palletId).trim() : '';
  if (!palletId) throw new Error('palletId required');
  const statusRaw = raw.status != null ? String(raw.status) : 'placed';
  return {
    id: `${palletId}-${receivedAt}-${Math.random().toString(36).slice(2, 6)}`,
    palletId,
    missionId: raw.missionId != null ? Number(raw.missionId) : null,
    stationId: raw.stationId != null ? String(raw.stationId) : 'esp-numpad-1',
    status: statusRaw,
    purpose:
      raw.purpose != null
        ? String(raw.purpose)
        : statusRaw === 'placed'
          ? 'Warehouse placement validated'
          : '',
    action: raw.action != null ? String(raw.action) : 'upsert',
    notes: raw.notes != null ? String(raw.notes) : '',
    createdAt: receivedAt,
    updatedAt: receivedAt,
    voidedBy: null,
    voidedAt: null,
    raw,
  };
}

class PalletStore {
  constructor(options = {}) {
    this.storagePath = options.storagePath || path.join(__dirname, '..', 'data', 'pallets.json');
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
      console.warn(`Pallet load failed: ${err.message}`);
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

  _findIndex(palletId, stationId) {
    return this.records.findIndex(
      (r) =>
        String(r.palletId) === String(palletId) &&
        String(r.stationId) === String(stationId) &&
        r.status !== 'void'
    );
  }

  upsert(raw) {
    const incoming = normalize(raw);
    const idx = this._findIndex(incoming.palletId, incoming.stationId);
    let updated = false;
    if (idx >= 0) {
      const prev = this.records[idx];
      this.records[idx] = {
        ...prev,
        ...incoming,
        id: prev.id,
        createdAt: prev.createdAt,
        updatedAt: Date.now(),
        voidedBy: prev.voidedBy,
        voidedAt: prev.voidedAt,
      };
      updated = true;
    } else {
      this.records.unshift(incoming);
    }
    if (this.records.length > this.maxRecords) {
      this.records = this.records.slice(0, this.maxRecords);
    }
    this._save();
    return { record: updated ? this.records[idx] : this.records[0], updated };
  }

  voidPallet(palletId, adminUser) {
    const id = String(palletId);
    let count = 0;
    const now = Date.now();
    for (const r of this.records) {
      if (String(r.palletId) === id && r.status !== 'void') {
        r.status = 'void';
        r.voidedBy = adminUser || 'admin';
        r.voidedAt = now;
        r.updatedAt = now;
        count += 1;
      }
    }
    if (count) this._save();
    return count;
  }

  list(limit = 100) {
    const n = Math.min(Number(limit) || 100, this.maxRecords);
    return { records: this.records.slice(0, n), stats: this.getStats() };
  }

  getStats() {
    const byStatus = {};
    for (const r of this.records) {
      byStatus[r.status] = (byStatus[r.status] || 0) + 1;
    }
    return { total: this.records.length, byStatus };
  }

  toCsv() {
    const header = [
      'palletId',
      'status',
      'purpose',
      'missionId',
      'stationId',
      'createdAt',
      'updatedAt',
      'voidedBy',
      'notes',
    ];
    const lines = ['\uFEFF' + header.join(',')]; // BOM for Excel
    for (const r of this.records) {
      const row = [
        r.palletId,
        r.status,
        r.purpose || '',
        r.missionId ?? '',
        r.stationId,
        r.createdAt,
        r.updatedAt,
        r.voidedBy || '',
        String(r.notes || '').replace(/"/g, '""'),
      ].map((c) => `"${c}"`);
      lines.push(row.join(','));
    }
    return lines.join('\n');
  }

  /** SpreadsheetML — opens in Microsoft Excel as .xls */
  toExcelXml() {
    const esc = (s) =>
      String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    const headers = [
      'Pallet ID',
      'Status',
      'Purpose',
      'Mission #',
      'Station',
      'Created (ms)',
      'Updated (ms)',
      'Voided by',
      'Notes',
    ];
    let rows = `<Row>${headers.map((h) => `<Cell><Data ss:Type="String">${esc(h)}</Data></Cell>`).join('')}</Row>`;
    for (const r of this.records) {
      const cells = [
        r.palletId,
        r.status,
        r.purpose || '',
        r.missionId ?? '',
        r.stationId,
        r.createdAt,
        r.updatedAt,
        r.voidedBy || '',
        r.notes || '',
      ];
      rows += `<Row>${cells
        .map((c) => {
          const isNum = typeof c === 'number' || (c !== '' && !Number.isNaN(Number(c)) && String(c).trim() !== '');
          const type = isNum && typeof c !== 'string' ? 'Number' : 'String';
          const val = isNum && type === 'Number' ? Number(c) : esc(c);
          return `<Cell><Data ss:Type="${type}">${val}</Data></Cell>`;
        })
        .join('')}</Row>`;
    }
    return `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Pallets">
  <Table>${rows}</Table>
 </Worksheet>
</Workbook>`;
  }
}

module.exports = { PalletStore, DEFAULT_TOPIC: 'callstation/pallet/record' };
