#!/usr/bin/env python3
"""Decode one labelled segment from the published dataset and play it with ffplay.

Usage:
    .venv/bin/python play_clip.py [segment_index] [--split train|test] [--repo USER/NAME]

Press q or Esc in the player window to close it.
"""
import argparse
import subprocess

from datasets import load_dataset

REPO_ID = "Kavitha/kathakali-test"

parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("index", type=int, nargs="?", default=0, help="segment row number (default 0)")
parser.add_argument("--split", default="train", choices=["train", "test"])
parser.add_argument("--repo", default=REPO_ID, help=f"dataset repo id or local path (default {REPO_ID})")
args = parser.parse_args()

# each segment row comes with its video
segments = load_dataset(args.repo, "segments", split=args.split)
seg = segments[args.index]
decoder = seg["video"]
clip = decoder.get_frames_played_in_range(seg["start_sec"], seg["end_sec"])

frames = clip.data.permute(0, 2, 3, 1).contiguous()  # [N, C, H, W] -> [N, H, W, C] for raw RGB
n, height, width, _ = frames.shape
title = f"{seg['label']} - {seg['video_id']} {seg['start_time']}-{seg['end_time']} ({n} frames)"
print(title)

# Feed raw RGB frames to ffplay on stdin
subprocess.run(
    ["ffplay", "-hide_banner", "-loglevel", "error", "-window_title", title, "-autoexit",
     "-f", "rawvideo", "-pixel_format", "rgb24",
     "-video_size", f"{width}x{height}", "-framerate", str(decoder.metadata.average_fps), "-i", "pipe:0"],
    input=frames.numpy().tobytes(),
)
