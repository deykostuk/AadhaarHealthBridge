/**
 * In-Browser Offline Cryptographic QR Verifier (ECDSA-P256 / Web Crypto API)
 * Enables 100% offline verification of digital signatures and decompression of clinical triage records.
 */

const AHB_DEFAULT_JWK = {
  kty: "EC",
  crv: "P-256",
  x: "cqjjDC1ZPMV5UbpIUwvLL9MvYSGxxIJSF2-pSxDsCsw",
  y: "9oquEtHGHigVpUra8o7H3SELMLciWbXElALKhmcyR8g",
  use: "sig",
  alg: "ES256",
  kid: "ahb-offline-qr-v1"
};

class CryptoQRVerifier {
  constructor() {
    this.cryptoKey = null;
    this.cachedJwk = null;
  }

  // Base64-URL to Uint8Array helper
  static base64UrlToUint8Array(b64UrlStr) {
    let str = b64UrlStr.replace(/-/g, '+').replace(/_/g, '/');
    while (str.length % 4) str += '=';
    const binary = atob(str);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  // Converts ASN.1 DER ECDSA signature to IEEE P1363 (R || S) format for Web Crypto API
  static derToP1363(derBytes) {
    let offset = 0;
    if (derBytes[offset++] !== 0x30) throw new Error("Invalid DER sequence");
    let seqLen = derBytes[offset++];
    if (seqLen & 0x80) {
      const lenBytes = seqLen & 0x7f;
      offset += lenBytes;
    }

    // R value
    if (derBytes[offset++] !== 0x02) throw new Error("Expected integer for R");
    let rLen = derBytes[offset++];
    let rStart = offset;
    offset += rLen;
    if (derBytes[rStart] === 0x00) { rStart++; rLen--; }

    // S value
    if (derBytes[offset++] !== 0x02) throw new Error("Expected integer for S");
    let sLen = derBytes[offset++];
    let sStart = offset;
    offset += sLen;
    if (derBytes[sStart] === 0x00) { sStart++; sLen--; }

    const raw = new Uint8Array(64);
    raw.set(derBytes.subarray(rStart, rStart + rLen), 32 - rLen);
    raw.set(derBytes.subarray(sStart, sStart + sLen), 64 - sLen);
    return raw;
  }

  async getCryptoKey() {
    if (this.cryptoKey) return this.cryptoKey;

    let jwk = AHB_DEFAULT_JWK;
    const stored = localStorage.getItem('ahb_offline_public_key');
    if (stored) {
      try { jwk = JSON.parse(stored); } catch (e) {}
    }

    try {
      this.cryptoKey = await window.crypto.subtle.importKey(
        "jwk",
        jwk,
        { name: "ECDSA", namedCurve: "P-256" },
        true,
        ["verify"]
      );
      return this.cryptoKey;
    } catch (err) {
      console.error("[CryptoQRVerifier] Failed to import Web Crypto key:", err);
      throw err;
    }
  }

  async decompressZlib(compressedBytes) {
    if (typeof DecompressionStream !== 'undefined') {
      try {
        const ds = new DecompressionStream('deflate');
        const writer = ds.writable.getWriter();
        writer.write(compressedBytes);
        writer.close();
        const response = new Response(ds.readable);
        const arrayBuffer = await response.arrayBuffer();
        return new TextDecoder().decode(arrayBuffer);
      } catch (err) {
        console.warn('[DecompressionStream] Native deflate failed, trying raw:', err);
      }
    }

    // Fallback: simple text decode if uncompressed
    return new TextDecoder().decode(compressedBytes);
  }

  async verifySignedPayload(rawString) {
    const parts = (rawString || "").trim().split(".");
    if (parts.length !== 3 || parts[0] !== "AHB1") {
      throw new Error("Invalid QR format. Expected 'AHB1.<payload>.<signature>' header.");
    }

    const payloadB64 = parts[1];
    const sigB64 = parts[2];

    const payloadBytes = new TextEncoder().encode(payloadB64);
    const derSigBytes = CryptoQRVerifier.base64UrlToUint8Array(sigB64);
    const p1363SigBytes = CryptoQRVerifier.derToP1363(derSigBytes);

    const key = await this.getCryptoKey();

    // 1. Verify ECDSA-P256 signature
    const isValid = await window.crypto.subtle.verify(
      { name: "ECDSA", hash: { name: "SHA-256" } },
      key,
      p1363SigBytes,
      payloadBytes
    );

    if (!isValid) {
      throw new Error("Digital Signature Verification FAILED! Tampered or counterfeit QR pass.");
    }

    // 2. Decompress Payload
    const compressedPayload = CryptoQRVerifier.base64UrlToUint8Array(payloadB64);
    const jsonStr = await this.decompressZlib(compressedPayload);
    const data = JSON.parse(jsonStr);

    return {
      verified: true,
      data: data,
      rawHeader: parts[0],
      signatureAlgorithm: "ECDSA-SHA256 (P-256)"
    };
  }
}

// Global Singleton
window.cryptoQRVerifier = new CryptoQRVerifier();
