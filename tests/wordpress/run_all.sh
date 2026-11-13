#!/usr/bin/env bash
# The whole real-WordPress test, from a saved project to the walkthrough. Needs Podman and internet access.
# Usage: tests/wordpress/run_all.sh <project folder> <work folder>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
E="$HERE/wp_env.sh"
PROJECT="$1"; WORK="$2"; NAME="${3:-Mulusa Innovations}"; PORT="${MTS_WP_PORT:-8089}"
SLUG="$(echo "$NAME" | tr 'A-Z ' 'a-z-')"
mkdir -p "$WORK"
"$PY" "$HERE/export_project.py" "$PROJECT" "$WORK/zip" "$NAME"
"$PY" "$HERE/sample_posts.py" "$WORK/post-images"
"$E" up | tail -2
"$E" install-zip "$WORK/zip/$SLUG.zip" theme | tail -1
"$E" install-zip "$WORK/zip/$SLUG-content.zip" plugin | tail -1
"$E" wp mulusa-content import
"$E" wp term create category News >/dev/null
"$E" wp post delete 1 --force >/dev/null  # WordPress's own "Hello world!" post.
podman exec mts-wp-web mkdir -p /var/www/html/wp-content/seed
i=0
for title in "Sample project: harbour booking system" "Sample project: farm records app" "Sample project: clinic scheduling" "Sample news: office update"; do
  i=$((i + 1)); category=projects; [ "$i" = 4 ] && category=news
  podman cp "$WORK/post-images/post-$i.jpg" mts-wp-web:/var/www/html/wp-content/seed/
  id=$("$E" wp post create --post_status=publish --post_title="$title" --post_category="$category" --tags_input="sample,demo" \
    --post_excerpt="Invented example post number $i, written to test how posts appear." \
    --post_content="<!-- wp:paragraph --><p>This post is invented test content, number $i. It shows the single post template.</p><!-- /wp:paragraph --><!-- wp:heading --><h2 class=\"wp-block-heading\">A subheading</h2><!-- /wp:heading --><!-- wp:paragraph --><p>More body text to show how a long article reads.</p><!-- /wp:paragraph -->" --porcelain)
  "$E" wp media import "/var/www/html/wp-content/seed/post-$i.jpg" --post_id="$id" --featured_image --porcelain >/dev/null
done
# The first directory lookup on a new site can fail, so it gets a few tries.
for _ in 1 2 3 4; do "$E" wp plugin install theme-check --activate >/dev/null 2>&1 && break; sleep 4; done
echo "--- Theme Check"; "$E" wp theme-check run "$SLUG" || true
echo "--- Versions"; "$E" wp core version; podman exec mts-wp-web php -r 'echo PHP_VERSION,"\n";'
echo "--- Walkthrough"; QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$PY" "$HERE/walkthrough.py" "http://localhost:$PORT" "$WORK/shots" "$SLUG" 2>&1 | grep -vE "Vulkan|GLX|GPUInfo|^js:|Release of|\[.*ERROR"
echo "--- PHP errors logged"; podman logs mts-wp-web 2>&1 | grep -iE "php (warning|fatal|notice|parse)" | tail -5 || true
