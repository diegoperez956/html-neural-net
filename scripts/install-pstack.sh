#!/usr/bin/env bash
# Fetch skill sources only. No upstream install scripts or dependencies run.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/reference/cursor-plugins"
REV=9bd4a8289f1c3fe870d518051772762a78b66ea0
URL=https://github.com/cursor/plugins.git

if [[ ! -e "$DEST" ]]; then
    git clone --filter=blob:none --sparse "$URL" "$DEST"
fi
[[ -d "$DEST/.git" ]] || { echo "Refusing to replace non-repository $DEST" >&2; exit 1; }
[[ "$(git -C "$DEST" remote get-url origin)" == "$URL" ]] || {
    echo 'Refusing unexpected pstack remote' >&2; exit 1;
}
[[ -z "$(git -C "$DEST" status --porcelain)" ]] || {
    echo 'Refusing to replace modified pstack sources' >&2; exit 1;
}
git -C "$DEST" cat-file -e "$REV^{commit}" 2>/dev/null || git -C "$DEST" fetch origin "$REV"
git -C "$DEST" sparse-checkout set pstack
git -C "$DEST" checkout --detach "$REV"
printf 'pstack sources pinned to %s\nSkills: /skill:pstack and /skill:unslop\n' "$REV"
