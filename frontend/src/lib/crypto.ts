/**
 * Web Crypto API utilities for client-side vault encryption.
 *
 * Security Architecture:
 * - Master password never leaves the browser after initial setup/unlock
 * - PBKDF2 derives a 256-bit AES key from password + server-provided salt
 * - AES-GCM provides authenticated encryption (confidentiality + integrity)
 * - Each item gets a unique random IV
 */

// PBKDF2 configuration
const PBKDF2_ITERATIONS = 100000;
const PBKDF2_HASH = 'SHA-256';
const KEY_LENGTH_BITS = 256;

// AES-GCM configuration
const AES_MODE = 'AES-GCM';
const IV_LENGTH_BYTES = 12; // 96 bits, recommended for AES-GCM

/**
 * Derive an AES-256 encryption key from a password and salt using PBKDF2.
 *
 * @param password - The user's master password
 * @param saltBase64 - Base64-encoded salt from the server
 * @returns CryptoKey suitable for AES-GCM encryption/decryption
 */
export async function deriveKey(
  password: string,
  saltBase64: string
): Promise<CryptoKey> {
  // Decode the salt
  const salt = base64ToBytes(saltBase64);

  // Import password as raw key material
  const encoder = new TextEncoder();
  const passwordKey = await window.crypto.subtle.importKey(
    'raw',
    encoder.encode(password),
    'PBKDF2',
    false, // not extractable
    ['deriveBits', 'deriveKey']
  );

  // Derive the AES key
  const aesKey = await window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: PBKDF2_ITERATIONS,
      hash: PBKDF2_HASH,
    },
    passwordKey,
    {
      name: AES_MODE,
      length: KEY_LENGTH_BITS,
    },
    false, // not extractable - key cannot be exported
    ['encrypt', 'decrypt']
  );

  return aesKey;
}

/**
 * Encrypt plaintext using AES-GCM with the provided key.
 *
 * @param key - CryptoKey from deriveKey()
 * @param plaintext - The string to encrypt
 * @returns Object with base64-encoded encrypted data and IV
 */
export async function encrypt(
  key: CryptoKey,
  plaintext: string
): Promise<{ encrypted: string; iv: string }> {
  // Generate a random IV (unique per encryption)
  const iv = window.crypto.getRandomValues(new Uint8Array(IV_LENGTH_BYTES));

  // Encode plaintext to bytes
  const encoder = new TextEncoder();
  const plaintextBytes = encoder.encode(plaintext);

  // Encrypt
  const encryptedBuffer = await window.crypto.subtle.encrypt(
    {
      name: AES_MODE,
      iv,
    },
    key,
    plaintextBytes
  );

  // Convert to base64 for storage/transport
  return {
    encrypted: bytesToBase64(new Uint8Array(encryptedBuffer)),
    iv: bytesToBase64(iv),
  };
}

/**
 * Decrypt ciphertext using AES-GCM with the provided key.
 *
 * @param key - CryptoKey from deriveKey()
 * @param encryptedBase64 - Base64-encoded ciphertext
 * @param ivBase64 - Base64-encoded initialization vector
 * @returns The decrypted plaintext string
 * @throws Error if decryption fails (wrong key or tampered data)
 */
export async function decrypt(
  key: CryptoKey,
  encryptedBase64: string,
  ivBase64: string
): Promise<string> {
  // Decode from base64
  const encrypted = base64ToBytes(encryptedBase64);
  const iv = base64ToBytes(ivBase64);

  // Decrypt
  const decryptedBuffer = await window.crypto.subtle.decrypt(
    {
      name: AES_MODE,
      iv,
    },
    key,
    encrypted
  );

  // Decode bytes to string
  const decoder = new TextDecoder();
  return decoder.decode(decryptedBuffer);
}

/**
 * Convert a Uint8Array to a base64 string.
 */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert a base64 string to a Uint8Array.
 */
export function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Encrypt a JavaScript object as JSON.
 * Convenience wrapper for encrypt().
 */
export async function encryptObject(
  key: CryptoKey,
  data: unknown
): Promise<{ encrypted: string; iv: string }> {
  const json = JSON.stringify(data);
  return encrypt(key, json);
}

/**
 * Decrypt and parse a JSON object.
 * Convenience wrapper for decrypt().
 */
export async function decryptObject<T = unknown>(
  key: CryptoKey,
  encryptedBase64: string,
  ivBase64: string
): Promise<T> {
  const json = await decrypt(key, encryptedBase64, ivBase64);
  return JSON.parse(json) as T;
}
