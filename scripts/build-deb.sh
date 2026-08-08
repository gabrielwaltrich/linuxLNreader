#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-1.0.9}"
ARCH="${ARCH:-all}"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"

# Some mounted workspaces force the setgid bit on newly-created directories,
# which dpkg-deb rejects for DEBIAN/. Build in /tmp by default to avoid that.
BUILD_BASE="${BUILD_BASE:-$(mktemp -d -t novel-reader-deb.XXXXXX)}"
PKG_ROOT="$BUILD_BASE/novel-reader"
_cleanup_build() {
  if [[ "${KEEP_BUILD:-0}" != "1" ]]; then
    rm -rf "$BUILD_BASE"
  fi
}
trap _cleanup_build EXIT

rm -rf "$PKG_ROOT"
mkdir -p \
  "$PKG_ROOT/DEBIAN" \
  "$PKG_ROOT/opt/novel-reader" \
  "$PKG_ROOT/usr/bin" \
  "$PKG_ROOT/usr/share/applications" \
  "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps" \
  "$PKG_ROOT/usr/share/doc/novel-reader"

# Project files used at runtime.
cp -a "$ROOT/novel_reader" "$PKG_ROOT/opt/novel-reader/"
cp "$ROOT/main.py" "$PKG_ROOT/opt/novel-reader/"
cp "$ROOT/cli.py" "$PKG_ROOT/opt/novel-reader/"
cp "$ROOT/pyproject.toml" "$PKG_ROOT/opt/novel-reader/"
cp "$ROOT/README.md" "$PKG_ROOT/usr/share/doc/novel-reader/README.md"
cp "$ROOT/scripts/install-check.sh"   "$PKG_ROOT/usr/bin/novel-reader-install-check"
chmod 0755 "$PKG_ROOT/usr/bin/novel-reader-install-check"
cp "$ROOT/KNOWN-ISSUES.md" "$PKG_ROOT/usr/share/doc/novel-reader/KNOWN-ISSUES.md"
cp "$ROOT/COMPATIBILITY.md" "$PKG_ROOT/usr/share/doc/novel-reader/COMPATIBILITY.md"
cp "$ROOT/LICENSE" "$PKG_ROOT/usr/share/doc/novel-reader/LICENSE"
cp "$ROOT/CHANGELOG.md" "$PKG_ROOT/usr/share/doc/novel-reader/CHANGELOG.md"

cp "$ROOT/packaging/novel-reader.desktop" \
  "$PKG_ROOT/usr/share/applications/novel-reader.desktop"
cp "$ROOT/packaging/novel-reader-cli.desktop" \
  "$PKG_ROOT/usr/share/applications/novel-reader-cli.desktop"
cp "$ROOT/packaging/icons/novel-reader.svg" \
  "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/novel-reader.svg"

cat > "$PKG_ROOT/usr/bin/novel-reader" <<'EOF'
#!/usr/bin/env bash
set -e
exec /usr/bin/python3 /opt/novel-reader/main.py "$@"
EOF

cat > "$PKG_ROOT/usr/bin/novel-reader-cli" <<'EOF'
#!/usr/bin/env bash
set -e
exec /usr/bin/python3 /opt/novel-reader/cli.py "$@"
EOF

chmod 0755 \
  "$PKG_ROOT/usr/bin/novel-reader" \
  "$PKG_ROOT/usr/bin/novel-reader-cli"

cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: novel-reader
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Novel Reader Project
Depends: python3 (>= 3.10), python3-pyside6.qtwidgets, python3-pyside6.qtwebenginecore, python3-pyside6.qtwebenginewidgets, python3-httpx, python3-bs4, python3-pil, libxcb-cursor0
Recommends: chafa
Description: Novel and webnovel reader for Linux
 Novel Reader provides a graphical reader and a full-screen terminal interface,
 Library management, offline cache, ranking browsing and public WebNovel
 support.
EOF

cat > "$PKG_ROOT/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env bash
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi

echo
echo "Validando componentes do Novel Reader..."
if /usr/bin/novel-reader-install-check; then
  echo "Novel Reader instalado com os requisitos obrigatórios disponíveis."
else
  code=$?
  echo "Aviso: a validação encontrou requisito(s) ausente(s) (código $code)."
  echo "Execute 'novel-reader-cli --doctor' para instruções detalhadas."
fi

exit 0
EOF

cat > "$PKG_ROOT/DEBIAN/postrm" <<'EOF'
#!/usr/bin/env bash
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications || true
fi
exit 0
EOF

chmod 0755 "$PKG_ROOT/DEBIAN/postinst" "$PKG_ROOT/DEBIAN/postrm"

mkdir -p "$OUT_DIR"

# dpkg-deb rejects setgid/setuid bits on DEBIAN even when inherited by the
# underlying filesystem. Strip them at the last possible moment.
chmod 0755 "$PKG_ROOT/DEBIAN"
chmod 0644 "$PKG_ROOT/DEBIAN/control"
chmod 0755 "$PKG_ROOT/DEBIAN/postinst" "$PKG_ROOT/DEBIAN/postrm"

dpkg-deb --build --root-owner-group \
  "$PKG_ROOT" \
  "$OUT_DIR/novel-reader_${VERSION}_${ARCH}.deb"

echo "$OUT_DIR/novel-reader_${VERSION}_${ARCH}.deb"
