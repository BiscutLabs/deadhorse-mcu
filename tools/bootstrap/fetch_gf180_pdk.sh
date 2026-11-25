#!/bin/bash
# Fetch the GF180 standard-cell library from the pinned PDK release.
# usage: fetch_gf180_pdk.sh <destination directory>
set -euo pipefail
DEST=${1:?destination directory}
COMMIT=792ef67037d74c8c51811eab3ce23cf793491296
BASE=https://github.com/fossi-foundation/ciel-releases/releases/download/gf180mcu-$COMMIT
mkdir -p "$DEST"; cd "$DEST"
fetch() { # name sha256
  [ -f "$1.tar.zst" ] || curl -fsSL -o "$1.tar.zst" "$BASE/$1.tar.zst"
  echo "$2  $1.tar.zst" | sha256sum -c -
  tar --zstd -xf "$1.tar.zst"
}
fetch gf180mcu_fd_sc_mcu7t5v0 0d4b8cc43105865e09e192cab0a9f643845f9567b5782672a7be19b2499f9ce0
ls gf180mcuD/libs.ref/*/lib/*__tt_025C_3v30.lib
