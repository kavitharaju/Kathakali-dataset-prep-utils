#!/usr/bin/env python3
"""Convert all .srt files in a folder into train/test segment CSVs.

Output: segments_train.csv and segments_test.csv in each --output-dirs folder that
holds all the videos (by default videos_sd, and videos_hd once it is filled).
Columns: file_name, video_id, start_time, end_time, start_sec, end_sec, start_frame, end_frame, label
  - file_name:             the video file in that folder (links each row to its video)
  - video_id:              SRT file name without extension (e.g. IMG_0781.srt -> IMG_0781)
  - start_time/end_time:   HH:MM:SS.mmm
  - start_sec/end_sec:     time in seconds (float, millisecond precision)
  - start_frame/end_frame: frame index (seconds x fps, rounded), using the fps of
                           the matching video in --video-dir
  - label:                 subtitle text (multi-line text joined with a space)

The `segments` config in the README loads these files, so each segment row comes with
its video. They sit next to the videos because the Hugging Face video-folder loader
only accepts metadata files in the same folder as the videos (or above).

The split is stratified by label: the segments of each label are shuffled and
divided by --test-ratio, so every label appears in both sets in the same
proportion. A label with only one segment goes to train.

Usage:
    python3 Kathakali-dataset-prep-utils/srt_to_segments.py [--srt-dir DIR] [--video-dir DIR]
                                     [--output-dirs DIR ...] [--test-ratio 0.2] [--seed 42]
"""
import argparse
import csv
import random
import re
import subprocess
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

TIME_LINE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{3})"
)
HEADER = ["file_name", "video_id", "start_time", "end_time", "start_sec", "end_sec",
          "start_frame", "end_frame", "label"]


def to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def to_timestamp(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def video_fps(video_dir, video_id):
    """Return the frame rate of <video_dir>/<video_id>.* (e.g. 60 or 30000/1001)."""
    matches = sorted(p for p in video_dir.glob(f"{video_id}.*") if p.suffix.lower() in {".mp4", ".mov"})
    if not matches:
        sys.exit(f"No video found for '{video_id}' in '{video_dir}'")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(matches[0])],
        capture_output=True, text=True, check=True,
    )
    return Fraction(out.stdout.strip())


def parse_srt(path):
    """Yield (start, end, label) for each cue in an SRT file."""
    text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips a BOM if present
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            match = TIME_LINE.search(line)
            if match:
                g = match.groups()
                start, end = to_seconds(*g[:4]), to_seconds(*g[4:])
                label = " ".join(lines[i + 1:])
                yield start, end, label
                break


def stratified_split(segments, test_ratio, seed):
    """Split segments per label so each label keeps the same train/test ratio."""
    by_label = defaultdict(list)
    for seg in segments:
        by_label[seg[3]].append(seg)

    rng = random.Random(seed)
    train, test = [], []
    for label in sorted(by_label):
        items = by_label[label]
        rng.shuffle(items)
        n_test = round(len(items) * test_ratio) if len(items) > 1 else 0
        test.extend(items[:n_test])
        train.extend(items[n_test:])

    key = lambda s: (s[0], s[1])  # order by video, then start time
    return sorted(train, key=key), sorted(test, key=key)


def write_csv(path, rows, fps, file_names):
    """Write segment rows; file_names maps each video_id to its video file name."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for video_id, start, end, label in rows:
            rate = fps[video_id]
            writer.writerow([
                file_names[video_id], video_id, to_timestamp(start), to_timestamp(end),
                f"{start:.3f}", f"{end:.3f}",
                round(start * rate), round(end * rate),
                label,
            ])


def video_file_names(video_dir, video_ids):
    """Map each video id to its file name in video_dir, or return None if any is missing."""
    files = {p.stem: p.name for p in video_dir.glob("*") if p.suffix.lower() in {".mp4", ".mov"}}
    if not all(v in files for v in video_ids):
        return None
    return {v: files[v] for v in video_ids}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--srt-dir", default="dataTimestamp")
    parser.add_argument("--video-dir", default="Kathakali-test/videos_sd")
    parser.add_argument("--output-dirs", nargs="+",
                        default=["Kathakali-test/videos_sd", "Kathakali-test/videos_hd"])
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    srt_dir = Path(args.srt_dir)
    srt_files = sorted(p for p in srt_dir.iterdir() if p.suffix.lower() == ".srt")
    if not srt_files:
        sys.exit(f"No .srt files found in '{srt_dir}'")

    video_dir = Path(args.video_dir)
    segments, fps = [], {}
    for srt in srt_files:
        fps[srt.stem] = video_fps(video_dir, srt.stem)
        found = [(srt.stem, start, end, label) for start, end, label in parse_srt(srt)]
        print(f"{srt.name}: {len(found)} segments @ {float(fps[srt.stem]):g} fps")
        segments.extend(found)

    train, test = stratified_split(segments, args.test_ratio, args.seed)

    print(f"Split: {len(train)} train / {len(test)} test segments")

    for output_dir in map(Path, args.output_dirs):
        file_names = video_file_names(output_dir, fps) if output_dir.is_dir() else None
        if file_names is None:
            print(f"{output_dir}: not all videos present, skipped")
            continue
        write_csv(output_dir / "segments_train.csv", train, fps, file_names)
        write_csv(output_dir / "segments_test.csv", test, fps, file_names)
        print(f"{output_dir}: wrote segments_train.csv / segments_test.csv")


if __name__ == "__main__":
    main()
