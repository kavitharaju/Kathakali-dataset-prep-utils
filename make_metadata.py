#!/usr/bin/env python3
"""Write metadata.jsonl for a folder of videos (Hugging Face videofolder format).

One line per video:
    {"file_name": "IMG_0781.mp4", "video_id": "IMG_0781", "duration_sec": 380.6,
     "fps": 60.0, "num_frames": 22836, "width": 1820, "height": 1024}

Usage:
    python3 Kathakali-dataset-prep-utils/make_metadata.py [video_dir ...]
    (default: Kathakali-test/videos_sd Kathakali-test/videos_hd)
"""
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

DEFAULT_DIRS = ["Kathakali-test/videos_sd", "Kathakali-test/videos_hd"]


def probe(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(out.stdout)
    stream, duration = info["streams"][0], float(info["format"]["duration"])
    fps = Fraction(stream["r_frame_rate"])
    num_frames = int(stream.get("nb_frames") or round(duration * fps))
    return {
        "file_name": video.name,
        "video_id": video.stem,
        "duration_sec": round(duration, 3),
        "fps": round(float(fps), 3),
        "num_frames": num_frames,
        "width": stream["width"],
        "height": stream["height"],
    }


def main():
    for video_dir in map(Path, sys.argv[1:] or DEFAULT_DIRS):
        videos = sorted(p for p in video_dir.glob("*") if p.suffix.lower() in {".mp4", ".mov"})
        if not videos:
            print(f"{video_dir}: no videos, skipped")
            continue
        with (video_dir / "metadata.jsonl").open("w", encoding="utf-8") as f:
            for video in videos:
                f.write(json.dumps(probe(video)) + "\n")
        print(f"{video_dir}: wrote metadata.jsonl for {len(videos)} videos")


if __name__ == "__main__":
    main()
