#!/usr/bin/env bash
set -u

PYTHON="${PYTHON:-python3}"
FAILURES=0
WARNINGS=0

ok()   { printf '  [OK]   %s\n' "$1"; }
fail() { printf '  [ERRO] %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
warn() { printf '  [OPC]  %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

python_module() {
  "$PYTHON" - "$1" >/dev/null 2>&1 <<'PY'
import importlib.util, sys
name = sys.argv[1]
raise SystemExit(0 if importlib.util.find_spec(name) else 1)
PY
}

echo "Novel Reader — validação da instalação"
echo

echo "Obrigatórios:"

if has_cmd "$PYTHON"; then
  if "$PYTHON" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
  then
    ok "Python >= 3.10 ($("$PYTHON" -V 2>&1))"
  else
    fail "Python 3.10+ é obrigatório"
  fi
else
  fail "python3 não encontrado"
fi

if python_module "PySide6"; then
  ok "PySide6"
else
  fail "PySide6 não encontrado"
fi

if python_module "PySide6.QtWebEngineWidgets"; then
  ok "QtWebEngineWidgets"
else
  fail "QtWebEngineWidgets não encontrado"
fi

if python_module "PIL"; then
  ok "Pillow"
else
  fail "Pillow não encontrado"
fi

if python_module "httpx"; then
  ok "httpx"
else
  fail "httpx não encontrado"
fi

if python_module "bs4"; then
  ok "BeautifulSoup4"
else
  fail "BeautifulSoup4 não encontrado"
fi

if ldconfig -p 2>/dev/null | grep -q 'libxcb\.so'; then
  ok "libxcb"
else
  fail "libxcb não encontrado"
fi

if ldconfig -p 2>/dev/null | grep -Eq 'libxcb-cursor\.so|libxcb_cursor\.so'; then
  ok "libxcb-cursor"
else
  fail "libxcb-cursor não encontrado"
fi

if has_cmd novel-reader-cli; then
  ok "comando novel-reader-cli"
else
  fail "comando novel-reader-cli não encontrado"
fi

if has_cmd novel-reader; then
  ok "comando novel-reader"
else
  fail "comando novel-reader não encontrado"
fi

echo
echo "Opcionais:"

if has_cmd chafa; then
  ok "Chafa ($(command -v chafa))"
else
  warn "Chafa ausente — capas no terminal usarão outro backend"
fi

if has_cmd kitten; then
  ok "kitten ($(command -v kitten))"
else
  warn "kitten ausente — Kitty Graphics não estará disponível"
fi

terminal="${TERM_PROGRAM:-${TERM:-desconhecido}}"
if [[ -n "${KITTY_WINDOW_ID:-}" ]] || [[ "$terminal" == *kitty* ]] || \
   [[ "$terminal" == *wezterm* ]] || [[ "$terminal" == *ghostty* ]]; then
  ok "terminal compatível com protocolo gráfico detectado: $terminal"
else
  warn "terminal atual não anuncia Kitty Graphics: $terminal"
fi

echo
if [[ "$FAILURES" -eq 0 ]]; then
  echo "Resultado: instalação obrigatória OK."
  if [[ "$WARNINGS" -gt 0 ]]; then
    echo "Há $WARNINGS recurso(s) opcional(is) indisponível(is)."
  fi
  exit 0
else
  echo "Resultado: $FAILURES requisito(s) obrigatório(s) ausente(s)."
  echo "Execute também: novel-reader-cli --doctor"
  exit 2
fi
