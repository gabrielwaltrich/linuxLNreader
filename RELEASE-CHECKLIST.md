# Checklist de Release — Novel Reader 1.0.0

## Automático
- [x] `python -m compileall -q novel_reader`
- [x] `pytest -q`
- [x] versão final `1.0.0`
- [x] `.deb` gera sem erro
- [x] `dpkg-deb -I` válido
- [x] `novel-reader-install-check` incluído no pacote
- [x] LICENSE
- [x] CHANGELOG
- [x] CONTRIBUTING
- [x] README para GitHub

## Ainda recomendado em máquina real
- [ ] instalação limpa em Ubuntu/Debian
- [ ] GNOME Terminal
- [ ] Konsole
- [ ] Kitty
- [ ] launcher gráfico
- [ ] Ranking → livro → voltar → outro livro
- [ ] nenhuma sequência `^[[A`/`^[[B`
- [ ] capa Kitty em terminal compatível
- [ ] backup/restauração com Library real

## GitHub
- [ ] criar tag `v1.0.0`
- [ ] criar GitHub Release
- [ ] anexar `.deb`
- [ ] anexar ZIP do código
- [ ] adicionar screenshots/GIF quando disponíveis
