'use strict';

const crypto = require('crypto');

/**
 * Reeman Android apps typically use AES/ECB/PKCS5Padding.
 * Key is taken from pairing multicast "key" field.
 * If key length is not 16/24/32 bytes, pad/truncate to 16 for AES-128.
 */
function normalizeKey(key) {
  if (!key || typeof key !== 'string') {
    throw new Error('encryptKey is required for AES');
  }
  const buf = Buffer.from(key, 'utf8');
  if (buf.length === 16 || buf.length === 24 || buf.length === 32) {
    return buf;
  }
  const out = Buffer.alloc(16, 0);
  buf.copy(out, 0, 0, Math.min(buf.length, 16));
  return out;
}

function encrypt(plaintext, key) {
  const keyBuf = normalizeKey(key);
  const cipher = crypto.createCipheriv(`aes-${keyBuf.length * 8}-ecb`, keyBuf, null);
  cipher.setAutoPadding(true);
  const enc = Buffer.concat([
    cipher.update(typeof plaintext === 'string' ? plaintext : JSON.stringify(plaintext), 'utf8'),
    cipher.final(),
  ]);
  return enc.toString('base64');
}

function decrypt(ciphertextB64, key) {
  const keyBuf = normalizeKey(key);
  const decipher = crypto.createDecipheriv(`aes-${keyBuf.length * 8}-ecb`, keyBuf, null);
  decipher.setAutoPadding(true);
  const dec = Buffer.concat([
    decipher.update(Buffer.from(ciphertextB64, 'base64')),
    decipher.final(),
  ]);
  const text = dec.toString('utf8');
  try {
    return { ok: true, text, json: JSON.parse(text) };
  } catch {
    return { ok: true, text, json: null };
  }
}

function tryDecryptBody(body, code, key) {
  if (body == null || body === '') {
    return { decrypted: null, raw: body, error: null };
  }
  // Success codes: 0 or 200 — decrypt. Error ranges: leave plaintext.
  const shouldDecrypt = code === 0 || code === 200;
  if (!shouldDecrypt) {
    return { decrypted: body, raw: body, error: null, plaintextError: true };
  }
  if (!key) {
    return { decrypted: null, raw: body, error: 'encryptKey missing — cannot decrypt body' };
  }
  try {
    const result = decrypt(body, key);
    return { decrypted: result.json != null ? result.json : result.text, raw: body, error: null };
  } catch (err) {
    return { decrypted: null, raw: body, error: err.message };
  }
}

module.exports = { encrypt, decrypt, tryDecryptBody, normalizeKey };
