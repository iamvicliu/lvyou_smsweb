"""Call-recording storage.

The board uploads one AMR file per call as ``multipart/form-data`` with the
form field named ``media`` (see the vendor's telrecordupload spec). This
module owns the on-disk layout and the AMR -> MP3 transcode:

* browsers other than Safari cannot play AMR, so a converted MP3 is what the
  call list actually streams,
* the AMR original is kept because it is the board's evidence file and is
  five to ten times smaller.

Everything lives under ``<data dir>/recordings`` so it survives container
rebuilds (the data dir is the bind mount).
"""

from __future__ import annotations

import email
import logging
import os
import re
import shutil
import subprocess
import uuid
from email.policy import HTTP
from pathlib import Path
from typing import Optional, Tuple

from backend.config import DBPATH

logger = logging.getLogger("board-manager")

# 32 kbps AMR is ~4 KB/s, so 8 MB is well above the 60 s the firmware caps a
# recording at. The limit exists to keep a broken client from filling the N1.
MAX_BYTES = int(os.environ.get("BMRECORDINGMAX", str(8 * 1024 * 1024)))
AMR_MAGIC = b"#!AMR\n"

_SAFE_DEV = re.compile(r"[^0-9A-Za-z_-]")


def recordings_root() -> Path:
    override = os.environ.get("BMRECORDINGSDIR", "").strip()
    root = Path(override) if override else Path(DBPATH).parent / "recordings"
    root.mkdir(parents=True, exist_ok=True)
    return root


def parse_media_part(body: bytes, content_type: str) -> Optional[Tuple[str, bytes]]:
    """Pull the ``media`` part out of a multipart body.

    Uses the stdlib parser instead of ``python-multipart`` so the image needs
    no extra dependency (and no extra build-time network access).
    """
    if "multipart/" not in (content_type or "").lower():
        return None
    try:
        raw = (
            b"Content-Type: " + content_type.encode("latin-1", "replace")
            + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
        )
        msg = email.message_from_bytes(raw, policy=HTTP)
        if not msg.is_multipart():
            return None
        for part in msg.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name != "media":
                continue
            filename = part.get_filename() or "recording.amr"
            payload = part.get_payload(decode=True) or b""
            return filename, payload
    except Exception:
        logger.debug("multipart parse failed", exc_info=True)
    return None


def store_amr(dev_id: str, payload: bytes) -> Path:
    """Write the original AMR under a random name; never trust the filename."""
    safe_dev = _SAFE_DEV.sub("_", (dev_id or "unknown")[:64]) or "unknown"
    stamp = uuid.uuid4().hex[:16]
    folder = recordings_root() / safe_dev
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stamp}.amr"
    path.write_bytes(payload)
    return path


def transcode_mp3(amr_path: Path) -> Optional[Path]:
    """Convert to MP3 next to the AMR. Returns None when ffmpeg is absent."""
    ffmpeg = ffmpeg_binary()
    if not ffmpeg:
        return None
    out = amr_path.with_suffix(".mp3")
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(amr_path), "-ac", "1", "-ar", "16000", "-b:a", "32k",
             str(out)],
            capture_output=True, timeout=30,
        )
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
        logger.warning("ffmpeg failed for %s: %s", amr_path.name,
                       (proc.stderr or b"")[:200].decode("utf-8", "replace"))
    except Exception:
        logger.warning("ffmpeg crashed for %s", amr_path.name, exc_info=True)
    try:
        out.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def ffmpeg_binary() -> str:
    """Locate ffmpeg, preferring one shipped beside the database.

    The N1 runs the panel from a small overlay partition, so ffmpeg lives on
    the data disk (``<data>/bin/ffmpeg``) instead of inside the image.
    """
    candidates = [
        os.environ.get("BMRECORDINGFFMPEG", "").strip(),
        str(Path(DBPATH).parent / "bin" / "ffmpeg"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("ffmpeg") or ""


# AMR-NB frame payload sizes in bytes, indexed by the frame's FT field.
# 15 is the "no data" frame: one header byte, no payload.
_AMR_FRAME_BYTES = (12, 13, 15, 17, 19, 20, 26, 31, 5, -1, -1, -1, -1, -1, -1, 0)


def amr_duration_seconds(path: Path) -> int:
    """Walk the AMR-NB frames; each frame is exactly 20 ms."""
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    if not data.startswith(AMR_MAGIC):
        return 0
    offset, frames = len(AMR_MAGIC), 0
    while offset < len(data):
        header = data[offset]
        if header & 0x83:
            break  # not a frame header: stop rather than count garbage
        size = _AMR_FRAME_BYTES[(header >> 3) & 0x0F]
        if size < 0:
            break
        offset += 1 + size
        frames += 1
    return int(round(frames * 0.02))
