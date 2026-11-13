#!/usr/bin/env bash
# Installs exported themes in a fresh, throwaway WordPress one at a time and checks them for real:
# the theme activates, the content plugin creates the pages, every page answers 200 with no PHP
# error, a published post appears in post lists, and Gutenberg finds no invalid block.
# Needs Podman (and internet access the first time, for the images).
# Usage: tests/wordpress/check_exports.sh <exports folder> <slug> [<slug> ...]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
E="$HERE/wp_env.sh"
PORT="${MTS_WP_PORT:-8089}"
URL="http://localhost:$PORT"
OUT="$1"; shift
FAILED=0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
for SLUG in "$@"; do
  echo "=================== $SLUG"
  "$E" up >/dev/null 2>&1 || { echo "WordPress did not start"; exit 2; }
  "$E" install-zip "$OUT/$SLUG.zip" theme | tail -1
  "$E" install-zip "$OUT/$SLUG-content.zip" plugin | tail -1
  "$E" wp mulusa-content import
  "$E" wp post delete 1 --force >/dev/null
  post=$("$E" wp post create --post_status=publish --post_title="Check post: site handover" --post_excerpt="A test post." \
         --post_content="<!-- wp:paragraph --><p>Test post body.</p><!-- /wp:paragraph -->" --porcelain)
  ids=$("$E" wp post list --post_type=page --field=ID --format=csv | tr '\n' ',' | sed 's/,$//')
  for path in $("$E" wp post list --post_type=page --post_status=publish --field=url | sed "s#$URL##"); do
    code=$(curl -s -o $T/page.html -w '%{http_code}' "$URL$path")
    lists=""; grep -q "Check post: site handover" $T/page.html && lists="  (lists the test post)"
    errors=$(grep -ciE "fatal error|warning:|notice:|deprecated:" $T/page.html)
    echo "page $path: HTTP $code, PHP messages $errors$lists"
    [ "$code" = 200 ] && [ "$errors" = 0 ] || FAILED=1
  done
  code=$(curl -sL -o /dev/null -w '%{http_code}' "$URL/?p=$post"); echo "single post: HTTP $code"; [ "$code" = 200 ] || FAILED=1
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$PY" "$HERE/check_gutenberg.py" "$URL" "$ids" "$SLUG" >$T/gutenberg.txt 2>&1 || FAILED=1
  grep -E "^(post|pattern|TOTAL)|did not become ready" $T/gutenberg.txt | tail -30
  echo "--- PHP errors logged"; podman logs mts-wp-web 2>&1 | grep -iE "php (warning|fatal|notice|parse)" | tail -5 || true
done
"$E" down >/dev/null 2>&1
exit $FAILED
