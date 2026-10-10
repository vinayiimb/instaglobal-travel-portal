#!/bin/zsh
# usage: pget.sh URL OUT  -- parallel ranged download (16 parts), for throttled hosts
url=$1; out=$2; n=16
size=$(curl -sIL "$url" | grep -i '^content-length' | tail -1 | tr -dc '0-9')
[ -z "$size" ] && { echo "no size for $url"; exit 1; }
part=$(( (size + n - 1) / n ))
for i in $(seq 0 $((n-1))); do
  s=$((i*part)); e=$((s+part-1)); [ $e -ge $size ] && e=$((size-1))
  ( until curl -sL --retry 5 -r $s-$e -o "$out.part$i" "$url" && [ $(stat -f%z "$out.part$i") -eq $((e-s+1)) ]; do sleep 2; done ) &
done
wait
cat $(for i in $(seq 0 $((n-1))); do echo "$out.part$i"; done) > "$out" && rm -f "$out".part*
echo "$out $(stat -f%z "$out") / $size"
