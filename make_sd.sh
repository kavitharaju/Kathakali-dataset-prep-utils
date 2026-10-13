#!/usr/bin/env bash
# Convert MOV files to SD MP4 (H.264, no audio, height 1024, width keeps aspect ratio).
# Usage: Kathakali-dataset-prep-utils/make_sd.sh [input_dir] [output_dir]
set -euo pipefail

IN_DIR="${1:-raw data}"
OUT_DIR="${2:-Kathakali-test/videos_sd}"

mkdir -p "$OUT_DIR"
shopt -s nullglob nocaseglob

files=("$IN_DIR"/*.mov)
if [ ${#files[@]} -eq 0 ]; then
    echo "No .MOV files found in '$IN_DIR'"
    exit 1
fi

for src in "${files[@]}"; do
    name="$(basename "$src")"
    dst="$OUT_DIR/${name%.*}.mp4"

    if [ -e "$dst" ]; then
        echo "Skipping (exists): $dst"
        continue
    fi

    # Height 1024, width auto-computed and rounded to an even number (required by H.264)
    vf="zscale=w=-2:h=1024"

    # iPhone recordings are HDR (HLG or PQ, BT.2020 colours); tone-map them to standard
    # BT.709 video, otherwise the 8-bit output looks washed out
    trc="$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of csv=p=0 "$src")"
    if [ "$trc" = "arib-std-b67" ] || [ "$trc" = "smpte2084" ]; then
        echo "Converting (HDR -> SDR): $src -> $dst"
        vf="$vf,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv"
    else
        echo "Converting: $src -> $dst"
    fi

    # yuv420p ensures playback compatibility (iPhone MOVs are often 10-bit HEVC)
    ffmpeg -nostdin -hide_banner -loglevel warning -stats \
        -i "$src" \
        -vf "$vf,format=yuv420p" \
        -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
        -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
        -an \
        -movflags +faststart \
        "$dst"
done

echo "Done."
