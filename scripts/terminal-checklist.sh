#!/usr/bin/env bash
set -euo pipefail
PYTHON="${PYTHON:-python3}"
echo "Novel Reader — checklist manual de terminal"
"$PYTHON" cli.py --compat-report
cat <<'EOF'

[ ] Home abre e setas funcionam
[ ] Ranking abre
[ ] Ranking → livro → voltar → outro livro
[ ] Nenhum ^[[A / ^[[B aparece na tela
[ ] L adiciona/remove da Library
[ ] F favorita/desfavorita
[ ] / busca fuzzy funciona
[ ] H abre histórico da busca
[ ] Capítulo abre e volta ao índice
[ ] A prepara capítulos offline
[ ] O filtra capítulos offline
[ ] X abre gerenciador de cache
[ ] R respeita TTL
[ ] F5 força sync
[ ] ? / F2 mostra diagnóstico Kitty
[ ] Capa Chafa/Pillow renderiza
[ ] Capa Kitty renderiza somente em terminal compatível
[ ] Q/Esc restauram o terminal corretamente
EOF
