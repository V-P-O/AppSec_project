import os
import secrets
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image, ImageOps

def _starts_with(data: bytes, sig: bytes) -> bool:
    return data[:len(sig)] == sig

def sniff_kind(head: bytes) -> str | None:
    # PNG
    if _starts_with(head, b"\x89PNG\r\n\x1a\n"):
        return "png"
    # JPEG
    if _starts_with(head, b"\xff\xd8\xff"):
        return "jpg"
    # GIF
    if _starts_with(head, b"GIF87a") or _starts_with(head, b"GIF89a"):
        return "gif"
    # WEBP: RIFF....WEBP
    if len(head) >= 12 and head[0:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    # MP4: ... 'ftyp'
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4"
    # WEBM: EBML header
    if _starts_with(head, b"\x1a\x45\xdf\xa3"):
        return "webm"
    return None

def media_type_from_kind(kind: str) -> str:
    if kind in {"png", "jpg", "webp"}:
        return "image"
    if kind == "gif":
        return "gif"
    return "video"

def save_upload_hardened(file_storage):
    """
    Returns dict with:
      file_path (absolute path), kind, media_type, original_filename, file_size_bytes
    or None on rejection.
    """
    original = (file_storage.filename or "").strip()
    if not original:
        return None

    # extension allowlist (fast pre-check, not trusted)
    safe_name = secure_filename(original)
    if "." not in safe_name:
        return None
    ext = safe_name.rsplit(".", 1)[1].lower()

    allowed = (current_app.config["ALLOWED_IMAGE_EXT"]
               | current_app.config["ALLOWED_GIF_EXT"]
               | current_app.config["ALLOWED_VIDEO_EXT"])
    if ext not in allowed:
        return None

    # read header to sniff actual file type (trust this more)
    head = file_storage.stream.read(4096)
    file_storage.stream.seek(0)

    kind = sniff_kind(head)
    if not kind:
        return None

    # enforce that sniffed kind matches allowed sets
    if kind in {"png", "jpg", "webp"} and kind not in current_app.config["ALLOWED_IMAGE_EXT"]:
        return None
    if kind == "gif" and kind not in current_app.config["ALLOWED_GIF_EXT"]:
        return None
    if kind in {"mp4", "webm"} and kind not in current_app.config["ALLOWED_VIDEO_EXT"]:
        return None

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    rnd = secrets.token_hex(16)
    base = secure_filename(safe_name.rsplit(".", 1)[0])[:40] or "upload"
    out_name = f"{base}_{rnd}.{kind}"
    abs_path = os.path.join(upload_dir, out_name)

    # IMAGE HARDENING: re-encode (strips metadata, fixes content-type ambiguity)
    if kind in {"png", "jpg", "webp"}:
        return _save_reencoded_image(file_storage, abs_path, kind, original)

    # GIF / VIDEO: store as-is (see notes below)
    file_storage.save(abs_path)
    size = os.path.getsize(abs_path)

    return {
        "file_path": abs_path,
        "kind": kind,
        "media_type": media_type_from_kind(kind),
        "original_filename": original,
        "file_size_bytes": size,
    }

def _save_reencoded_image(file_storage, abs_path: str, kind: str, original: str):
    # Prevent decompression bomb
    Image.MAX_IMAGE_PIXELS = 20_000_000  # tune (e.g. 20MP)

    img = Image.open(file_storage.stream)
    img.verify()  # validates structure
    file_storage.stream.seek(0)

    img = Image.open(file_storage.stream)

    # Normalize orientation (EXIF) then drop metadata by re-encoding
    img = ImageOps.exif_transpose(img)

    # Convert to a safe mode
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    # Enforce max dimensions (optional but recommended)
    max_side = 4000
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))

    # Save WITHOUT EXIF/metadata
    save_kwargs = {}
    if kind == "jpg":
        if img.mode == "RGBA":
            img = img.convert("RGB")
        save_kwargs = {"quality": 85, "optimize": True}
        img.save(abs_path, format="JPEG", **save_kwargs)
    elif kind == "png":
        img.save(abs_path, format="PNG", optimize=True)
    elif kind == "webp":
        img.save(abs_path, format="WEBP", quality=85, method=6)
    else:
        return None

    size = os.path.getsize(abs_path)
    return {
        "file_path": abs_path,
        "kind": kind,
        "media_type": "image",
        "original_filename": original,
        "file_size_bytes": size,
    }