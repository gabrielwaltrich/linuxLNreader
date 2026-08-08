#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"

rm -f \
  "$PREFIX/bin/novel-reader" \
  "$PREFIX/bin/novel-reader-cli" \
  "$PREFIX/share/applications/novel-reader.desktop" \
  "$PREFIX/share/applications/novel-reader-cli.desktop" \
  "$PREFIX/share/icons/hicolor/scalable/apps/novel-reader.svg"

rm -rf "$PREFIX/share/novel-reader"

echo "Novel Reader removido de $PREFIX."
echo "Dados da Library/config/cache do usuário foram preservados."
