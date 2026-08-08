# Changelog

Todas as mudanças importantes do Novel Reader são registradas aqui.


## [1.0.1] - 2026-08-08

Atualização focada na experiência visual da interface gráfica.

### GUI
- Novo sistema visual claro e escuro.
- Cabeçalho de aplicação com ações principais.
- Campo de URL reorganizado em card próprio.
- Área de leitura com superfície, espaçamento e tipografia mais refinados.
- Estado vazio do Reader redesenhado.
- Barra de leitura inferior compacta e consistente.
- Botões primários, secundários, acento e perigo padronizados.
- Library redesenhada com card de detalhes, busca e árvore mais legíveis.
- Preferências redesenhadas.
- Scrollbars, campos, combos, tooltips e status bar atualizados.
- Título e textos antigos de versões de desenvolvimento removidos.


## [1.0.0] - 2026-08-08

Primeira versão estável do Novel Reader para Linux.

### Destaques
- GUI em PySide6 e interface TUI/CLI em tela cheia.
- Suporte inicial ao WebNovel para conteúdo público/acessível pela sessão.
- Power Ranking Fan-Fic.
- Library SQLite com progresso, favoritos, categorias, tags, notas e pins.
- Busca fuzzy e histórico.
- Cache de capítulos e capas.
- Modo offline explícito e pré-cache.
- Sincronização inteligente de índice com TTL.
- Capas no terminal com Chafa/Pillow e Kitty Graphics quando suportado.
- Configuração centralizada.
- Logs, modo `--debug`, `--doctor`, `--setup` e `--self-test`.
- Backup automático SQLite + JSON e restauração validada.
- Lock de instância.
- Relatório de compatibilidade.
- Pacote `.deb`, launchers `.desktop`, ícone e validador pós-instalação.

### Correções importantes
- Detecção falsa de capítulos bloqueados.
- Estabilização de índices grandes e dinâmicos.
- Browser QtWebEngine persistente no CLI.
- Correção de sequências `^[[A`/`^[[B` ao retornar de livros na TUI.
- Correção da colisão do atalho `L` no Ranking.
- Carregamento progressivo do Ranking mais rápido.
- Fallback do sistema de logs para ambientes com diretório XDG não gravável.

### Escopo
O Novel Reader não contorna paywalls, CAPTCHA, login, DRM ou outros controles
de acesso.

## [1.0.0-rc1] - 2026-08-08

Primeiro Release Candidate da série 1.0.
