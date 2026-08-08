# Changelog

Todas as mudanças importantes do Novel Reader são registradas aqui.









## [1.0.9] - 2026-08-08

### Reader TUI
- Modo de leitura limpa incondicionalmente imagens Kitty/icat ao entrar no
  capítulo, inclusive capas desenhadas por outra tela/renderer.
- `+` e `-` alteram a densidade/tamanho visual do texto entre compacto,
  normal e grande.
- `W` alterna a largura da coluna de leitura.
- `[` e `]` diminuem/aumentam o espaçamento entre parágrafos.
- Preferências do Reader TUI são salvas no `config.json`.
- Rodapé exibe densidade atual e largura da coluna.

### Observação
O tamanho físico da fonte é controlado pelo emulador de terminal; o Reader
ajusta densidade, largura e paginação para obter um efeito equivalente na TUI.


## [1.0.8] - 2026-08-08

### Corrigido
- Ranking não tenta mais carregar até 250 obras antes de abrir a TUI.
- Primeira carga fica limitada a aproximadamente 20 obras.
- Ao navegar até os últimos itens, o Reader solicita mais um lote de ~20.
- Paginação incremental evita timeout de 35 segundos e reduz uso de CPU/rede.
- O navegador QtWebEngine é reutilizado entre os lotes do mesmo período.


## [1.0.7] - 2026-08-08

### Corrigido
- Fan-Fic Ranking continua carregando além dos 20 itens iniciais.
- O navegador rola repetidamente até o fim da lista para disparar o lazy loading normal da página.
- A captura acumula lotes por URL e mira até 250 posições.
- A estabilização não encerra mais o ranking ao detectar apenas o primeiro lote estável.


## [1.0.6] - 2026-08-08

### Corrigido
- Parser do Fan-Fic Ranking refeito usando a estrutura real da página.
- JSON-LD `ItemList.position` agora é a fonte primária da posição oficial.
- `i.ff_number` é usado apenas como confirmação/fallback do DOM.
- `strong.ff_number > span` permanece exclusivamente como Power.
- Cards são lidos diretamente de `.j_rank_wrapper > section`.
- Título, autor, sinopse e capa passam a usar seletores estruturais do card.
- Removida a renumeração artificial de posições esparsas: o rank exibido volta
  a ser sempre o rank oficial do WebNovel.


## [1.0.5] - 2026-08-08

### Corrigido
- Ranking não usa mais nenhum fallback numérico para posição.
- Somente `i.ff_number` pode fornecer a posição original do WebNovel.
- `strong.ff_number` continua reservado exclusivamente para Power.
- Rankings carregados de listas virtualizadas são ordenados pelo rank original
  e recebem uma posição visual contínua `1, 2, 3...`.
- A posição original do WebNovel é preservada internamente em `source_rank`.


## [1.0.4] - 2026-08-08

### Corrigido
- Corrigido crash do processo QtWebEngine no pacote `.deb` quando
  `novel-reader-cli` era iniciado fora de `/opt/novel-reader`.
- O worker agora recebe explicitamente o diretório da aplicação no
  `PYTHONPATH` e usa esse diretório como `cwd`.
- Stderr do worker não é mais descartado; falhas agora exibem o último detalhe
  útil junto ao código de saída.
- `novel-reader-install-check` passa a validar também a importação do worker do
  navegador.


## [1.0.3] - 2026-08-08

### Corrigido
- Ranking diferencia explicitamente `i.ff_number` (posição) de
  `strong.ff_number > span` (Power).
- Power e posição deixam de compartilhar heurísticas numéricas.
- Capas do Fan-Fic Ranking agora usam `img[data-original]` como fonte
  preferencial, com fallback para `src`/`data-src`.
- URLs de capa iniciadas por `//book-pic.webnovel.com/...` são normalizadas
  para HTTPS.


## [1.0.2] - 2026-08-08

### Corrigido
- Fan-Fic Power Ranking agora usa explicitamente o elemento `.ff_number` do
  WebNovel como posição da obra.
- Valores de Power como `5`, `12`, `51`, `200` e `356` deixam de ser
  confundidos com posições do ranking.
- Valores exibidos como `001`, `002`, `012` são convertidos para `1`, `2`,
  `12` respectivamente.


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
