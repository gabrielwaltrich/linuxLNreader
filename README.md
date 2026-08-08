# Novel Reader

Leitor de novels e webnovels para Linux, com **interface gráfica** e **modo CLI/TUI**.

O objetivo do Novel Reader é transformar páginas de leitura da web em uma experiência mais limpa, organizada e confortável, mantendo biblioteca, progresso, favoritos, categorias, tags e cache local em um único aplicativo.

> **Status:** em preparação para a versão 1.0.

---

## Recursos

### Leitura

- leitor sem distrações;
- capítulos anterior/próximo;
- progresso automático;
- continuar de onde parou;
- temas claro e escuro;
- tamanho da fonte e largura do conteúdo configuráveis;
- leitura de arquivos `.txt`;
- cache local de capítulos já carregados;
- cache antecipado opcional dos próximos capítulos públicos.

### WebNovel

O suporte atual é focado principalmente no **WebNovel**.

O Reader consegue:

- abrir uma URL de livro;
- abrir uma URL de capítulo;
- detectar título, autor, sinopse e capa;
- carregar o índice de capítulos;
- navegar entre capítulos;
- explorar o **Fan-Fic Power Ranking**;
- trocar entre os períodos:
  - Monthly;
  - Season;
  - Bi-annual;
  - Annual;
  - All-time.

O carregamento do ranking é progressivo para lidar com páginas que usam lazy loading ou listas virtualizadas.

### Library

A biblioteca do usuário guarda obras já lidas ou adicionadas manualmente.

Cada livro pode ter:

- progresso;
- favorito;
- categoria;
- tags pessoais;
- nota pessoal de 1 a 5 estrelas;
- marcador de livro fixado;
- histórico recente;
- último capítulo aberto;
- capa;
- índice de capítulos.

Categorias disponíveis:

- **Lendo**;
- **Concluídos**;
- **Planejo ler**;
- **Favoritos**.

Também é possível exportar e importar a Library em JSON.

### CLI / TUI

O modo terminal possui uma interface interativa baseada em `curses`.

```text
NOVEL READER

▶ Abrir por link
  Explorar Fan-Fic Ranking
  Minha Library
  Busca unificada
  Continuar última leitura
  Sair
```

No índice de capítulos é possível navegar usando as setas do teclado, pesquisar capítulos, abrir o Reader, continuar a leitura e gerenciar a Library sem sair do terminal.

### Capas no terminal

O Reader suporta diferentes métodos de renderização:

1. **Kitten icat** — imagem real em terminais compatíveis com Kitty Graphics Protocol;
2. **Chafa** — conversão avançada da capa para caracteres;
3. **Pillow ASCII** — fallback em Python;
4. capa desativada.

O modo padrão é **Auto**.

---

# Instalação

## Requisitos

- Linux;
- Python **3.10 ou superior**;
- `pip`;
- suporte gráfico para Qt caso use a interface GUI.

Dependências Python são instaladas automaticamente pelo `pip`:

- PySide6;
- httpx;
- BeautifulSoup4;
- Pillow.

---

## Ubuntu / Debian

Instale primeiro os pacotes básicos:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Em algumas instalações Linux, o Qt precisa também do pacote:

```bash
sudo apt install libxcb-cursor0
```

Clone ou extraia o projeto e entre na pasta:

```bash
cd novel-reader
```

Crie um ambiente virtual:

```bash
python3 -m venv .venv
```

Ative:

```bash
source .venv/bin/activate
```

Atualize o `pip`:

```bash
python -m pip install --upgrade pip
```

Instale o Novel Reader:

```bash
python -m pip install .
```

Depois disso estarão disponíveis:

```bash
novel-reader
```

e:

```bash
novel-reader-cli
```

---

## Fedora

Pacotes básicos:

```bash
sudo dnf install python3 python3-pip
```

Crie o ambiente e instale:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

---

## Arch Linux

Pacotes básicos:

```bash
sudo pacman -S python python-pip
```

Depois:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

---

# Recursos opcionais do terminal

## Chafa

O Chafa melhora bastante a visualização de capas em terminais comuns.

Ubuntu/Debian:

```bash
sudo apt install chafa
```

Arch:

```bash
sudo pacman -S chafa
```

Fedora:

```bash
sudo dnf install chafa
```

Confirme:

```bash
chafa --version
```

---

## Kitty / kitten icat

Para mostrar a **imagem real da capa** no terminal, use um terminal compatível com o Kitty Graphics Protocol.

No Kitty, o `kitten icat` normalmente já faz parte da instalação.

Ubuntu/Debian:

```bash
sudo apt install kitty
```

Teste:

```bash
kitten icat imagem.jpg
```

Dentro do Novel Reader pressione:

```text
?
```

ou:

```text
F2
```

para abrir o diagnóstico do backend gráfico.

> Instalar `kitten` não faz um terminal incompatível ganhar suporte ao Kitty Graphics Protocol. Se o terminal atual não oferecer esse protocolo, use Chafa ou Pillow ASCII.

---

# Executando

## Interface gráfica

Depois da instalação:

```bash
novel-reader
```

ou diretamente pelo código:

```bash
python main.py
```

---

## CLI/TUI

Para abrir a Home interativa:

```bash
novel-reader-cli
```

ou:

```bash
python cli.py
```

A Home permite:

```text
Abrir por link
Explorar Fan-Fic Ranking
Minha Library
Busca unificada
Continuar última leitura
Sair
```

---

## Abrir um livro diretamente

```bash
novel-reader-cli "https://www.webnovel.com/book/..."
```

Também funciona com:

```bash
python cli.py "https://www.webnovel.com/book/..."
```

---

# Atalhos do CLI

Os atalhos alfabéticos não diferenciam maiúsculas de minúsculas.

## Índice do livro

| Tecla | Ação |
|---|---|
| `↑` / `↓` | selecionar capítulo |
| `J` / `K` | navegar para baixo/cima |
| `Enter` | abrir capítulo |
| `/` | buscar capítulo |
| `I` | escolher modo da capa |
| `?` / `F2` | diagnóstico Kitten icat |
| `L` | adicionar/remover da Library |
| `A` | cachear próximos capítulos públicos |
| `C` | continuar leitura |
| `U` | próximo não lido |
| `R` | atualizar índice |
| `Q` | sair |

## Reader

| Tecla | Ação |
|---|---|
| `→`, `↓`, `Espaço`, `N` | próxima página |
| `←`, `↑`, `P` | página anterior |
| `G` | ir para uma página |
| `Q` / `Esc` | voltar ao índice |

## Power Ranking

| Tecla | Ação |
|---|---|
| `←` / `→` | mudar período |
| `↑` / `↓` | selecionar obra |
| `Enter` | abrir obra |
| `L` | adicionar/remover da Library |
| `/` | pesquisar |
| `?` / `F2` | diagnóstico do backend gráfico |
| `Esc` | voltar |

## Library

| Tecla | Ação |
|---|---|
| `↑` / `↓` | selecionar livro |
| `Enter` | abrir |
| `F` | favoritar |
| `P` | fixar/desafixar |
| `T` | editar tags |
| `N` | nota pessoal |
| `C` | categoria |
| `V` | alternar categorias |
| `O` | alternar ordenação |
| `/` | pesquisar |
| `B` | exportar Library |
| `M` | importar Library |
| `D` | remover da Library |
| `Esc` | voltar |

---

# Backup da Library

Dentro da Library pressione:

```text
B
```

O local sugerido é:

```text
~/novel-reader-library.json
```

Para importar:

```text
M
```

A importação faz **merge** com a biblioteca atual e preserva o maior progresso conhecido de cada capítulo.

---

# Dados locais

O Reader usa SQLite para guardar:

- livros;
- capítulos;
- progresso;
- favoritos;
- categorias;
- tags;
- avaliações pessoais;
- histórico;
- índice de capítulos.

Também utiliza o diretório de cache do usuário para guardar capítulos e capas processadas.

Nenhum servidor próprio é necessário.

---

# Desenvolvimento

Clone o repositório:

```bash
git clone https://github.com/gabrielwaltrich/linuxLNreader.git
cd linuxLNreader
```

Crie o ambiente:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale com dependências de desenvolvimento:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Execute os testes:

```bash
pytest -q
```

A versão atual possui testes automatizados cobrindo parser de fontes, banco de dados, Library, ranking, CLI/TUI, cache, capas e integração do navegador.

---

# Estrutura resumida

```text
novel_reader/
├── browser/             QtWebEngine e sessão de navegador
├── database/            SQLite / Library / histórico
├── services/            cache, mídia, ranking e utilidades
├── sources/             adaptadores das fontes
├── ui/                  interface PySide6
├── cli.py               entrada principal do CLI
├── startup_tui.py       Home, Ranking e Library
├── terminal_tui.py      índice e Reader no terminal
├── terminal_cover.py    Kitten / Chafa / Pillow
└── terminal_config.py   preferências do CLI
```

---

# Limitações e escopo

O Novel Reader **não contorna**:

- paywalls;
- capítulos pagos;
- CAPTCHA;
- autenticação;
- DRM;
- controles de acesso.

Ele apenas lê o conteúdo disponibilizado normalmente pela página ou pela sessão do usuário.

Alguns sites carregam conteúdo de forma dinâmica e podem mudar sua estrutura sem aviso, portanto adaptadores podem precisar ser atualizados ao longo do tempo.

O suporte atual é mais completo para WebNovel. A arquitetura de fontes foi criada para permitir novos adaptadores futuramente.

---

# Projeto

Repositório:

```text
https://github.com/gabrielwaltrich/linuxLNreader
```

Contribuições, relatórios de bugs e sugestões são bem-vindos.

---

## Licença

Antes do lançamento 1.0, adicione ao repositório um arquivo `LICENSE` com a licença escolhida para o projeto.

Se você pretende aceitar contribuições públicas, uma licença permissiva como MIT ou Apache-2.0 costuma simplificar a colaboração.
