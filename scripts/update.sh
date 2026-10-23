#!/bin/sh
# Update ParsRAG to the latest release, after backing up its data.
#
# Run from anywhere inside the ParsRAG folder:
#   sh scripts/update.sh
#
# Steps: check the copy is clean, find the latest release tag, back up the
# server data (documents index and settings) and .env, switch the code to that
# release (skipping any versions in between), rebuild and restart with the
# same Compose files, and wait until the service is ready. If the rebuild
# fails, the previous version is started again.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

fail() { printf 'ParsRAG update stopped: %s\n' "$1" >&2; exit 1; }

for tool in git docker; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool is not installed or not on PATH."
done
[ -d .git ] || fail "this folder is not a git clone of ParsRAG; download the new release by hand."
[ -z "$(git status --porcelain --untracked-files=no)" ] \
  || fail "files in this copy were changed. Commit or undo them first (git status shows them)."

branch=$(git symbolic-ref -q --short HEAD || true)
if [ -n "$branch" ] && [ "$branch" != main ]; then
  fail "this copy follows the '$branch' branch. Switch to main (git switch main) or update by hand."
fi

echo "Looking for the latest release..."
git fetch --quiet --tags origin
latest=$(git tag -l 'v*' --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -n 1 || true)
[ -n "$latest" ] || fail "no release tags were found."
current=$(tr -d '[:space:]' < VERSION)
if [ "v$current" = "$latest" ]; then
  echo "ParsRAG $current is already the latest release."
  exit 0
fi
echo "Updating ParsRAG $current to ${latest#v}."

# Reuse the Compose files and profile the running stack was started with.
set --
project=parsrag
image=""
app=$(docker compose ps -q app 2>/dev/null || true)
if [ -n "$app" ]; then
  files=$(docker inspect "$app" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')
  old_ifs=$IFS; IFS=,
  for file in $files; do [ -n "$file" ] && set -- "$@" -f "$file"; done
  IFS=$old_ifs
  project=$(docker inspect "$app" --format '{{index .Config.Labels "com.docker.compose.project"}}')
  image=$(docker inspect "$app" --format '{{.Config.Image}}')
  if [ -n "$(docker compose "$@" ps -q ollama 2>/dev/null || true)" ]; then
    set -- "$@" --profile local-model
  fi
fi

# Back up before anything changes.
stamp=$(date +%Y%m%d-%H%M%S)
backup="$ROOT/backups/$stamp-v$current"
mkdir -p "$backup"
[ -f .env ] && cp .env "$backup/env.backup"
volumes=""
for volume in "${project}_qdrant_data" "${project}_app_config"; do
  docker volume inspect "$volume" >/dev/null 2>&1 && volumes="$volumes $volume"
done
if [ -n "$volumes" ]; then
  [ -n "$image" ] || image=qdrant/qdrant:v1.19.1
  echo "Backing up the documents index and settings (the service stops for a moment)..."
  docker compose "$@" stop app qdrant
  for volume in $volumes; do
    if ! docker run --rm --user 0 --entrypoint tar -v "$volume:/data:ro" -v "$backup:/backup" "$image" \
        -czf "/backup/$volume.tar.gz" -C /data .; then
      docker compose "$@" up -d >/dev/null 2>&1 || true
      fail "the backup failed, so nothing was updated."
    fi
  done
fi
cat > "$backup/RESTORE.txt" <<EOF
ParsRAG $current backup, $stamp.
To go back: git checkout v$current, then restore each volume with
  docker run --rm --user 0 --entrypoint tar -v <volume>:/data -v <this folder>:/backup <image> -xzf /backup/<volume>.tar.gz -C /data
and start ParsRAG again. Conversations live in the browser: use the backup
file the app downloaded before this update (Settings > Data > Import).
EOF
echo "Backup saved in $backup"

previous=$(git rev-parse HEAD)
rollback() {
  echo "The update failed. Starting the previous version again..." >&2
  git checkout --quiet "$previous"
  docker compose "$@" up -d --build || true
  fail "the previous version ($current) is running again. Your backup is in $backup"
}
if [ "$branch" = main ]; then
  git pull --quiet --ff-only origin main || rollback "$@"
else
  git checkout --quiet "$latest" || rollback "$@"
fi
echo "Building and starting the new version (this can take several minutes)..."
docker compose "$@" up -d --build || rollback "$@"

address=$(docker compose "$@" port app 8000 2>/dev/null | sed 's/^0\.0\.0\.0/127.0.0.1/' || true)
[ -n "$address" ] || address=127.0.0.1:8000
echo "Waiting for ParsRAG at http://$address ..."
i=0
while [ "$i" -lt 120 ]; do
  if curl -fsS --max-time 3 "http://$address/health/ready" >/dev/null 2>&1; then
    echo "ParsRAG ${latest#v} is ready: http://$address"
    echo "Reload the page in the browser; it shows what changed."
    exit 0
  fi
  i=$((i + 1)); sleep 5
done
echo "ParsRAG ${latest#v} started but is not ready yet; check: docker compose logs app"
