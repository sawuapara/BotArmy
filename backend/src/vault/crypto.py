"""
Server-side vault encryption using PBKDF2 + AES-GCM.

Mirrors the client-side crypto.ts implementation for compatibility.
"""

import base64
import hashlib
import os
import json
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# PBKDF2 configuration (must match frontend)
PBKDF2_ITERATIONS = 100000
PBKDF2_HASH = 'sha256'
KEY_LENGTH_BYTES = 32  # 256 bits

# AES-GCM configuration
IV_LENGTH_BYTES = 12  # 96 bits, recommended for AES-GCM


def derive_key(password: str, salt_base64: str) -> bytes:
    """
    Derive a 256-bit AES key from password and salt using PBKDF2.

    Args:
        password: The master password
        salt_base64: Base64-encoded salt from the database

    Returns:
        32-byte key suitable for AES-256-GCM
    """
    salt = base64.b64decode(salt_base64)
    key = hashlib.pbkdf2_hmac(
        PBKDF2_HASH,
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH_BYTES
    )
    return key


def encrypt(key: bytes, plaintext: str) -> tuple[str, str]:
    """
    Encrypt plaintext using AES-256-GCM.

    Args:
        key: 32-byte encryption key
        plaintext: String to encrypt

    Returns:
        Tuple of (encrypted_base64, iv_base64)
    """
    # Generate random IV
    iv = os.urandom(IV_LENGTH_BYTES)

    # Encrypt
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)

    # Return base64 encoded
    return (
        base64.b64encode(ciphertext).decode('ascii'),
        base64.b64encode(iv).decode('ascii')
    )


def decrypt(key: bytes, encrypted_base64: str, iv_base64: str) -> str:
    """
    Decrypt ciphertext using AES-256-GCM.

    Args:
        key: 32-byte encryption key
        encrypted_base64: Base64-encoded ciphertext
        iv_base64: Base64-encoded initialization vector

    Returns:
        Decrypted plaintext string

    Raises:
        Exception if decryption fails (wrong key or tampered data)
    """
    ciphertext = base64.b64decode(encrypted_base64)
    iv = base64.b64decode(iv_base64)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)

    return plaintext.decode('utf-8')


def encrypt_object(key: bytes, data: Any) -> tuple[str, str]:
    """
    Encrypt a Python object as JSON.

    Args:
        key: 32-byte encryption key
        data: Object to encrypt (must be JSON-serializable)

    Returns:
        Tuple of (encrypted_base64, iv_base64)
    """
    json_str = json.dumps(data)
    return encrypt(key, json_str)


def decrypt_object(key: bytes, encrypted_base64: str, iv_base64: str) -> Any:
    """
    Decrypt and parse a JSON object.

    Args:
        key: 32-byte encryption key
        encrypted_base64: Base64-encoded ciphertext
        iv_base64: Base64-encoded initialization vector

    Returns:
        Decrypted and parsed object
    """
    json_str = decrypt(key, encrypted_base64, iv_base64)
    return json.loads(json_str)
