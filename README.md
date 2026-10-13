# Kathakali dataset prep utils

Scripts for turning raw iPhone recordings and SRT annotation files into a
Hugging Face video dataset with labelled segments, plus how to check and use the
published dataset.

The resulting dataset repo looks like this:

```
<dataset repo>/
├── README.md               dataset card (with the configs YAML)
├── .gitattributes          stores *.mp4 with Git LFS
├── videos_sd/
│   ├── metadata.jsonl      one row per video
│   ├── segments_train.csv  one row per labelled segment
│   ├── segments_test.csv
│   └── IMG_0781.mp4 ...    H.264, 1024 px high, no audio
└── videos_hd/              same, at original resolution
```

## Scripts

| Script | What it does |
|---|---|
| `make_sd.sh` | `.MOV` → SD `.mp4` (H.264, 1024 px high, no audio, HDR → SDR) |
| `make_hd.sh` | `.MOV` → HD `.mp4` (same, original resolution) |
| `make_metadata.py` | Writes `metadata.jsonl` for each video folder |
| `srt_to_segments.py` | SRT files → `segments_train.csv` / `segments_test.csv` in each video folder |
| `make_dummy_srt.py` | Generates dummy SRT files (random animal labels) for testing the pipeline |
| `testing/test_dataset.py` | Checks that the published (or local) dataset loads and its segments decode |
| `testing/play_clip.py` | Plays one segment from the published dataset with `ffplay` |
| `testing/play_clip_streaming.py` | Same, with `streaming=True` (reads only the needed part of one video) |

## Prerequisites

- **ffmpeg** with the `zscale` filter (`ffmpeg -filters | grep zscale`). Ubuntu's
  `ffmpeg` package has it.
- **Python 3.10+**. The prep scripts use only the standard library.
- **git** and **git-lfs** (`sudo apt install git-lfs && git lfs install`).
- A **Hugging Face account** and an access token with write permission.

## Set your paths

The commands below use shell variables for every folder and name, so they work
from any directory. Set them once per terminal session, replacing the `<…>`
placeholders. Absolute paths are safest; quote any path with spaces.

```bash
UTILS_DIR=<path-to>/Kathakali-dataset-prep-utils   # this repo
RAW_DIR=<raw-videos-dir>                           # original .MOV recordings
SRT_DIR=<srt-dir>                                  # one .srt per video, named like the video (IMG_0781.srt)
HF_USER=<hf-user>                                  # Hugging Face user or organisation
HF_REPO=<hf-repo-name>                             # dataset repo name
DATASET_DIR=<path-to>/<hf-repo-name>               # local git clone of the dataset repo
```

Python snippets use `"<hf-user>/<hf-repo-name>"` for the dataset id.

Each script also has defaults (`raw data`, `dataTimestamp` and a dataset clone
named `Kathakali-test`, relative to the current folder), but passing the paths
explicitly, as below, avoids depending on them. The usage line at the top of
each script lists all its options.

## 1. Create and clone the dataset repo

Create a dataset repo on huggingface.co (or `hf repo create "$HF_USER/$HF_REPO" --repo-type dataset`),
then clone it:

```bash
git lfs install
git clone "https://huggingface.co/datasets/$HF_USER/$HF_REPO" "$DATASET_DIR"
```

The `.gitattributes` Hugging Face creates already stores `*.mp4` with LFS.
Hugging Face rejects any file over 10 MB that is not in LFS, so **git-lfs must be
installed before you `git add` any video**.

## 2. Convert the videos

```bash
"$UTILS_DIR/make_sd.sh" "$RAW_DIR" "$DATASET_DIR/videos_sd"
"$UTILS_DIR/make_hd.sh" "$RAW_DIR" "$DATASET_DIR/videos_hd"
```

Arguments: `<input_dir> <output_dir>`. The output folder is created if needed.

Both scripts:

- convert every `.mov`/`.MOV` in the input folder to `.mp4`, keeping the file
  name (`IMG_0781.MOV` → `IMG_0781.mp4`);
- encode H.264 (`libx264`, CRF 23, `yuv420p`) and drop the audio track;
- **tone-map HDR to SDR.** iPhone recordings are HDR (HLG or PQ, BT.2020
  colours). Converted to 8-bit without tone mapping they look washed out, so
  HDR input is converted to BT.709 with the `mobius` curve (chosen by comparing
  frames; `hable` came out dark and yellowish). SDR input is converted as is;
- skip outputs that already exist. Delete an output to redo it.

`make_sd.sh` scales to 1024 px height and keeps the aspect ratio (3840×2160 →
1820×1024). `make_hd.sh` keeps the original resolution. The HD outputs are 4K at
60 fps, so they are slow to encode and large.

## 3. Prepare the annotations

Annotations are SRT subtitle files in `$SRT_DIR`, one per video, named
after the video (`IMG_0781.srt` for `IMG_0781.mp4`). Each subtitle is one
segment and its text is the label:

```
1
00:00:02,099 --> 00:00:04,174
Peacock
```

To test the pipeline without real annotations, generate dummy ones:

```bash
python3 "$UTILS_DIR/make_dummy_srt.py" --video-dir "$DATASET_DIR/videos_sd" --output-dir "$SRT_DIR"
```

This writes an SRT for every video in `--video-dir`: 2–5 s
segments with 2–8 s gaps, using 10 animal names spread evenly (each label is
used the same number of times, ±1). It overwrites existing SRT files in
`--output-dir` and gives the same output for the same `--seed` (default 42).

## 4. Convert SRT to segments

```bash
python3 "$UTILS_DIR/srt_to_segments.py" \
    --srt-dir "$SRT_DIR" \
    --video-dir "$DATASET_DIR/videos_sd" \
    --output-dirs "$DATASET_DIR/videos_sd" "$DATASET_DIR/videos_hd" \
    --test-ratio 0.2 --seed 42
```

This reads every `.srt` in `--srt-dir`, splits the segments into train and
test, and writes `segments_train.csv` and `segments_test.csv` into each
`--output-dirs` folder that contains all the videos (a folder with missing
videos, such as an empty `videos_hd/`, is skipped). `--video-dir` is where the
frame rate is read from.

| Column | Description |
|---|---|
| `file_name` | Video file in the same folder; links the row to its video |
| `video_id` | SRT file name without extension |
| `start_time`, `end_time` | `HH:MM:SS.mmm` |
| `start_sec`, `end_sec` | Seconds, millisecond precision |
| `start_frame`, `end_frame` | Seconds × fps, rounded (fps read from the video in `--video-dir`) |
| `label` | Subtitle text |

- **Split:** stratified by label. 20% of each label's segments go to test
  (`--test-ratio`), so both splits have the same class balance. A label with a
  single segment goes to train. Fixed `--seed`, so reruns give the same split.
  Segments from one video can end up in both splits.
- **Why the CSVs sit next to the videos:** the Hugging Face video loader only
  links a metadata file's `file_name` to videos in the same folder or its subfolders.
  This is what lets each segment row carry its video in the dataset viewer.
- **Edit the SRT files, not the CSVs**, then rerun the script. It overwrites the CSVs.
- The script stops if an SRT has no matching video, so frame numbers are never guessed.

## 5. Write the video metadata

```bash
python3 "$UTILS_DIR/make_metadata.py" "$DATASET_DIR/videos_sd" "$DATASET_DIR/videos_hd"
```

Writes `metadata.jsonl` in each folder given (folders without videos are skipped), with `file_name`, `video_id`, `duration_sec`, `fps`, `num_frames`,
`width` and `height` for each video, read with `ffprobe`. Rerun after adding videos.

## 6. Dataset card configs

The dataset card (`README.md` in the dataset repo) needs this `configs` block in
its YAML header:

```yaml
configs:
  - config_name: videos
    default: true
    data_files:
      - split: train
        path: [videos_sd/*.mp4, videos_sd/metadata.jsonl]
  - config_name: videos_hd
    data_files:
      - split: train
        path: [videos_hd/*.mp4, videos_hd/metadata.jsonl]
  - config_name: segments
    metadata_filenames: [segments_train.csv, segments_test.csv]
    data_files:
      - split: train
        path: [videos_sd/*.mp4, videos_sd/segments_train.csv]
      - split: test
        path: [videos_sd/*.mp4, videos_sd/segments_test.csv]
```

Things that matter here:

- `datasets` picks **one loader for the whole repo**, from the first config
  (here the video-folder loader), and uses it for every config. A config that
  points at plain CSV files loads 0 rows. That is why segments are loaded as
  the video loader's metadata (`metadata_filenames`) rather than as CSVs.
- List the `.mp4` files and the metadata file explicitly, so the `videos`
  configs don't pick up the segment CSVs.
- **Leave out (or comment out) the `videos_hd` config until `videos_hd/` has the
  videos and `metadata.jsonl`.** A config with no files fails in the viewer.
- If a config shows `ResponseNotFound` in the viewer while its split and row
  counts are correct, the viewer's preview job for it did not run (this happened
  right after a repo rename). Any new commit makes the viewer reprocess everything.

## 7. Commit and push

```bash
cd "$DATASET_DIR"
git add .
git lfs ls-files        # every .mp4 must be listed here before you commit
git commit -m "Add videos and segments"
git push
```

When asked for a password, use a Hugging Face access token with write
permission. The viewer takes a few minutes to update after a push.

## 8. Use and test the published dataset

The scripts in `testing/` run with their own virtual environment, which is
kept out of git (`.gitignore`).

### Environment

Install `torch` and `torchcodec` from PyTorch's CPU index first. From the
default index, `torchcodec` comes as the CUDA build and fails to load without
NVIDIA libraries (`Could not load this library: .../libtorchcodec_image.so`).

```bash
cd "$UTILS_DIR/testing"
uv venv .venv
uv pip install --python .venv/bin/python torch torchcodec --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/bin/python -r requirements.txt
```

(`python3 -m venv` works too if the `python3-venv` package is installed.)
The download is large (about 1 GB installed), so allow time on a slow connection.

### Test scripts

Run from `$UTILS_DIR/testing`. Pass the dataset with `--repo` (play scripts) or
as the first argument (`test_dataset.py`); either a Hub id or a local folder works.

```bash
cd "$UTILS_DIR/testing"
.venv/bin/python test_dataset.py "$HF_USER/$HF_REPO"                      # check the published dataset
.venv/bin/python test_dataset.py "$DATASET_DIR"                           # check the local clone before pushing
.venv/bin/python play_clip.py 42 --repo "$HF_USER/$HF_REPO"               # play train segment 42
.venv/bin/python play_clip.py 3 --split test --repo "$HF_USER/$HF_REPO"   # play test segment 3
.venv/bin/python play_clip_streaming.py 3 --split test --repo "$HF_USER/$HF_REPO"
```

Without a repo argument the scripts fall back to `Kavitha/kathakali-test`
(`REPO_ID` at the top of each script).

`test_dataset.py` runs the usage example below and checks that both splits have
rows, that every segment's video is in the `videos` config, that each segment's
attached video matches its `video_id`, and that the decoded clip has the expected
number of frames. The play scripts close the window when the clip ends; press
`q` or `Esc` to close it sooner.

### Load segments with their videos

```python
from datasets import load_dataset

segments = load_dataset("<hf-user>/<hf-repo-name>", "segments", split="train")

seg = segments[0]
clip = seg["video"].get_frames_played_in_range(seg["start_sec"], seg["end_sec"])
print(seg["label"], clip.data.shape)  # e.g. Peacock torch.Size([126, 3, 1024, 1820])
```

- **Downloads:** `load_dataset` downloads every file of the requested config
  once, into `~/.cache/huggingface/hub/`, and reuses it on later runs. The
  `segments` and `videos` configs share the SD videos; `videos_hd` downloads
  the 4K files. Each row only stores the path to the cached video, and frames
  are decoded only for the range you request.
- **`get_frames_played_in_range`** returns every frame on screen during the
  range, including partly-shown frames at both ends. That can be one or two
  more frames than `end_frame - start_frame`.
- **HD frames:** load the `videos_hd` config and look the video up by `video_id`.

### Streaming

To read a few clips without downloading the whole config:

```python
from itertools import islice
from datasets import Video, load_dataset

segments = load_dataset("<hf-user>/<hf-repo-name>", "segments", split="train", streaming=True)
segments = segments.cast_column("video", Video(decode=False))  # don't open videos while skipping rows
seg = next(islice(segments, 42, None))                         # streamed datasets can't be indexed

decoder = Video(seek_mode="approximate").decode_example(seg["video"])
clip = decoder.get_frames_played_in_range(seg["start_sec"], seg["end_sec"])
```

Use `seek_mode="approximate"` when streaming. The default `"exact"` mode scans
the whole file before seeking, which over the network means downloading all
of it (measured: ~61 MB instead of ~10 MB for one 3 s clip). Streaming caches
nothing, so every run fetches again.

### Playing a clip

`ffplay` (part of ffmpeg) can play decoded frames without extra packages:

```python
import subprocess

frames = clip.data.permute(0, 2, 3, 1).contiguous()  # [N, C, H, W] -> [N, H, W, C]
n, h, w, _ = frames.shape
subprocess.run(
    ["ffplay", "-autoexit", "-f", "rawvideo", "-pixel_format", "rgb24",
     "-video_size", f"{w}x{h}", "-framerate", "60", "-i", "pipe:0"],
    input=frames.numpy().tobytes(),
)
```

### Testing before you push

`load_dataset` also accepts a local folder, which is how
`test_dataset.py "$DATASET_DIR"` checks the clone before pushing:

```python
load_dataset("<path-to>/<hf-repo-name>", "segments", split="train")
```

The Hugging Face viewer uses `datasets` to build its preview, so if every config
loads locally, the viewer should be able to show it.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| Push rejected: "files larger than 10 MiB" | Videos were committed without LFS. Install git-lfs, then rebuild the commit: `git reset --soft origin/main`, `git rm -r --cached -q .`, `git add .`, check `git lfs ls-files`, commit and push. |
| `segments` config loads 0 rows / not in viewer | The segments were added as plain CSVs. Use the `metadata_filenames` config from step 6, with the CSVs inside the video folder. |
| `Could not load this library: ...libtorchcodec_...so` | CUDA build of `torchcodec` on a CPU-only machine. Reinstall from `https://download.pytorch.org/whl/cpu`. |
| Converted videos look pale or washed out | HDR input converted without tone mapping. Use these scripts, which detect HDR with `ffprobe` and tone-map it. |
| `make_sd.sh` / `make_hd.sh` skips a file | The output already exists. Delete it to convert again. |
