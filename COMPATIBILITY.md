# Compatibility matrix

Este arquivo separa testes automatizados de testes manuais.

## Automatizado em CI

| Ambiente | compileall | pytest | self-test |
|---|---:|---:|---:|
| Ubuntu / Python 3.10 | CI | CI | CI |
| Ubuntu / Python 3.11 | CI | CI | CI |
| Ubuntu / Python 3.12 | CI | CI | CI |
| Ubuntu / Python 3.13 | CI | CI | CI |
| Fedora latest container | CI | CI | CI |
| Arch latest container | CI | CI | CI |

Containers validam Python, banco, cache, configuração, busca, backups e código da TUI, mas **não substituem um terminal gráfico real**.

## Validação manual necessária antes da 1.0

| Distro | Terminal | Status |
|---|---|---|
| Ubuntu/Debian | GNOME Terminal | pendente |
| Ubuntu/Debian | Kitty | pendente |
| KDE/qualquer distro | Konsole | pendente |
| Fedora | GNOME Terminal | pendente |
| Arch | Kitty | pendente |

Execute:

```bash
./scripts/terminal-checklist.sh
```

## Fluxos críticos

1. Home → Ranking → livro → voltar → outro livro.
2. Library → livro → capítulo → voltar.
3. Busca Unificada → resultado → Library/favorito.
4. Offline → capítulo em cache e capítulo ausente.
5. Cache manager → status e limpeza.
6. Sync → `R` com TTL e `F5` forçado.
7. Saída → terminal restaurado sem `^[[A`, `^[[B` ou modo raw residual.
8. Capa Chafa/Pillow.
9. Kitty `icat` somente onde o protocolo for realmente suportado.

## Relatório para bugs

```bash
novel-reader-cli --doctor
novel-reader-cli --self-test
novel-reader-cli --compat-report compat.json
novel-reader-cli --debug
```
