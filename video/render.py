#!/usr/bin/env python3
"""Render resumable silent Manim chapters, then assemble a chaptered MP4."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-show_chapters",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )


def timestamp(seconds):
    value = int(seconds)
    return f"{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}"


def validate(path, width, height, fps, audio=False):
    result = probe(path)
    streams = result["streams"]
    video_streams = [s for s in streams if s["codec_type"] == "video"]
    audio_streams = [s for s in streams if s["codec_type"] == "audio"]
    assert len(video_streams) == 1, "Expected exactly one video stream"
    if audio:
        assert len(audio_streams) == 1, "Expected exactly one audio stream"
    else:
        assert not audio_streams, "Expected no audio stream"
    stream = video_streams[0]
    assert (stream["width"], stream["height"]) == (width, height)
    numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
    assert abs(numerator / denominator - fps) < 0.01
    duration = float(result["format"]["duration"])
    assert duration > 0
    return duration


def assemble(output, chapters, key, width, height, fps, audio=False, final=None):
    manifest = []
    notes = (
        [
            "# Follow the narrated htmlnet study video",
            "",
            "These are the explanations spoken and shown beside the animations.",
            "",
        ]
        if audio
        else [
            "# Follow the silent htmlnet study video",
            "",
            "There is no voice or music. These are the explanations shown beside the animations.",
            "",
        ]
    )
    metadata = [
        ";FFMETADATA1",
        "title=How a neural network runs in CSS",
        "artist=htmlnet study",
    ]
    files = []
    offset = 0.0
    audio_codecs = set()
    for number, (slug, title) in enumerate(chapters, 1):
        path = output / "chapters" / f"{number:02d}-{slug}.mp4"
        data_path = output / "notes" / f"{number:02d}-{slug}.json"
        if not path.exists() or not data_path.exists():
            return None
        data = json.loads(data_path.read_text())
        if data.get("cache_key") != key:
            return None
        duration = validate(path, width, height, fps, audio=audio)
        assert not data["layout_warnings"], f"Out-of-frame objects in chapter {number}"
        files.append(f"file '{path.resolve().as_posix()}'")
        if audio:
            chapter_streams = probe(path)["streams"]
            astream = next(s for s in chapter_streams if s["codec_type"] == "audio")
            audio_codecs.add((astream["codec_name"], astream.get("sample_rate")))
        metadata.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={round(offset * 1000)}",
                f"END={round((offset + duration) * 1000)}",
                f"title={number:02d}. {title}",
            ]
        )
        notes.extend([f"## {timestamp(offset)} · {number:02d}. {title}", ""])
        for note in data["notes"]:
            notes.extend(
                [f"**{timestamp(offset + note['start'])}.** {note['text']}", ""]
            )
        manifest.append(
            {
                "chapter": number,
                "title": title,
                "path": str(path.relative_to(ROOT)),
                "start": offset,
                "duration": duration,
            }
        )
        offset += duration
    (output / "concat.txt").write_text("\n".join(files) + "\n")
    (output / "chapters.ffmeta").write_text("\n".join(metadata) + "\n")
    (output / "follow-along.md").write_text("\n".join(notes))
    final = final or (output / "htmlnet-study.mp4")
    audio_args = (
        ["-map", "0:a:0", "-c:a", "copy" if len(audio_codecs) == 1 else "aac"]
        if audio
        else ["-an"]
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(output / "concat.txt"),
            "-f",
            "ffmetadata",
            "-i",
            str(output / "chapters.ffmeta"),
            "-map",
            "0:v:0",
            *audio_args,
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
    )
    result = probe(final)
    final_audio = [s for s in result["streams"] if s["codec_type"] == "audio"]
    if audio:
        assert len(final_audio) == 1
    else:
        assert not final_audio
    assert len(result["chapters"]) == len(chapters)
    actual = float(result["format"]["duration"])
    assert abs(actual - offset) < 1
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "file": str(final.relative_to(ROOT)),
                "duration_seconds": actual,
                "duration": timestamp(actual),
                "width": width,
                "height": height,
                "fps": fps,
                "audio": audio,
                "cache_key": key,
                "chapters": manifest,
            },
            indent=2,
        )
    )
    print(
        f"COMPLETE {final}\n{timestamp(actual)} · {width}×{height} · {fps} fps · "
        + (f"audio {final_audio[0]['codec_name']}" if audio else "no audio"),
        flush=True,
    )
    return final


def contact_sheets(output, chapters):
    from PIL import Image, ImageDraw

    for start in range(0, len(chapters), 14):
        selected = list(enumerate(chapters, 1))[start : start + 14]
        sheet = Image.new("RGB", (1920, 4 * 302), "#282828")
        draw = ImageDraw.Draw(sheet)
        for j, (number, (slug, title)) in enumerate(selected):
            directory = output / "notes/frames"
            candidates = [
                directory / f"{number:02d}-step-07.png",
                directory / f"{number:02d}-step-03.png",
                directory / f"{number:02d}-end.png",
            ]
            path = next((p for p in candidates if p.exists()), None)
            if path:
                image = Image.open(path).convert("RGB")
                image.thumbnail((480, 270))
                x, y = (j % 4) * 480, (j // 4) * 302
                sheet.paste(image, (x, y))
                draw.text((x + 8, y + 274), f"{number:02d} {title}", fill="#ebdbb2")
        sheet.save(output / f"contact-{start // 14 + 1}.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="short 960×540 previews, not the final lesson",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="reproduce the original 28-chapter silent htmlnet-study.mp4",
    )
    parser.add_argument(
        "--chapters", help="comma-separated chapter numbers, such as 1,8,16"
    )
    parser.add_argument(
        "--force", action="store_true", help="rerender selected chapters"
    )
    parser.add_argument("--bundle-only", action="store_true")
    args = parser.parse_args()
    from manim import tempconfig
    from video.lesson import ALL_CHAPTERS, CHAPTERS, CSSStudy
    from video.model import source_digest

    chapters = ALL_CHAPTERS if args.silent else CHAPTERS
    voice_on = not args.preview and not args.silent
    final_path = None
    if args.preview:
        width, height, fps, pace = 960, 540, 12, 0.08
        output = ROOT / "video" / ".cache/preview"
    elif args.silent:
        width, height, fps, pace = 1920, 1080, 24, 1.0
        output = ROOT / "video" / "output"
    else:
        width, height, fps, pace = 1920, 1080, 24, 0.6
        output = ROOT / "video" / "output" / "voiced"
        final_path = ROOT / "video" / "output" / "htmlnet-study-15.mp4"
    output.mkdir(parents=True, exist_ok=True)
    (output / "chapters").mkdir(exist_ok=True)
    notes_dir = output / "notes"
    code = b"\0".join(
        (ROOT / "video" / p).read_bytes()
        for p in ("lesson.py", "visuals.py", "model.py", "render.py", "voice.py")
    )
    key = hashlib.sha256(
        code
        + source_digest().encode()
        + f"{width}:{height}:{fps}:{pace}:{voice_on}".encode()
    ).hexdigest()
    selected = (
        [int(x) for x in args.chapters.split(",")]
        if args.chapters
        else list(range(1, len(chapters) + 1))
    )
    assert selected and all(1 <= n <= len(chapters) for n in selected)
    if not args.bundle_only:
        for number in selected:
            slug, title = chapters[number - 1]
            filename = f"{number:02d}-{slug}"
            target = output / "chapters" / (filename + ".mp4")
            data_path = notes_dir / (filename + ".json")
            if not args.force and target.exists() and data_path.exists():
                existing = json.loads(data_path.read_text())
                if existing.get("cache_key") == key and not existing.get(
                    "layout_warnings"
                ):
                    validate(target, width, height, fps, audio=voice_on)
                    print(f"SKIP {filename}: verified cached chapter", flush=True)
                    continue
            print(f"RENDER {number:02d}/{len(chapters)} {title}", flush=True)
            with tempconfig(
                {
                    "pixel_width": width,
                    "pixel_height": height,
                    "frame_rate": fps,
                    "frame_width": 16,
                    "frame_height": 9,
                    "background_color": "#282828",
                    "renderer": "cairo",
                    "media_dir": str(ROOT / "video/.cache/manim"),
                    "output_file": filename,
                    "write_to_movie": True,
                    "save_last_frame": False,
                    "preview": False,
                    "progress_bar": "none",
                    "verbosity": "WARNING",
                    "max_files_cached": 1000,
                    # Manim's partial-movie cache sets skip_animations on a hit and
                    # add_sound() silently drops narration while it is set.
                    # render.py has its own chapter-level cache, so disable it.
                    "disable_caching": True,
                }
            ):
                scene = CSSStudy(
                    chapter=number, pace=pace, notes_dir=notes_dir, voice=voice_on
                )
                scene.render()
                movie = Path(scene.renderer.file_writer.movie_file_path)
                shutil.copy2(movie, target)
            duration = validate(target, width, height, fps, audio=voice_on)
            data = json.loads(data_path.read_text())
            data["cache_key"] = key
            data["file_duration"] = duration
            data_path.write_text(json.dumps(data, indent=2))
            print(
                f"DONE {filename}: {duration:.2f}s, {len(data['notes'])} explanations, {len(data['layout_warnings'])} bounds warnings",
                flush=True,
            )
            if data["layout_warnings"]:
                print(json.dumps(data["layout_warnings"], indent=2), flush=True)
    contact_sheets(output, chapters)
    final = assemble(
        output, chapters, key, width, height, fps, audio=voice_on, final=final_path
    )
    if args.bundle_only and final is None:
        raise SystemExit(
            "Cannot assemble: some chapters are missing, stale, or invalid"
        )
    if final is None:
        print(
            "Selected chapters rendered. Full movie needs all chapters from this source revision.",
            flush=True,
        )


if __name__ == "__main__":
    main()
