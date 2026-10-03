# htmlnet study video

The primary video is **narrated, 15 minutes 33 seconds**, at 1920×1080 and 24
fps. It has 14 embedded chapter markers, 115 on-screen explanations, and an
AAC voice track (Kokoro `am_michael`) reading each caption aloud. It is a
14-chapter cut of the full 28-chapter lesson — see `scenes.md` for which
chapters it keeps.

A separate **silent, 50-minute, 28-chapter** cut still exists and still
renders from the same source; see [Silent 50-minute cut](#silent-50-minute-cut)
below.

## Watch and follow along

- [Narrated MP4](output/htmlnet-study-15.mp4)
- [Timestamped follow-along notes](output/voiced/follow-along.md)
- [Individual chapter files](output/voiced/chapters/)
- [Chapter manifest](output/voiced/manifest.json)
- [Next-chat knowledge-test handoff](../docs/STUDY_HANDOFF.md)

```bash
xdg-open video/output/htmlnet-study-15.mp4
```

The animation shows changing values, moving carries, binary words, XOR hidden
neurons, stroke processing, and a complete score trace. The code panels
either quote generated CSS or identify a line-wrapped or shortened source
excerpt. Gate pulses explain dependencies; they are not measurements of
browser evaluation order or timing.

Manim renders the teaching video in Python; Kokoro (`kokoro-onnx`, ONNX
Runtime backend, no torch) synthesizes narration from the same caption text
in `lesson.py`. The actual deployed network still runs in HTML and CSS. Open
`dist/no-js.html` to use the fully script-free build, or `dist/index.html`
for optional drag input.

## Reproduce the render

The existing local Manim environment did not have `kokoro-onnx`/`soundfile`
installed, so this run added them to the existing
`/home/diego/iceberg/.venv` (which already had `manim==0.20.1`) rather than
building a fresh `video/.venv`:

```bash
/home/diego/iceberg/.venv/bin/python -m pip install kokoro-onnx soundfile
/home/diego/iceberg/.venv/bin/python video/render.py
```

For a separate environment, install the requirements under
`video/requirements.txt`. Use Manim Community 0.20.1, not ManimGL. The
source uses Pango text and explicit math layouts rather than LaTeX, so it
does not require a TeX installation. It uses the installed Noto Sans and
JetBrains Mono fonts. FFmpeg and ffprobe must be on the path.

The Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`, about 340 MB
combined) download once into `video/.cache/kokoro/` on first narrated
render; see `video/voice.py`.

```bash
python video/render.py --preview                # fast silent preview, 14-chapter cut
python video/render.py --preview --chapters 8,16 # preview a subset
python video/render.py --chapters 8,16           # final voiced render of a subset
python video/render.py                           # full voiced 14-chapter render (default)
python video/render.py --bundle-only             # just reassemble from cached chapters
python video/render.py --silent                  # reproduce the original 28-chapter silent cut
```

The renderer resumes completed chapters only when their source fingerprint
and render settings match — the cache key covers `lesson.py`, `visuals.py`,
`model.py`, `render.py`, `voice.py`, the model source digest, and the
resolution/fps/pace/voice settings. It checks each cached file before
reusing it. Use `--force` to regenerate selected chapters. A subset render
does not claim the complete movie exists until all chapters are ready.

Final voiced files live under `video/output/voiced/`, with the assembled
movie at `video/output/htmlnet-study-15.mp4`. The silent cut's files live
under `video/output/` directly, as `htmlnet-study.mp4`. Short previews live
under `video/.cache/preview/`. Those generated directories, plus
`video/.cache/kokoro/` and `video/.cache/voice/` (the per-line narration WAV
cache), are ignored by Git. Source changes or model changes invalidate the
cached chapters.

## Files

- `scenes.md` is the scene plan for all 28 chapters. Its initial duration
  estimates are superseded by the actual durations in
  `output/voiced/manifest.json` (or `output/manifest.json` for the silent
  cut).
- `model.py` calculates the independent arithmetic and reads the saved model.
  It loads the actual drawing fixtures from the runtime test source.
- `visuals.py` defines reusable diagrams, words, grids, and code panels.
- `lesson.py` defines all 28 chapter scenes and on-screen explanations
  (`ALL_CHAPTERS`), plus the 14-chapter narrated subset (`CHAPTERS`) and the
  narration timing (`note`/`step`, gated by a `voice` flag).
- `voice.py` synthesizes narration WAVs with Kokoro, cached by
  voice+speed+text. `python video/voice.py "some text"` synths one line.
- `render.py` renders, caches, validates, and joins the chapters, silent or
  voiced.
- `verify.py` checks a completed movie (pass `--manifest` to pick which one)
  and can OCR its actual caption pixels.
- `../tests/test_video_math.py` checks the examples and their mathematical
  assumptions.

The numeric examples are tied to the currently saved weights. If you retrain,
update the study material and its tests rather than silently keep an old video
next to new model results. Rendering never changes the weight files.

## Verification

```bash
make test
python video/verify.py --decode --manifest video/output/voiced/manifest.json
# Optional local OCR, when libtesseract and English language data are installed:
python video/verify.py --decode --ocr --manifest video/output/voiced/manifest.json
```

The renderer checks stable-frame bounds and text collisions. It writes
keyframes under `output/voiced/notes/frames/` and contact sheets under
`output/voiced/contact-*.png`. The verifier checks the finished file's
codec, dimensions, duration, chapter markers, and (when the manifest says
`"audio": true`) that there is exactly one AAC audio stream whose mean
volume is above -40 dB, i.e. not silent. `--decode` decodes every frame with
FFmpeg. OCR reads one real caption image per chapter and compares it with
the intended text. These checks do not replace human judgment about visual
taste, narration quality, or pacing — nobody has listened to the narration
end to end; duration-per-word and non-silence checks stand in for that.

## Silent 50-minute cut

`video/render.py --silent` reproduces the original, unnarrated 28-chapter
lesson at `video/output/htmlnet-study.mp4` (50 minutes 5 seconds, 252
on-screen explanations, no audio track). It is not re-rendered by default;
run the command above if you need to rebuild it. Verify it with
`python video/verify.py --decode` (the default `--manifest` points at
`video/output/manifest.json`).
