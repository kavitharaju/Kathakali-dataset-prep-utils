#!/usr/bin/env python3
"""Smoke test for the published Kathakali-test dataset, based on the README usage example.

Usage:
    .venv/bin/python test_dataset.py [repo_id_or_local_path]
"""
import sys

from datasets import load_dataset

REPO_ID = sys.argv[1] if len(sys.argv) > 1 else "Kavitha/kathakali-test"

# --- README example ---
segments = load_dataset(REPO_ID, "segments", split="train")

# each segment row comes with its video; decode just the segment's frames
seg = segments[0]
clip = seg["video"].get_frames_played_in_range(seg["start_sec"], seg["end_sec"])

print(seg["label"], clip.data.shape)

# --- extra checks ---
videos = load_dataset(REPO_ID, "videos", split="train")
test_segments = load_dataset(REPO_ID, "segments", split="test")
print(f"\nvideos:   {len(videos)} ({', '.join(videos['video_id'])})")
print(f"segments: {len(segments)} train / {len(test_segments)} test")
print(f"columns:  {segments.column_names}")

assert len(segments) > 0 and len(test_segments) > 0, "segments config returned no rows"

video_ids = set(videos["video_id"])
missing = {s for s in list(segments["video_id"]) + list(test_segments["video_id"]) if s not in video_ids}
assert not missing, f"segments refer to videos that are not in the dataset: {missing}"

# the video attached to a segment must be the one named by its video_id
assert seg["video"].metadata.path.endswith(f"{seg['video_id']}.mp4"), seg["video"].metadata.path

# frames decoded should cover the segment's duration; get_frames_played_in_range also
# returns the partly-shown frames at both ends, so allow 2 frames of difference
fps = seg["video"].metadata.average_fps
expected = (seg["end_sec"] - seg["start_sec"]) * fps
assert abs(clip.data.shape[0] - expected) <= 2, f"got {clip.data.shape[0]} frames, expected ~{expected:.0f}"

print("\nAll checks passed.")
