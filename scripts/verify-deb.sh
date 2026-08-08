#!/usr/bin/env bash
set -euo pipefail

DEB="${1:?uso: ./scripts/verify-deb.sh ARQUIVO.deb}"

echo "== metadata =="
dpkg-deb -I "$DEB"
echo
echo "== arquivos principais =="
dpkg-deb -c "$DEB" | grep -E \
  'usr/bin/novel-reader|usr/share/applications|novel-reader.svg|opt/novel-reader/cli.py'
