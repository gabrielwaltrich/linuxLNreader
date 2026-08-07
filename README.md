# Novel Reader — v0.3.1 Browser Source

A v0.3.1 resolve o principal limite encontrado na v0.2: algumas fontes recusam requisições HTTP simples ou montam o capítulo com JavaScript.

## O que mudou

- `WebNovelSource` agora declara `requires_browser = True`
- páginas WebNovel são abertas com **QtWebEngine/Chromium**
- o navegador executa JavaScript normalmente
- depois do carregamento, o DOM renderizado é capturado com `toHtml()`
- o DOM volta para o mesmo `SourceManager` e para o mesmo parser de `Chapter`
- cookies e cache do navegador são persistentes entre execuções
- páginas simples continuam usando o downloader HTTP leve da v0.2
- nenhum mecanismo de desbloqueio, paywall ou automação de login foi adicionado

## Arquitetura

```text
                         URL
                          │
                          ▼
                    SourceManager
                     │          │
          requires_browser     HTTP simples
                     │          │
                     ▼          ▼
              BrowserSession  SourceWorker
              QtWebEngine       httpx
                     │          │
             DOM renderizado    HTML
                     └────┬─────┘
                          ▼
                     NovelSource
                          │
                          ▼
                       Chapter
                          │
                          ▼
                      ReaderView
```

## Instalação

```bash
cd novel-reader-v0.3.1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python main.py
```

O pacote `PySide6` instala os módulos Qt necessários, incluindo QtWebEngine nas distribuições suportadas.

### Dependências do sistema Linux

QtWebEngine precisa de uma sessão gráfica funcional. Em distribuições Linux muito mínimas, podem faltar bibliotecas do Chromium/Qt. Em Ubuntu/Debian desktop normal, a instalação via `pip` geralmente já fornece os componentes Qt do lado Python.

## Como testar o caso do WebNovel

1. Abra `python main.py`.
2. Cole uma URL pública de capítulo WebNovel.
3. Clique em **Abrir**.
4. A barra inferior deve mostrar etapas como:
   - `Navegador: conectando…`
   - `Navegador: carregando…`
   - `Página carregada; aguardando conteúdo dinâmico…`
   - `Extraindo texto da página renderizada…`
5. Se o parser encontrar o capítulo público, ele será mostrado no Reader.

A primeira abertura pode ser mais lenta porque o Chromium precisa inicializar seu perfil/cache.

## Limites desta versão

O navegador embutido não é mostrado visualmente. Isso significa que páginas que exijam interação humana, CAPTCHA ou login não podem ser concluídas nesta versão. O leitor também não tenta contornar esses mecanismos.

Se o site mostrar um desafio de segurança mesmo dentro do QtWebEngine, a v0.3.1 apresentará erro em vez de tentar disfarçar o cliente ou burlar o desafio.

## Estrutura nova

```text
novel_reader/
├── browser/
│   ├── __init__.py
│   └── session.py
├── services/
│   └── downloader.py
├── sources/
│   ├── base.py
│   ├── generic.py
│   ├── manager.py
│   └── webnovel.py
└── ui/
    ├── main_window.py
    ├── reader_view.py
    └── source_worker.py
```

## Próximo passo sugerido — v0.4

Depois de confirmar que o Browser Source consegue carregar seus capítulos de teste, a próxima versão pode adicionar uma janela de navegador visível opcional para sessões que precisem de interação legítima e, em seguida, a biblioteca SQLite com histórico e retomada de leitura.

## Correções da v0.3.1

- Corrige falso positivo em capítulos gratuitos causado por textos globais como `Batch unlock chapters`.
- Procura o texto real do capítulo antes de classificar uma página como bloqueada.
- Faz capturas progressivas do DOM em 0,5 s, 1 s, 2 s e 4 s após o carregamento.
- Só apresenta diagnóstico de bloqueio depois de esgotar as tentativas de conteúdo dinâmico.
- Mantém a regra de não contornar paywall, login ou controles de acesso.
