"""Build the short README demo video from captured product screenshots."""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "public" / "demo"
OUTPUT = DEMO_DIR / "nyc311-pulse-demo.mp4"
COVER = DEMO_DIR / "nyc311-pulse-demo-cover.png"
SIZE = (1280, 960)
FPS = 15
BACKGROUND = (242, 241, 236)
INK = (25, 25, 23)
ORANGE = (246, 82, 48)

SLIDES = [
    ("01-home.png", "Research queue and fixed-snapshot overview"),
    ("02-filtered-queue.png", "Filter candidate episodes by borough"),
    ("03-signal-evidence.png", "Inspect explainable signal evidence"),
    ("04-signal-chart.png", "Compare observations with the calibrated baseline"),
    ("05-district-explore.png", "Explore all 59 Community Districts"),
    ("06-district-trend.png", "Load district-specific trends"),
    ("07-evaluation-lab.png", "Audit the release-gate protocol"),
    ("08-locked-metrics.png", "Review locked-test metrics and model selection"),
    ("09-methodology.png", "Trace methodology, privacy, and limitations"),
    ("10-data-quality.png", "Verify completeness and data quality"),
]


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_frame(source: Image.Image) -> Image.Image:
    frame = Image.new("RGB", SIZE, BACKGROUND)
    image = source.convert("RGB")
    image.thumbnail(SIZE, Image.Resampling.LANCZOS)
    frame.paste(image, ((SIZE[0] - image.width) // 2, (SIZE[1] - image.height) // 2))
    return frame


def caption_frame(source: Image.Image, caption: str) -> Image.Image:
    frame = fit_frame(source)
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((42, 842, 1238, 928), radius=24, fill=(25, 25, 23, 226))
    draw.ellipse((68, 871, 82, 885), fill=ORANGE + (255,))
    draw.text((102, 862), caption, fill=(255, 255, 255, 255), font=font(30, bold=True))
    return Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")


def title_frame(title: str, subtitle: str) -> Image.Image:
    frame = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(frame)
    draw.ellipse((80, 108, 132, 160), fill=INK)
    draw.text((95, 115), "311", fill="white", font=font(15, bold=True), anchor="mm")
    draw.text((80, 250), title, fill=INK, font=font(76, bold=True))
    draw.rectangle((80, 365, 260, 375), fill=ORANGE)
    draw.multiline_text((80, 430), subtitle, fill=(88, 87, 82), font=font(32), spacing=12)
    return frame


def write_hold(writer: imageio.Writer, frame: Image.Image, seconds: float) -> None:
    array = np.asarray(frame)
    for _ in range(round(seconds * FPS)):
        writer.append_data(array)


def write_transition(writer: imageio.Writer, first: Image.Image, second: Image.Image, seconds: float = 0.35) -> None:
    for alpha in np.linspace(0, 1, max(2, round(seconds * FPS)), endpoint=False):
        writer.append_data(np.asarray(Image.blend(first, second, float(alpha))))


def main() -> None:
    frames = [caption_frame(Image.open(DEMO_DIR / filename), caption) for filename, caption in SLIDES]
    intro = title_frame(
        "NYC311 Pulse",
        "Evidence-first anomaly triage\nfor New York City service requests",
    )
    outro = title_frame(
        "Built to be audited.",
        "Complete aggregates · locked evaluation\nprivacy-minimized public artifacts",
    )

    cover = frames[0].copy()
    cover_draw = ImageDraw.Draw(cover)
    cover_draw.ellipse((570, 390, 710, 530), fill=(25, 25, 23))
    cover_draw.polygon([(622, 426), (622, 494), (678, 460)], fill="white")
    cover.save(COVER, optimize=True)

    sequence = [intro, *frames, outro]
    with imageio.get_writer(
        OUTPUT,
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=None,
    ) as writer:
        for index, frame in enumerate(sequence):
            write_hold(writer, frame, 2.0 if index in {0, len(sequence) - 1} else 1.65)
            if index < len(sequence) - 1:
                write_transition(writer, frame, sequence[index + 1])

    print(f"Wrote {OUTPUT}")
    print(f"Wrote {COVER}")


if __name__ == "__main__":
    main()
