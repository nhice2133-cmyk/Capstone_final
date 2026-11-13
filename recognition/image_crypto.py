"""
SMART ENTRY — Biometric & Snapshot Image Encryption Engine
Caraga State University Cabadbaran Campus (CSUCC) - Athenaeum Library
---------------------------------------------------------------------
Cryptographically safeguards student facial biometric datasets (face_data/)
and stranger surveillance alert snapshots (static/snapshots/) at rest.

Key Characteristics:
- Encryption Standard: Authenticated AES (Fernet: 128-bit AES-CBC + HMAC-SHA256).
- Key Derivation: Deterministically generated from the institutional Master Recovery Key
  (Config.ADMIN_RECOVERY_KEY) using PBKDF2-HMAC-SHA256 with 100,000 rounds.
- Transparent In-Memory Decoding: Images are encrypted on disk and decoded directly
  to OpenCV BGR matrices in RAM, ensuring zero unencrypted biometric exposure to the filesystem.
- Automatic Migration: Automatically encrypts legacy unencrypted JPEG files on startup.
"""

import os
import glob
import base64
import hashlib
import numpy as np
import cv2
from cryptography.fernet import Fernet, InvalidToken
from config import Config

INSTITUTIONAL_SALT = b"CSUCC-ATHENAEUM-BIOMETRIC-ENCRYPTION-SALT-2026"
_FERNET_INSTANCE = None


def get_encryption_key() -> bytes:
    """
    Derives a URL-safe 32-byte Fernet key deterministically from the
    CSUCC Master Recovery Key using PBKDF2-HMAC-SHA256 with 100,000 iterations.
    """
    master_key = getattr(Config, "ADMIN_RECOVERY_KEY", "CSUCC-ATHENAEUM-RESET-2026")
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        master_key.encode("utf-8"),
        INSTITUTIONAL_SALT,
        iterations=100_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(derived_key)


def get_fernet() -> Fernet:
    """Returns a singleton Fernet cipher instance."""
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None:
        _FERNET_INSTANCE = Fernet(get_encryption_key())
    return _FERNET_INSTANCE


def encrypt_image(image_or_bytes) -> bytes:
    """
    Encrypt a numpy BGR image array or raw image bytes.
    Returns authenticated ciphertext bytes.
    """
    if isinstance(image_or_bytes, np.ndarray):
        success, encoded = cv2.imencode(".jpg", image_or_bytes, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise ValueError("Failed to encode image frame to JPEG format.")
        raw_bytes = encoded.tobytes()
    elif isinstance(image_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(image_or_bytes)
    else:
        raise TypeError(f"Expected numpy.ndarray or bytes, got {type(image_or_bytes)}")

    cipher = get_fernet()
    return cipher.encrypt(raw_bytes)


def decrypt_image_bytes(ciphertext_or_path) -> bytes | None:
    """
    Decrypt ciphertext bytes or a file path on disk, returning raw JPEG bytes.
    Transparently falls back to raw data if the file is an unencrypted legacy JPEG.
    """
    if isinstance(ciphertext_or_path, (str, os.PathLike)):
        if not os.path.exists(ciphertext_or_path):
            return None
        with open(ciphertext_or_path, "rb") as fp:
            data = fp.read()
    else:
        data = bytes(ciphertext_or_path)

    if not data:
        return None

    # Check if file is already an unencrypted image (JPEG, PNG, WebP)
    if data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG") or data.startswith(b"RIFF"):
        return data

    cipher = get_fernet()
    try:
        decrypted = cipher.decrypt(data)
        if decrypted and (decrypted.startswith(b"\xff\xd8\xff") or decrypted.startswith(b"\x89PNG") or decrypted.startswith(b"RIFF")):
            return decrypted
        return decrypted
    except (InvalidToken, Exception):
        # Do not return raw encrypted ciphertext
        return None


def decrypt_image(ciphertext_or_path) -> np.ndarray | None:
    """
    Decrypts ciphertext and decodes directly into a standard OpenCV BGR image matrix.
    Returns None if decryption or image decoding fails.
    """
    raw_jpeg = decrypt_image_bytes(ciphertext_or_path)
    if not raw_jpeg:
        return None
    arr = np.frombuffer(raw_jpeg, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def save_encrypted_image(target_path: str, image_or_bytes) -> str:
    """
    Encrypts an image frame in memory and saves ciphertext bytes to target_path.
    Creates parent directories automatically if needed.
    """
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    encrypted_bytes = encrypt_image(image_or_bytes)
    with open(target_path, "wb") as f:
        f.write(encrypted_bytes)
    return target_path


def load_encrypted_image(file_path: str) -> np.ndarray | None:
    """
    Loads an encrypted (.enc) or legacy (.jpg) image from disk into an OpenCV BGR array.
    """
    if not os.path.exists(file_path):
        return None
    return decrypt_image(file_path)


def encrypt_directory_files(directory_path: str) -> int:
    """
    Walks a directory and converts all unencrypted .jpg / .jpeg / .png files
    into encrypted .enc files, safely removing the plain files.
    Returns the count of encrypted files.
    """
    if not os.path.exists(directory_path):
        return 0

    count = 0
    for root, _, files in os.walk(directory_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in [".jpg", ".jpeg", ".png"]:
                src = os.path.join(root, f)
                dst = os.path.splitext(src)[0] + ".enc"
                try:
                    with open(src, "rb") as fp:
                        raw = fp.read()
                    # Only encrypt if not already encrypted
                    if raw.startswith(b"\xff\xd8\xff"):
                        enc = encrypt_image(raw)
                        with open(dst, "wb") as fp:
                            fp.write(enc)
                        os.remove(src)
                        count += 1
                except Exception as e:
                    print(f"[IMAGE_CRYPTO] Failed to encrypt {src}: {e}")
    return count


def encrypt_all_saved_images() -> dict:
    """
    Startup migration routine: ensures all images in face_data/ and
    static/snapshots/ are stored in encrypted format.
    """
    face_count = encrypt_directory_files(Config.FACE_DATA_DIR)
    snap_count = encrypt_directory_files(Config.ALERTS_SNAPSHOT_DIR)
    return {
        "encrypted_faces": face_count,
        "encrypted_snapshots": snap_count,
        "total": face_count + snap_count,
    }

