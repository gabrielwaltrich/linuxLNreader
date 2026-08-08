# Contribuindo

Obrigado por contribuir com o Novel Reader.

## Ambiente

```bash
git clone https://github.com/gabrielwaltrich/linuxLNreader.git
cd linuxLNreader
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Antes de enviar uma mudança

```bash
python -m compileall -q novel_reader
pytest -q
novel-reader-cli --self-test
```

Para alterações na TUI:

```bash
./scripts/terminal-checklist.sh
```

## Regras de fontes

Adapters devem operar somente sobre conteúdo público ou normalmente acessível
pela sessão do usuário. Não implemente bypass de paywall, CAPTCHA, DRM, login
ou outros controles de acesso.

## Pull requests

Descreva:
- problema resolvido;
- comportamento anterior;
- comportamento novo;
- testes executados;
- distro e terminal, quando relevante.
