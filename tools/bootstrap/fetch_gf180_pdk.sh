#!/bin/bash
# Fetch the GF180 standard-cell library from the pinned PDK release.
# usage: fetch_gf180_pdk.sh <destination directory>
set -euo pipefail
DEST=${1:?destination directory}
COMMIT=f6bfbd4d3d23c4236ff1f36126489ee59aa35cbd
BASE=https://github.com/fossi-foundation/ciel-releases/releases/download/gf180mcu-$COMMIT
mkdir -p "$DEST"; cd "$DEST"
fetch() { # name sha256
  [ -f "$1.tar.zst" ] || curl -fsSL -o "$1.tar.zst" "$BASE/$1.tar.zst"
  echo "$2  $1.tar.zst" | sha256sum -c -
  tar --zstd -xf "$1.tar.zst"
}
fetch gf180mcu_fd_sc_mcu7t5v0 48340b027293da69226b854087a8e9f0f757fcc9e631d1c18eab2681a359e33a
ls gf180mcuD/libs.ref/*/lib/*__tt_025C_3v30.lib
