# Known issues — pré-1.0

## Kitty graphics protocol

A presença do executável `kitten` não significa que o terminal atual suporte Kitty Graphics Protocol. Em terminais incompatíveis, prefira Chafa ou Pillow.

## WebNovel

A estrutura da página é externa ao projeto e pode mudar sem aviso. Ranking e índice usam captura progressiva para lidar com lazy loading e listas virtualizadas, mas alterações do site podem exigir atualização do adapter.

## Conteúdo protegido

O Reader não tenta contornar paywalls, capítulos pagos, CAPTCHA, login, controles de acesso ou DRM.

## Testes de terminal

Testes automatizados exercitam a lógica da TUI, porém escape sequences e protocolos gráficos precisam ser validados em terminais reais antes da 1.0.
