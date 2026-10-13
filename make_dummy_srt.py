#!/usr/bin/env python3
"""Create dummy .srt files (random animal-name segments) for every video in a folder.

Labels are balanced across all videos combined: every label is used the same
number of times (counts differ by at most 1), so the data can later be split
into balanced train/test sets for classification.

Usage:
    python3 Kathakali-dataset-prep-utils/make_dummy_srt.py [--video-dir DIR] [--output-dir DIR] [--seed 42]
"""
import argparse
import random
import subprocess
from collections import Counter
from pathlib import Path

LABELS = ["Elephant", "Tiger", "Peacock", "Monkey", "Deer",
          "Lion", "Swan", "Snake", "Parrot", "Horse"]
SEGMENT_SECONDS = (2, 5)  # length of each segment
GAP_SECONDS = (2, 8)      # gap between segments


def duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout)


def timestamp(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_segments(length, rng):
    """Return (start, end) pairs covering a video of the given length."""
    segments = []
    t = rng.uniform(0.5, 3)
    while True:
        end = t + rng.uniform(*SEGMENT_SECONDS)
        if end > length:
            return segments
        segments.append((t, end))
        t = end + rng.uniform(*GAP_SECONDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--video-dir", default="Kathakali-test/videos_sd")
    parser.add_argument("--output-dir", default="dataTimestamp")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    videos = sorted(p for p in Path(args.video_dir).iterdir() if p.suffix.lower() in {".mp4", ".mov"})
    timings = {v: make_segments(duration(v), rng) for v in videos}

    # Repeat the label list to cover every segment, then shuffle so labels mix across videos
    total = sum(len(t) for t in timings.values())
    labels = (LABELS * (total // len(LABELS) + 1))[:total]
    rng.shuffle(labels)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for video, segments in timings.items():
        cues = []
        for i, (start, end) in enumerate(segments, 1):
            cues.append(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{labels.pop()}\n")
        (out_dir / f"{video.stem}.srt").write_text("\n".join(cues), encoding="utf-8")
        print(f"{video.stem}.srt: {len(segments)} segments")

    print(f"Total {total} segments across {len(videos)} videos")


if __name__ == "__main__":
    main()
