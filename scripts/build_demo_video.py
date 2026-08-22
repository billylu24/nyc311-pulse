"""Transcode the real Playwright walkthrough into a GitHub-friendly MP4."""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "nyc311-pulse-walkthrough.webm"
OUTPUT = ROOT / "public" / "demo" / "nyc311-pulse-demo.mp4"
COVER = ROOT / "public" / "demo" / "nyc311-pulse-demo-cover.png"


def run(*arguments: str) -> None:
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", *arguments],
        check=True,
    )


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(
            "Missing recorded walkthrough. Start the app, then run "
            "`node scripts/record_walkthrough.mjs` first."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run(
        "-i",
        str(SOURCE),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "27",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(OUTPUT),
    )
    run(
        "-ss",
        "00:00:02",
        "-i",
        str(OUTPUT),
        "-frames:v",
        "1",
        "-update",
        "1",
        str(COVER),
    )
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {COVER}")


if __name__ == "__main__":
    main()
