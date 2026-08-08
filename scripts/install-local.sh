#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"

mkdir -p \
  "$PREFIX/share/novel-reader" \
  "$PREFIX/bin" \
  "$PREFIX/share/applications" \
  "$PREFIX/share/icons/hicolor/scalable/apps"

cp -a "$ROOT/novel_reader" "$PREFIX/share/novel-reader/"
cp "$ROOT/main.py" "$PREFIX/share/novel-reader/"
cp "$ROOT/cli.py" "$PREFIX/share/novel-reader/"

cat > "$PREFIX/bin/novel-reader" <<EOF
#!/usr/bin/env bash
exec /usr/bin/env python3 "$PREFIX/share/novel-reader/main.py" "\$@"
EOF

cat > "$PREFIX/bin/novel-reader-cli" <<EOF
#!/usr/bin/env bash
exec /usr/bin/env python3 "$PREFIX/share/novel-reader/cli.py" "\$@"
EOF

chmod +x "$PREFIX/bin/novel-reader" "$PREFIX/bin/novel-reader-cli"

cp "$ROOT/packaging/novel-reader.desktop" \
  "$PREFIX/share/applications/novel-reader.desktop"
cp "$ROOT/packaging/novel-reader-cli.desktop" \
  "$PREFIX/share/applications/novel-reader-cli.desktop"
cp "$ROOT/packaging/icons/novel-reader.svg" \
  "$PREFIX/share/icons/hicolor/scalable/apps/novel-reader.svg"

echo
echo "Novel Reader instalado em $PREFIX"
echo "Comandos:"
echo "  novel-reader"
echo "  novel-reader-cli"
echo
echo "Se $PREFIX/bin não estiver no PATH, adicione:"
echo "  export PATH=\"$PREFIX/bin:\$PATH\""
