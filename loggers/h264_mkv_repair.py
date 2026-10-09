"""Repair empty length-prefixed H.264 NAL units in FFmpeg-produced Matroska.

Some RTSP encoders emit zero-length NAL entries around an IDR frame. These
produce valid-looking MKV files that standard H.264 decoders cannot open.
Only empty NAL units are removed; the original video packets are not decoded
or re-encoded. Original files are kept when any repair is performed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Matroska master elements needed to descend to video blocks. Elements not in
# this set are carried through byte-for-byte. Matroska seeking indices are
# rebuilt by FFmpeg after removing bytes from blocks.
_MASTER = {
    0x1A45DFA3, 0x18538067, 0x1549A966, 0x1654AE6B, 0xAE, 0xE0, 0xE1,
    0x1F43B675, 0xA0, 0x1254C367, 0x7373, 0x67C8, 0x1941A469,
}
_INDEX = {0x114D9B74, 0x1C53BB6B}  # SeekHead, Cues (offsets become invalid)
_MAX_BYTES = 256 * 1024 * 1024


def _vint(data: bytes, pos: int, identifier: bool = False) -> tuple[int, int]:
    if pos >= len(data):
        raise ValueError("Truncated EBML integer")
    length, mask = 1, 0x80
    while not (data[pos] & mask):
        length += 1
        mask >>= 1
        if length > 8:
            raise ValueError("Invalid EBML integer")
    if pos + length > len(data):
        raise ValueError("Truncated EBML integer")
    value = int.from_bytes(data[pos:pos + length], "big")
    if not identifier:
        value &= (1 << (7 * length)) - 1
    return value, length


def _size_bytes(size: int, min_length: int) -> bytes:
    length = min_length
    while size >= (1 << (7 * length)) - 1:
        length += 1
        if length > 8:
            raise ValueError("EBML element is too large")
    return ((1 << (7 * length)) | size).to_bytes(length, "big")


def _clean_block(block: bytes) -> tuple[bytes, int]:
    # Track number VINT + signed relative time (2 bytes) + flags (1 byte).
    _, track_len = _vint(block, 0)
    start = track_len + 3
    if len(block) < start:
        raise ValueError("Truncated Matroska Block")
    if block[start - 1] & 0x06:
        raise ValueError("Laced Matroska blocks are not supported")
    output = bytearray(block[:start])
    removed = 0
    pos = start
    while pos < len(block):
        if len(block) - pos < 4:
            raise ValueError("Truncated H.264 NAL length")
        length = int.from_bytes(block[pos:pos + 4], "big")
        pos += 4
        if length == 0:
            removed += 1
            continue
        if length > len(block) - pos:
            raise ValueError("H.264 NAL length exceeds packet")
        output.extend(length.to_bytes(4, "big"))
        output.extend(block[pos:pos + length])
        pos += length
    return bytes(output), removed


def strip_empty_h264_nals(mkv: bytes) -> tuple[bytes, int]:
    """Return updated Matroska and empty NAL count, or raise on bad structure.

    This is intentionally limited to non-laced single-video-stream captures.
    FFmpeg remuxes the result to regenerate SeekHead/Cues and normalize DTS.
    """
    count = 0

    def walk(start: int, end: int) -> bytes:
        nonlocal count
        output = bytearray()
        pos = start
        while pos < end:
            element, id_len = _vint(mkv, pos, identifier=True)
            size, size_len = _vint(mkv, pos + id_len)
            body_start = pos + id_len + size_len
            unknown = size == (1 << (7 * size_len)) - 1
            body_end = end if unknown else body_start + size
            if body_end > end:
                raise ValueError("Matroska element exceeds parent bounds")
            if element not in _INDEX:
                if element in _MASTER:
                    body = walk(body_start, body_end)
                elif element in (0xA3, 0xA1):  # SimpleBlock / Block
                    body, removed = _clean_block(mkv[body_start:body_end])
                    count += removed
                else:
                    body = mkv[body_start:body_end]
                output.extend(mkv[pos:pos + id_len])
                output.extend(mkv[pos + id_len:body_start] if unknown
                              else _size_bytes(len(body), size_len))
                output.extend(body)
            pos = body_end
        return bytes(output)

    return walk(0, len(mkv)), count


def repair_recording(path: Path, ffmpeg_bin: str = "ffmpeg") -> dict:
    """Verify and, if needed, repair a recorded MKV; never overwrite unverified data.

    Keep camera_original.mkv if repaired. Returns diagnostics; any failure
    raises, leaving camera.mkv unmodified and temporary files removed.
    """
    path = Path(path)
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("Recording exceeds 256 MiB repair safety limit")
    source = path.read_bytes()
    cleaned, removed = strip_empty_h264_nals(source)
    temp = path.with_name("camera_repair_input.mkv")
    repaired = path.with_name("camera_repair_output.mkv")
    try:
        if removed:
            temp.write_bytes(cleaned)
            # setts only increases *duplicate* PTS/DTS; packet timing is
            # otherwise retained. This does not synchronize capture to robot.
            result = subprocess.run(
                [ffmpeg_bin, "-nostdin", "-hide_banner", "-v", "error",
                 "-y", "-i", str(temp), "-map", "0:v:0", "-an",
                 "-c:v", "copy", "-bsf:v",
                 "setts=pts=max(PTS\\,PREV_OUTPTS+1):dts=max(DTS\\,PREV_OUTDTS+1)",
                 "-f", "matroska", str(repaired)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode:
                raise RuntimeError("FFmpeg video remux failed: " + result.stderr[-900:])
        candidate = repaired if removed else path
        decoded = subprocess.run(
            [ffmpeg_bin, "-nostdin", "-hide_banner", "-v", "error",
             "-xerror", "-progress", "pipe:1", "-i", str(candidate), "-map", "0:v:0",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        if decoded.returncode:
            raise RuntimeError("Recorded video decode failed: " + decoded.stderr[-900:])
        # FFmpeg can exit successfully without emitting a decoded frame.
        counts = [int(line[6:].strip()) for line in decoded.stdout.splitlines()
                  if line.startswith("frame=") and line[6:].strip().isdigit()]
        decoded_frames = max(counts, default=0)
        if decoded_frames < 1:
            raise RuntimeError("Video decode produced zero frames")
        if removed:
            original = path.with_name("camera_original.mkv")
            if original.exists():
                raise FileExistsError("Original camera backup already exists")
            shutil.copy2(path, original)
            repaired.replace(path)
        return {
            "validation": "ffmpeg_decoded",
            "decoded_frames": decoded_frames,
            "empty_h264_nals_removed": removed,
            "original_path": str(path.with_name("camera_original.mkv")) if removed else None,
            "note": "Video timestamps are host/RTSP estimates, not synchronized capture times.",
        }
    finally:
        temp.unlink(missing_ok=True)
        repaired.unlink(missing_ok=True)
