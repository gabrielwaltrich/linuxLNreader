# Novel Reader — v0.5

Leitor minimalista de novels para Linux, com interface PySide6/Qt e Source Engine
compartilhado entre GUI e CLI.

## Destaques da v0.5

A biblioteca agora é organizada por **livros**, e não apenas por uma lista plana
de capítulos.

Cada livro mostra:

- título;
- último capítulo aberto;
- progresso do último capítulo;
- quantidade de capítulos conhecidos;
- favorito do livro;
- capítulos já acessados, expansíveis abaixo do livro.

Também foi adicionada busca por livro/capítulo.

## Migração automática da v0.4 / v0.4.1

O arquivo `library.sqlite3` antigo é preservado.

Na primeira execução da v0.5:

1. a tabela `books` é criada;
2. a coluna `book_id` é adicionada ao histórico existente;
3. capítulos antigos são agrupados automaticamente;
4. progresso e histórico permanecem disponíveis.

Não é necessário apagar o banco antigo.

## O que continua funcionando

- WebNovel via QtWebEngine/Browser Source;
- fallback HTTP para fontes simples;
- leitura de TXT local;
- tema claro/escuro;
- tamanho de fonte;
- tela cheia;
- progresso automático;
- Continuar última leitura;
- capítulo anterior/próximo;
- CLI;
- exportação de capítulo pelo CLI.

## Instalação

Em Ubuntu/Debian, caso o Qt reclame do plugin `xcb`, instale as dependências
gráficas necessárias no sistema (por exemplo `libxcb-cursor0`) e execute o
programa como seu usuário normal, não como root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python main.py
```

Após instalar, também é possível:

```bash
novel-reader
```

## CLI

```bash
novel-reader-cli "https://www.webnovel.com/book/..."
```

Salvar:

```bash
novel-reader-cli "https://www.webnovel.com/book/..." -o capitulo.txt
```

## Atalhos

| Atalho | Ação |
|---|---|
| `Ctrl+B` | Mostrar/ocultar biblioteca |
| `Ctrl+R` | Continuar última leitura |
| `Ctrl+D` | Favoritar/desfavoritar livro atual |
| `Ctrl+O` | Abrir TXT |
| `Alt+←` | Capítulo anterior |
| `Alt+→` | Próximo capítulo |
| `+` / `=` | Aumentar fonte |
| `-` | Diminuir fonte |
| `T` | Tema |
| `F` | Tela cheia |
| `Esc` | Sair da tela cheia |

## Banco da v0.5

```text
books
├── id
├── book_key
├── source
├── title
├── favorite
└── last_opened

reading_history
├── url
├── book_id  ───────→ books.id
├── source
├── book_title
├── chapter_title
├── progress
├── favorite (compatibilidade v0.4)
└── last_opened
```

O `book_key` tenta usar um identificador estável da fonte. Para WebNovel, o
identificador do livro presente na URL é usado para evitar duplicatas mesmo se
o título mudar.

## Escopo

O Reader não contorna paywall, CAPTCHA, login ou controle de acesso. Ele apenas
processa conteúdo que a sessão/página disponibiliza normalmente.
