"""Record the shipped page with real pointer input in headless Chromium.

Run make build, then python3 scripts/record_demos.py.
Requires the dev Playwright install, Chromium, and ffmpeg. No retraining.
"""
from pathlib import Path
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
FPS = 8
SEGMENTS = {7: "abc", 3: "abcdg"}
# Canvas coordinates are (row, column). These match the thin-stroke test glyphs.
STROKES = {
    7: [[(1, 3), (1, 10), (6, 10)], [(8, 10), (12, 10)]],
    3: [[(1, 3), (1, 10), (6, 10)], [(7, 3), (7, 10)],
        [(8, 10), (13, 10), (13, 3)]],
}


def record(page, digit, directory):
    page.goto((ROOT / "dist" / "index.html").as_uri())
    page.evaluate("document.fonts.ready")
    app = page.locator(".app")
    grid = page.locator(".grid14").bounding_box()
    frame = 0

    def capture(count=1):
        nonlocal frame
        for _ in range(count):
            app.screenshot(path=str(directory / f"{frame:03}.png"))
            frame += 1

    def point(row, col):
        return (grid["x"] + (col + 0.5) * grid["width"] / 14,
                grid["y"] + (row + 0.5) * grid["height"] / 14)

    capture(4)
    for stroke in STROKES[digit]:
        page.mouse.move(*point(*stroke[0]))
        page.mouse.down()
        capture()
        for (r0, c0), (r1, c1) in zip(stroke, stroke[1:]):
            steps = max(abs(r1 - r0), abs(c1 - c0))
            for step in range(1, steps + 1):
                page.mouse.move(*point(r0 + (r1 - r0) * step / steps,
                                       c0 + (c1 - c0) * step / steps))
                capture()
        page.mouse.up()
        capture()
    page.mouse.move(grid["x"] - 20, grid["y"])
    result = page.evaluate("""() => {
        const style = getComputedStyle(document.body);
        const read = name => Number(style.getPropertyValue('--' + name));
        return {
            digit: read('mnist_digit_dec'),
            segments: 'abcdefg'.split('').filter(s => read('mnist_seg_' + s)).join('')
        };
    }""")
    assert result == {"digit": digit, "segments": SEGMENTS[digit]}, result
    capture(16)
    return result


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / ".test-results"
    scratch.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 900, "height": 1400},
                                    device_scale_factor=1, reduced_motion="reduce")
            for digit in STROKES:
                with tempfile.TemporaryDirectory(dir=scratch) as temporary:
                    directory = Path(temporary)
                    result = record(page, digit, directory)
                    output = MEDIA / f"draw-{digit}.gif"
                    subprocess.run([
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-framerate", str(FPS), "-i", str(directory / "%03d.png"),
                        "-filter_complex",
                        "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
                        "[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                        "-loop", "0", str(output),
                    ], check=True)
                    assert output.stat().st_size < 2_000_000, "GIF exceeds 2 MB"
                    print(f"{output.relative_to(ROOT)}: {output.stat().st_size} bytes; {result}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
