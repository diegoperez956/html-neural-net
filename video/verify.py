#!/usr/bin/env python3
"""Verify the rendered artifact. Optional OCR reads actual caption pixels."""

import argparse
import ctypes
import ctypes.util
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from video.render import probe  # noqa: E402


def normalize(text):
    return "".join(re.findall(r"[a-z0-9]+", text.lower()))


def check_captions(output):
    from PIL import Image, ImageOps

    library = ctypes.util.find_library("tesseract")
    if not library:
        raise RuntimeError("OCR requested but libtesseract is unavailable")
    lib = ctypes.CDLL(library)
    ptr = ctypes.c_void_p
    lib.TessBaseAPICreate.restype = ptr
    lib.TessBaseAPIInit3.argtypes = [ptr, ctypes.c_char_p, ctypes.c_char_p]
    lib.TessBaseAPIInit3.restype = ctypes.c_int
    lib.TessBaseAPISetPageSegMode.argtypes = [ptr, ctypes.c_int]
    lib.TessBaseAPISetImage.argtypes = [
        ptr,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.TessBaseAPISetSourceResolution.argtypes = [ptr, ctypes.c_int]
    lib.TessBaseAPIGetUTF8Text.argtypes = [ptr]
    lib.TessBaseAPIGetUTF8Text.restype = ptr
    lib.TessDeleteText.argtypes = [ptr]
    lib.TessBaseAPIDelete.argtypes = [ptr]
    api = lib.TessBaseAPICreate()
    results = []
    try:
        # Let Tesseract find its packaged language data. No download occurs.
        if lib.TessBaseAPIInit3(api, None, b"eng"):
            raise RuntimeError("Tesseract English data unavailable")
        lib.TessBaseAPISetPageSegMode(api, 6)
        for file in sorted((output / "notes").glob("*.json")):
            chapter = json.loads(file.read_text())
            number = chapter["chapter"]
            frame = output / "notes/frames" / f"{number:02d}-step-07.png"
            note_index = 6
            if not frame.exists():
                frame = output / "notes/frames" / f"{number:02d}-step-03.png"
                note_index = 2
            if not frame.exists():
                frame = output / "notes/frames" / f"{number:02d}-end.png"
                note_index = -1
            image = Image.open(frame).convert("RGB")
            w, h = image.size
            crop = image.crop((0, int(h * 0.80), w, int(h * 0.946)))
            crop = ImageOps.autocontrast(ImageOps.invert(crop.convert("L"))).convert(
                "RGB"
            )
            raw = (ctypes.c_ubyte * len(crop.tobytes())).from_buffer_copy(
                crop.tobytes()
            )
            lib.TessBaseAPISetImage(
                api, raw, crop.width, crop.height, 3, crop.width * 3
            )
            lib.TessBaseAPISetSourceResolution(api, 150)
            value = lib.TessBaseAPIGetUTF8Text(api)
            try:
                actual = ctypes.string_at(value).decode("utf-8") if value else ""
            finally:
                if value:
                    lib.TessDeleteText(value)
            expected = chapter["notes"][note_index]["text"]
            similarity = SequenceMatcher(
                None, normalize(expected), normalize(actual)
            ).ratio()
            results.append(
                {
                    "chapter": number,
                    "frame": str(frame.relative_to(ROOT)),
                    "similarity": similarity,
                    "expected": expected,
                    "ocr": actual.strip(),
                }
            )
    finally:
        lib.TessBaseAPIDelete(api)
    (output / "caption-ocr.json").write_text(json.dumps(results, indent=2))
    failed = [row for row in results if row["similarity"] < 0.90]
    if failed:
        raise AssertionError(
            f"Caption OCR needs review: {[r['chapter'] for r in failed]}"
        )
    return {
        "frames": len(results),
        "minimum_similarity": min(r["similarity"] for r in results),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decode", action="store_true", help="decode every frame with ffmpeg"
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="read one rendered caption per chapter with local Tesseract",
    )
    parser.add_argument(
        "--manifest",
        default="video/output/manifest.json",
        help="manifest to verify, e.g. video/output/voiced/manifest.json",
    )
    args = parser.parse_args()
    manifest_path = ROOT / args.manifest
    output = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    path = ROOT / manifest["file"]
    expect_audio = manifest.get("audio", False)
    media = probe(path)
    streams = media["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    audio_streams = [s for s in streams if s["codec_type"] == "audio"]
    if expect_audio:
        assert len(audio_streams) == 1, "Expected exactly one audio stream"
        assert audio_streams[0]["codec_name"] == "aac"
    else:
        assert not audio_streams, "Expected no audio stream"
    assert (video["width"], video["height"]) == (1920, 1080)
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    expected_chapters = len(manifest["chapters"])
    assert len(media["chapters"]) == expected_chapters
    assert abs(float(media["format"]["duration"]) - manifest["duration_seconds"]) < 0.1
    notes = [json.loads(p.read_text()) for p in (output / "notes").glob("*.json")]
    assert len(notes) == expected_chapters
    assert all(not n["layout_warnings"] for n in notes)
    assert all(n["cache_key"] == manifest["cache_key"] for n in notes)
    report = {
        "file": manifest["file"],
        "duration": manifest["duration"],
        "resolution": "1920x1080",
        "audio": expect_audio,
        "chapters": expected_chapters,
        "on_screen_explanations": sum(len(n["notes"]) for n in notes),
        "out_of_frame_or_text_overlap_warnings": 0,
        "full_decode": False,
        "caption_ocr": None,
        "mean_volume_db": None,
        "limits": "Geometry and OCR checks do not replace human visual review.",
    }
    if args.decode:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-xerror",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-an",
                "-f",
                "null",
                "-",
            ],
            check=True,
            timeout=600,
        )
        report["full_decode"] = True
    if expect_audio:
        volume = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-i",
                str(path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", volume.stderr)
        assert match, "ffmpeg volumedetect did not report a mean volume"
        mean_db = float(match.group(1))
        assert mean_db > -40, f"Audio track appears silent: {mean_db} dB"
        report["mean_volume_db"] = mean_db
    if args.ocr:
        report["caption_ocr"] = check_captions(output)
    (output / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
