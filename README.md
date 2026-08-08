# Novel Reader for Linux
# Suporte oficial da 1.0 apenas para o site WEBNOVEL

Leitor de **lightnovels e webnovels para Linux**, com interface gráfica e uma TUI
completa para terminal.

O projeto nasceu com foco em uma experiência de leitura confortável no Linux,
com Library local, histórico, leitura offline, busca, rankings e suporte a
capas no terminal.

> **Versão estável:** `1.0.0`

## Recursos

### Leitura
- leitura de capítulos em GUI ou terminal;
- navegação entre capítulos;
- progresso por capítulo;
- continuar de onde parou;
- largura, margens e tamanho do texto configuráveis;
- temas de leitura;
- cache local.

### WebNovel
Suporte inicial ao WebNovel para conteúdo que esteja normalmente acessível ao
usuário.

Inclui:
- URL de livro;
- URL de capítulo;
- índice de capítulos;
- metadados da obra;
- capa;
- autor e sinopse;
- Power Ranking Fan-Fic;
- listas carregadas progressivamente.

O projeto **não tenta contornar** capítulos pagos, paywalls, CAPTCHA, login,
DRM ou outros controles de acesso.

### Library
A Library local utiliza SQLite e oferece:
- histórico;
- favoritos;
- progresso;
- categorias:
  - Lendo
  - Concluído
  - Planejo ler
- tags;
- nota pessoal de 0 a 5;
- livros fixados;
- busca;
- continuar leitura;
- próximo não lido.

### Busca
A busca aceita pequenas diferenças de escrita:

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
- rankings já carregados.

O histórico de pesquisas é salvo localmente.

### Offline
O Reader possui modo offline explícito.

Capítulos que já estão em cache podem ser lidos sem rede.

```bash
novel-reader-cli --offline
```

No TUI:

```text
◆  capítulo disponível offline
O  filtrar apenas capítulos offline
A  preparar próximos capítulos
X  gerenciar cache
```

### Capas no terminal
Backends disponíveis:

```text
Auto
Kitten / Kitty Graphics
Chafa
Pillow
Desativado
```

Chafa é recomendado para uma experiência consistente em diversos terminais.

A presença do executável `kitten` sozinha não garante suporte ao Kitty Graphics
Protocol. O terminal atual também precisa implementar o protocolo.

## Instalação

### Ubuntu / Debian — pacote `.deb`

Baixe o pacote da página de Releases e execute:

```bash
sudo apt install ./novel-reader_1.0.0_all.deb
```

Depois:

```bash
novel-reader
```

ou:

```bash
novel-reader-cli
```

O pacote instala automaticamente as dependências Debian obrigatórias quando
elas estiverem disponíveis nos repositórios configurados.

### Validação pós-instalação

O pacote instala:

```bash
novel-reader-install-check
```

Ele verifica:

**Obrigatórios**
- Python 3.10+;
- PySide6;
- QtWebEngine;
- Pillow;
- httpx;
- BeautifulSoup4;
- libxcb;
- libxcb-cursor;
- comandos `novel-reader` e `novel-reader-cli`.

**Opcionais**
- Chafa;
- `kitten`;
- suporte do terminal ao Kitty Graphics Protocol.

Também estão disponíveis:

```bash
novel-reader-cli --doctor
novel-reader-cli --self-test
```

### Ubuntu / Debian — instalação manual para desenvolvimento

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip libxcb-cursor0
```

Opcional para capas:

```bash
sudo apt install chafa
```

Clone o projeto:

```bash
git clone https://github.com/gabrielwaltrich/linuxLNreader.git
cd linuxLNreader
```

Crie o ambiente:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale:

```bash
python -m pip install -e ".[dev]"
```

### Fedora

Dependências de sistema típicas:

```bash
sudo dnf install python3 python3-pip xcb-util-cursor
```

Chafa:

```bash
sudo dnf install chafa
```

### Arch Linux

```bash
sudo pacman -S python python-pip xcb-util-cursor
```

Chafa:

```bash
sudo pacman -S chafa
```

## Uso

### Interface gráfica

```bash
novel-reader
```

Ou pelo código-fonte:

```bash
python main.py
```

### Terminal

```bash
novel-reader-cli
```

Ou:

```bash
python cli.py
```

Abrir uma obra diretamente:

```bash
novel-reader-cli "https://www.webnovel.com/book/..."
```

## Tela inicial da TUI

A Home oferece:

```text
Abrir por link
Explorar Fan-Fic Ranking
Minha Library
Busca unificada
Offline e Cache
Continuar última leitura
Sair
```

## Atalhos principais

### Índice do livro

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

### Power Ranking

| Tecla | Ação |
|---|---|
| `↑` / `↓` | selecionar |
| `←` / `→` | mudar período |
| `Enter` | abrir |
| `L` | Library |
| `F` | favorito |
| `/` | buscar |
| `Esc` | voltar |

### Library

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

## Configuração

Arquivo principal:

```text
~/.config/novel-reader/config.json
```

Visualizar:

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

## Cache

Ver status:

```bash
novel-reader-cli --cache-status
```

Limpar:

```bash
novel-reader-cli --cache-clear chapters
novel-reader-cli --cache-clear covers
novel-reader-cli --cache-clear all
```

O limite padrão é de aproximadamente:

```text
500 MB
```

Os arquivos mais antigos são removidos primeiro quando o limite é ultrapassado.

## Backup e segurança dos dados

Backup manual:

```bash
novel-reader-cli --backup-now
```

Listar:

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

Por padrão são mantidos os **5 backups mais recentes**.

O Reader usa também um lock de instância para evitar que dois processos
escrevam simultaneamente na mesma Library.

## Diagnóstico

### Doctor

```bash
novel-reader-cli --doctor
```

### Setup assistido

```bash
novel-reader-cli --setup
```

O setup apenas sugere comandos. Ele não executa `sudo` ou instala pacotes
silenciosamente.

### Self-test

```bash
novel-reader-cli --self-test
```

### Relatório de compatibilidade

```bash
novel-reader-cli --compat-report
```

Salvar JSON:

```bash
novel-reader-cli --compat-report compat.json
```

### Debug

```bash
novel-reader-cli --debug
```

Logs:

```text
~/.local/state/novel-reader/novel-reader.log
```

## Dados locais

O Novel Reader mantém localmente:
- banco SQLite;
- cache;
- capas;
- configuração;
- histórico de busca;
- backups;
- logs;
- perfil persistente do QtWebEngine.

A desinstalação do aplicativo não deve apagar automaticamente esses dados.

## Desenvolvimento

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

## Estrutura resumida

```text
novel_reader/
├── browser/          QtWebEngine e sessão persistente
├── database/         Library SQLite
├── services/         cache, backup, busca, diagnóstico
├── sources/          adapters de fontes
├── ui/               interface gráfica
├── terminal_tui.py   leitor TUI
├── startup_tui.py    Home/Ranking/Library
├── cli.py            CLI
└── models.py         modelos principais

scripts/
├── build-deb.sh
├── install-check.sh
├── smoke-test.sh
└── terminal-checklist.sh
```

## Compatibilidade

O projeto é desenvolvido para Linux.

A matriz de testes está em:

```text
COMPATIBILITY.md
```

Problemas conhecidos:

```text
KNOWN-ISSUES.md
```

Alguns comportamentos — especialmente Kitty Graphics e restauração do modo do
terminal — precisam ser validados em terminais reais.

## Contribuindo

Veja:

```text
CONTRIBUTING.md
```

## Licença

MIT. Veja `LICENSE`.

## Repositório

https://github.com/gabrielwaltrich/linuxLNreader

---

Se você encontrou um problema, inclua quando possível:

```bash
novel-reader-cli --doctor
novel-reader-cli --self-test
novel-reader-cli --compat-report compat.json
```

Isso facilita bastante reproduzir problemas de distro, terminal e dependências.
