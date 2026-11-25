#!/bin/sh
# Usage: ./cast2gif.sh CAST OUT.gif [LAST_FRAME_SECS=3]   -> OUT.gif and OUT.png (last-frame poster, ./poster.sh)
# agg 1.5.0 (built into tools/agg/bin, see README notes in report), JetBrains Mono, Datum navy theme.
# One-time: ./cast2gif.sh --build   (builds localhost/agg-datum:1.5.0 with fonts + ImageMagick)
set -eu
cd "$(dirname "$0")"; HERE=$PWD
IMG=localhost/agg-datum:1.5.0
if [ "${1:-}" = "--build" ]; then nice -n 19 podman build --http-proxy=false -t $IMG -f Dockerfile.agg .; exit; fi
CAST=$(realpath "$1"); OUT=$(realpath -m "$2"); LAST=${3:-3}
COLS=$(python3 -I -c "import json,sys;print(json.loads(open(sys.argv[1]).readline())['width'])" "$CAST")
ROWS=$(python3 -I -c "import json,sys;print(json.loads(open(sys.argv[1]).readline())['height'])" "$CAST")
THEME=0c1d31,e8ecf1,2f3f48,f28c8c,e6f59b,f5d76e,8fb4ff,ebcfd2,7fd1c7,f6f5f1,5a6b75,f7a8a8,eefab5,f8e39a,b3ccff,f3dfe1,a8e3dc,ffffff
mkdir -p "$(dirname "$OUT")"
nice -n 19 podman run --rm --http-proxy=false --user 0 \
  -v "$HERE/tools/agg/bin:/opt/agg:ro,z" -v "$CAST:/in.cast:ro,z" -v "$(dirname "$OUT"):/out:z" $IMG \
  /opt/agg/agg --cols "$COLS" --rows "$ROWS" --font-family "JetBrains Mono" --font-size 16 --line-height 1.35 \
  --idle-time-limit 2 --speed 1.0 --last-frame-duration "$LAST" --theme "$THEME" /in.cast "/out/$(basename "$OUT")" 2>&1 | tr "\r" "\n" | tail -n 1 >/dev/null
"$HERE/poster.sh" "$OUT"
