# Novel Reader for Linux — 1.1

Leitor de **novels e webnovels para Linux**, com interface gráfica em PySide6 e uma TUI completa para terminal.

O projeto foi desenvolvido para oferecer uma experiência de leitura confortável no Linux, com Library local, histórico, leitura offline, busca, rankings, cache, backups e suporte a capas no terminal.

> **Versão apresentada neste README:** `1.1`
>
> **Suporte nativo atual:** **WebNovel**

## ⚠️ Suporte a sites

Atualmente, o Novel Reader possui suporte nativo somente ao **WebNovel**.

Isso significa que os recursos de:

- abertura de livros por URL;
- leitura de capítulos;
- índice de capítulos;
- metadados da obra;
- capas;
- autor e sinopse;
- Fan-Fic Power Ranking;
- carregamento progressivo do ranking;

foram desenvolvidos e testados especificamente para páginas do **WebNovel**.

O projeto já possui uma arquitetura baseada em **sources/adapters**, portanto a intenção é adicionar suporte nativo a **outros sites de novels e webnovels no futuro**, sem precisar reescrever o Reader inteiro.

Possíveis fontes futuras poderão ser adicionadas como adapters independentes.

> O suporte futuro a outros sites dependerá da estrutura pública de cada plataforma e respeitará seus controles de acesso.

O Novel Reader **não tenta contornar**:

- capítulos pagos;
- paywalls;
- CAPTCHA;
- login obrigatório;
- DRM;
- controles de acesso.

---

## Recursos principais

### Interface gráfica

A GUI recebeu uma renovação visual completa, incluindo:

- tema claro e escuro consistentes;
- cabeçalho reorganizado;
- campo de URL em card próprio;
- área de leitura mais limpa;
- melhor hierarquia visual;
- botões e campos padronizados;
- Library redesenhada;
- preferências reorganizadas;
- scrollbars, tooltips e estados vazios atualizados.

### Leitura

- leitura em GUI ou terminal;
- navegação entre capítulos;
- progresso por capítulo;
- continuar de onde parou;
- paginação no TUI;
- largura da coluna configurável;
- densidade do texto configurável;
- espaçamento entre parágrafos configurável;
- cache local de capítulos;
- leitura offline de conteúdo previamente armazenado.

### Reader TUI 1.1

Durante a leitura no terminal, capas Kitty são removidas automaticamente para não ficarem sobre o texto.

Atalhos de leitura:

| Tecla | Ação |
|---|---|
| `←` / `→` | página anterior/próxima |
| `+` / `-` | texto mais compacto/normal/grande |
| `W` | alternar largura da coluna |
| `[` / `]` | diminuir/aumentar espaçamento entre parágrafos |
| `G` | ir para página |
| `Q` / `Esc` | voltar ao índice |

As preferências são salvas no arquivo de configuração.

> O tamanho físico da fonte continua sendo controlado pelo emulador de terminal. O Novel Reader altera largura, densidade e paginação.

---

## WebNovel

O WebNovel é atualmente a única fonte suportada nativamente.

O Reader reconhece:

- URLs de livros;
- URLs de capítulos;
- páginas de índice;
- metadados;
- capas;
- autor;
- sinopse;
- Fan-Fic Power Ranking.

### Fan-Fic Power Ranking

O parser do ranking foi reformulado para usar a estrutura real da página.

A posição do ranking é obtida prioritariamente pelo JSON-LD oficial da página:

```text
ItemList.position
```

Com fallback estrutural para:

```css
i.ff_number
```

O valor de Power é tratado separadamente:

```css
strong.ff_number > span
```

As capas são extraídas de:

```css
img[data-original]
```

URLs iniciadas por:

```text
//book-pic.webnovel.com/...
```

são normalizadas automaticamente para HTTPS.

### Ranking com carregamento progressivo

O Reader não tenta mais carregar os 250 itens de uma só vez.

O comportamento atual é:

```text
abre o ranking
→ carrega aproximadamente 20 obras
→ usuário navega até o fim
→ carrega mais aproximadamente 20
→ repete até o limite disponível
```

Isso reduz:

- tempo de abertura;
- uso de CPU;
- uso de rede;
- risco de timeout do QtWebEngine.

---

## Library

A Library local utiliza SQLite e oferece:

- histórico;
- favoritos;
- progresso;
- continuar leitura;
- próximo capítulo não lido;
- categorias;
- tags;
- nota pessoal de 0 a 5;
- livros fixados;
- busca fuzzy;
- importação e exportação JSON.

Categorias disponíveis:

```text
Lendo
Concluído
Planejo ler
```

---

## Busca fuzzy

A busca tolera pequenas diferenças de escrita.

Exemplos:

```text
harry poter  → Harry Potter
cultivtion   → Cultivation
joao         → João
```

São considerados:

- título;
- autor;
- tags;
- categoria;
- rankings já carregados na sessão.

O histórico das pesquisas é salvo localmente.

---

## Offline e cache

O Reader possui modo offline explícito.

```bash
novel-reader-cli --offline
```

Capítulos já armazenados em cache podem ser lidos sem rede.

No índice TUI:

```text
◆  capítulo disponível offline
A  preparar próximos capítulos
O  filtrar somente capítulos offline
X  gerenciar cache
```

Ver status do cache:

```bash
novel-reader-cli --cache-status
```

Limpar:

```bash
novel-reader-cli --cache-clear chapters
novel-reader-cli --cache-clear covers
novel-reader-cli --cache-clear all
```

O limite padrão é aproximadamente:

```text
500 MB
```

Quando o limite é ultrapassado, os arquivos mais antigos são removidos primeiro.

---

## Capas no terminal

Backends disponíveis:

```text
Auto
Kitten / Kitty Graphics
Chafa
Pillow
Desativado
```

### Kitty / kitten

O executável `kitten` sozinho não garante que imagens Kitty serão exibidas.

O terminal também precisa implementar o Kitty Graphics Protocol.

Terminais conhecidos por possuir suporte incluem, dependendo da versão/configuração:

- Kitty;
- WezTerm;
- Ghostty.

Durante a leitura de capítulos, imagens Kitty são apagadas automaticamente para evitar sobreposição sobre o texto.

Chafa continua sendo recomendado como fallback compatível com diversos terminais.

---

# Instalação

## Ubuntu / Debian — pacote `.deb`

Baixe o pacote `.deb` na página de Releases.

Exemplo:

```bash
sudo apt install ./novel-reader_1.0.9_all.deb
```

Depois execute a GUI:

```bash
novel-reader
```

ou a TUI:

```bash
novel-reader-cli
```

---

## Validação pós-instalação

O pacote instala o comando:

```bash
novel-reader-install-check
```

Ele verifica componentes obrigatórios como:

- Python 3.10+;
- PySide6;
- QtWebEngine;
- Pillow;
- httpx;
- BeautifulSoup4;
- libxcb;
- libxcb-cursor;
- worker do QtWebEngine;
- `novel-reader`;
- `novel-reader-cli`.

E componentes opcionais como:

- Chafa;
- kitten;
- suporte do terminal ao Kitty Graphics Protocol.

Diagnóstico detalhado:

```bash
novel-reader-cli --doctor
```

Self-test:

```bash
novel-reader-cli --self-test
```

---

## Instalação para desenvolvimento

Clone o projeto:

```bash
git clone https://github.com/gabrielwaltrich/linuxLNreader.git
cd linuxLNreader
```

Crie um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale:

```bash
python -m pip install -e ".[dev]"
```

### Dependências comuns no Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip libxcb-cursor0
```

Opcional:

```bash
sudo apt install chafa
```

---

# Uso

## GUI

```bash
novel-reader
```

Pelo código-fonte:

```bash
python main.py
```

## TUI / CLI

```bash
novel-reader-cli
```

Ou:

```bash
python cli.py
```

Abrir diretamente uma obra do WebNovel:

```bash
novel-reader-cli "https://www.webnovel.com/book/..."
```

---

## Tela inicial da TUI

```text
Abrir por link
Explorar Fan-Fic Ranking
Minha Library
Busca unificada
Offline e Cache
Continuar última leitura
Sair
```

---

# Atalhos principais

## Índice do livro

| Tecla | Ação |
|---|---|
| `↑` / `↓` | mover |
| `Enter` | abrir capítulo |
| `/` | buscar |
| `L` | adicionar/remover da Library |
| `F` | favorito |
| `A` | preparar capítulos offline |
| `O` | filtro offline |
| `X` | gerenciador de cache |
| `R` | atualizar índice se necessário |
| `F5` | forçar sincronização |
| `I` | mudar backend da capa |
| `?` / `F2` | diagnóstico Kitty |
| `Q` | sair |

## Fan-Fic Power Ranking

| Tecla | Ação |
|---|---|
| `↑` / `↓` | selecionar / avançar na lista |
| `←` / `→` | mudar período |
| `Enter` | abrir obra |
| `L` | adicionar/remover da Library |
| `F` | favorito |
| `/` | buscar |
| `Esc` | voltar |

Ao chegar perto do final dos itens carregados, o próximo lote é solicitado automaticamente.

## Library

| Tecla | Ação |
|---|---|
| `Enter` | abrir |
| `F` | favorito |
| `P` | fixar |
| `T` | tags |
| `N` | nota |
| `C` | categoria |
| `V` | visão/categoria |
| `O` | ordenação |
| `/` | buscar |
| `B` | exportar JSON |
| `M` | importar JSON |
| `D` | ocultar da Library |
| `Esc` | voltar |

---

# Configuração

Arquivo principal:

```text
~/.config/novel-reader/config.json
```

Exibir configuração:

```bash
novel-reader-cli --config-show
```

Exemplos:

```bash
novel-reader-cli --config-set cover_mode=chafa
novel-reader-cli --config-set prefetch_count=5
novel-reader-cli --config-set cache_limit_mb=800
novel-reader-cli --config-set theme=dark
```

Configurações do Reader TUI também são salvas automaticamente quando alteradas durante a leitura.

---

# Backup e segurança

Backup manual:

```bash
novel-reader-cli --backup-now
```

Listar backups:

```bash
novel-reader-cli --backup-list
```

Verificar banco:

```bash
novel-reader-cli --db-check
```

Restaurar:

```bash
novel-reader-cli --restore-backup ARQUIVO.sqlite3
```

Por padrão, o Reader mantém os **5 backups mais recentes**.

O banco também utiliza um lock de instância para reduzir risco de duas execuções gravarem simultaneamente na mesma Library.

---

# Diagnóstico

## Doctor

```bash
novel-reader-cli --doctor
```

## Setup assistido

```bash
novel-reader-cli --setup
```

O setup não executa `sudo` silenciosamente.

## Self-test

```bash
novel-reader-cli --self-test
```

## Relatório de compatibilidade

```bash
novel-reader-cli --compat-report
```

Salvar em JSON:

```bash
novel-reader-cli --compat-report compat.json
```

## Debug

```bash
novel-reader-cli --debug
```

Logs normalmente ficam em:

```text
~/.local/state/novel-reader/novel-reader.log
```

---

# Dados locais

O Reader mantém localmente:

- Library SQLite;
- histórico;
- cache de capítulos;
- cache de capas;
- configuração;
- histórico de busca;
- backups;
- logs;
- perfil persistente do QtWebEngine.

A desinstalação do programa não deve apagar automaticamente esses dados.

---

# Estrutura do projeto

```text
novel_reader/
├── browser/          QtWebEngine e sessão persistente
├── database/         Library SQLite
├── services/         cache, backup, busca, ranking e diagnóstico
├── sources/          adapters de fontes
├── ui/               interface gráfica
├── terminal_tui.py   leitor TUI
├── startup_tui.py    Home / Ranking / Library
├── cli.py            CLI
└── models.py         modelos principais
```

A pasta `sources/` existe justamente para permitir a expansão futura para novos sites.

Hoje:

```text
sources/
└── WebNovel  ← suporte nativo atual
```

Futuramente, a arquitetura permite algo como:

```text
sources/
├── WebNovel
├── OutroSite
├── OutraPlataforma
└── ...
```

sem alterar o funcionamento principal da Library, Reader, cache e interfaces.

---

# Desenvolvimento

Rodar testes:

```bash
pytest -q
```

Compilar:

```bash
python -m compileall -q novel_reader
```

Smoke test:

```bash
./scripts/smoke-test.sh
```

Checklist de terminal:

```bash
./scripts/terminal-checklist.sh
```

Gerar `.deb`:

```bash
./scripts/build-deb.sh
```

---

# Compatibilidade

O projeto é desenvolvido para Linux.

Consulte:

```text
COMPATIBILITY.md
KNOWN-ISSUES.md
```

Comportamentos ligados a Kitty Graphics e ao modo raw do terminal devem ser testados em terminais reais.

---

# Roadmap após 1.1

Algumas áreas planejadas para evolução futura:

- novos sites com adapters nativos;
- mais fontes além do WebNovel;
- melhorias contínuas na GUI;
- novos modos de organização da Library;
- expansão do offline;
- melhorias de sincronização;
- otimizações de carregamento de rankings;
- suporte adicional a terminais e formatos de capa.

A prioridade é adicionar novos sites de forma **nativa e isolada por adapter**, preservando o comportamento já estável do Reader.

---

# Contribuindo

Veja:

```text
CONTRIBUTING.md
```

Adapters para novas fontes devem operar apenas sobre conteúdo público ou normalmente acessível pela sessão do usuário.

Não serão aceitos mecanismos para contornar paywalls, CAPTCHA, DRM ou controles de acesso.

---

# Licença

MIT. Consulte `LICENSE`.

# Repositório

https://github.com/gabrielwaltrich/linuxLNreader

---

Ao reportar um problema, envie quando possível:

```bash
novel-reader-cli --doctor
novel-reader-cli --self-test
novel-reader-cli --compat-report compat.json
```

Isso ajuda a identificar problemas específicos de distro, dependências e terminal.
