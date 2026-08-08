# Changelog

Todas as mudanças importantes do Novel Reader são registradas aqui.

## [1.0.0-rc1] - 2026-08-08

Primeiro Release Candidate da série 1.0.

### Adicionado
- GUI PySide6 e TUI/CLI full-screen.
- Browser persistente QtWebEngine para fontes dinâmicas.
- Suporte inicial a WebNovel público/acessível pela sessão.
- Índice de livros, capítulos e Power Ranking Fan-Fic.
- Library SQLite com progresso, favoritos, categorias, tags, nota e pin.
- Busca fuzzy e histórico.
- Cache de capítulos/capas e modo offline explícito.
- Pré-cache configurável.
- Sincronização de índice com TTL e refresh forçado.
- Capas em terminal via Chafa/Pillow e Kitty Graphics quando suportado.
- Configuração centralizada.
- Logs, `--debug`, `--doctor`, `--setup`, `--self-test`.
- Backups automáticos SQLite + JSON, integrity check e restauração.
- Lock de instância.
- Relatório de compatibilidade.
- Pacote `.deb`, launchers `.desktop` e ícone.
- Validação pós-instalação de componentes.

### Corrigido
- Detecção falsa de capítulos bloqueados.
- Estabilização de índices grandes/dinâmicos.
- Processo QtWebEngine persistente no CLI.
- Vazamento de sequências `^[[A`/`^[[B` ao retornar de livro na TUI.
- Colisão de atalho `L` do Ranking com Library.
- Ranking progressivo mais rápido.
- Fallback de logs quando o diretório XDG não é gravável.

### Segurança/escopo
O projeto não contorna paywalls, CAPTCHA, login, DRM ou controles de acesso.
