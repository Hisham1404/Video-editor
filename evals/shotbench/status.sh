#!/bin/bash
# What is running, what is done, what is stalled.
#
# Task chips only track runs the harness launched itself. Anything started with
# nohup is alive but invisible to them, so this reads the ground truth instead:
# row counts, and how long ago each file was last written.
cd "$(dirname "$0")"

echo "=== live python processes ==="
tasklist //FI "IMAGENAME eq python.exe" //FO CSV 2>/dev/null | tail -n +2 \
  | cut -d, -f2 | tr -d '"' | sed 's/^/  pid /' || echo "  none"

echo
echo "=== runs ==="
now=$(date +%s)
printf "  %-42s %8s  %-9s %s\n" "run" "rows" "target" "last write"
for f in results/*.jsonl; do
  [ -f "$f" ] || continue
  b=$(basename "$f" .jsonl)
  case "$f" in *filmshots*|*reels*) tot=859 ;; *) tot=3572 ;; esac
  n=$(wc -l < "$f" | tr -d ' ')
  age=$(( now - $(date -r "$f" +%s) ))
  # A file untouched for 3+ minutes while its process still exists is either
  # finished or wedged; either way it is worth looking at.
  if   [ "$n" -ge "$tot" ]; then state="done"
  elif [ "$age" -lt 180 ]; then  state="LIVE ${age}s ago"
  else                           state="stalled? ${age}s ago"
  fi
  printf "  %-42s %8s  %-9s %s\n" "$b" "$n" "$tot" "$state"
done

echo
echo "=== queued ==="
for q in queue_gemini queue_groq; do
  [ -f "$q.log" ] && printf "  %-16s %s\n" "$q" "$(tail -1 "$q.log" | cut -c1-64)"
done
