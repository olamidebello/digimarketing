#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
  echo 'Run this deployment script as root.' >&2
  exit 1
fi
exec 9>/run/digimarketing-deploy.lock
flock -n 9 || { echo 'A DigiMarketing deployment is already running.' >&2; exit 1; }
if ! command -v ansible-pull >/dev/null || ! command -v git >/dev/null; then
  apt-get update
  apt-get install -y git ansible-core
fi
exec ansible-pull --url https://github.com/olamidebello/digimarketing.git \
  --checkout main --directory /opt/digimarketing-bootstrap \
  --inventory localhost, --connection local \
  ansible/pull-and-deploy.yml "$@"
