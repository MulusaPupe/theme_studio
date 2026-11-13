#!/usr/bin/env bash
# A throwaway WordPress for testing exported themes. Test tooling only: the application never uses it.
# Usage: wp_env.sh up | down | wp <args...> | install-zip <theme.zip|plugin.zip> <theme|plugin>
set -euo pipefail
POD=mts-wp
PORT="${MTS_WP_PORT:-8089}"
URL="http://localhost:$PORT"
DB=(-e WORDPRESS_DB_HOST=127.0.0.1 -e WORDPRESS_DB_USER=wp -e WORDPRESS_DB_PASSWORD=wp -e WORDPRESS_DB_NAME=wp)
wp() { podman run --rm -i --pod "$POD" --user 33:33 "${DB[@]}" --volumes-from "$POD-web" -e HOME=/tmp docker.io/library/wordpress:cli wp "$@"; }
case "${1:-}" in
  up)
    podman pod exists "$POD" && podman pod rm -f "$POD" >/dev/null
    podman pod create --name "$POD" -p "$PORT:80" >/dev/null
    podman run -d --pod "$POD" --name "$POD-db" -e MARIADB_DATABASE=wp -e MARIADB_USER=wp -e MARIADB_PASSWORD=wp -e MARIADB_RANDOM_ROOT_PASSWORD=1 docker.io/library/mariadb:11 >/dev/null
    podman run -d --pod "$POD" --name "$POD-web" "${DB[@]}" docker.io/library/wordpress:latest >/dev/null
    for _ in $(seq 1 60); do
      podman exec "$POD-db" mariadb -uwp -pwp wp -e 'select 1' >/dev/null 2>&1 && curl -fs -o /dev/null "$URL/wp-includes/images/blank.gif" && break
      sleep 2
    done
    wp core install --url="$URL" --title="My WordPress Website" --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email
    wp core version; podman exec "$POD-web" php -r 'echo PHP_VERSION,"\n";'
    ;;
  down) podman pod rm -f "$POD" ;;
  wp) shift; wp "$@" ;;
  install-zip)
    # The WP-CLI container shares only the site's volume, so the file goes there for the install.
    podman cp "$2" "$POD-web:/var/www/html/wp-content/upload.zip"
    podman exec "$POD-web" chown www-data /var/www/html/wp-content/upload.zip
    wp "$3" install /var/www/html/wp-content/upload.zip --force --activate
    podman exec "$POD-web" rm -f /var/www/html/wp-content/upload.zip
    ;;
  *) echo "usage: $0 up|down|wp ...|install-zip file theme|plugin"; exit 2 ;;
esac
