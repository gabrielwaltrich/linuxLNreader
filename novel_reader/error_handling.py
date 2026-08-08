from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import traceback

from novel_reader.logging_setup import current_log_file, get_logger


@dataclass(slots=True)
class FriendlyError:
    title: str
    happened: str
    try_next: list[str]
    log_file: Path


def classify_exception(exc: BaseException) -> FriendlyError:
    message = str(exc).strip()
    name = type(exc).__name__
    lower = message.casefold()

    title = "O Novel Reader encontrou um problema"
    happened = f"{name}: {message or 'erro sem mensagem'}"
    tips = [
        "Tente repetir a operação.",
        "Execute `novel-reader-cli --doctor` para verificar o ambiente.",
    ]

    if "timeout" in lower or "não respondeu" in lower:
        title = "A página demorou demais para responder"
        tips = [
            "Confira sua conexão com a internet.",
            "Tente novamente em alguns segundos.",
            "Se for WebNovel, teste abrir a página normalmente no navegador.",
        ]
    elif "qt" in lower and ("platform" in lower or "xcb" in lower):
        title = "O Qt não conseguiu iniciar corretamente"
        tips = [
            "Execute `novel-reader-cli --doctor`.",
            "Em Ubuntu/Debian, verifique `libxcb-cursor0`.",
            "Execute o programa como seu usuário gráfico normal, não como root.",
        ]
    elif "pyside6" in lower or "no module named 'pyside6'" in lower:
        title = "PySide6 não está instalado"
        tips = [
            "Ative o ambiente virtual do projeto.",
            "Execute `python -m pip install .` novamente.",
        ]
    elif "pil" in lower or "pillow" in lower:
        title = "Pillow não está instalado"
        tips = [
            "Execute `python -m pip install Pillow`.",
            "Ou reinstale o projeto com `python -m pip install .`.",
        ]
    elif "outra instância" in lower or "database is locked" in lower:
        title = "A Library já está em uso"
        tips = [
            "Feche outras instâncias do Novel Reader.",
            "Espere alguns segundos e tente novamente.",
        ]
    elif "permission denied" in lower:
        title = "Permissão negada"
        tips = [
            "Confira se o usuário atual pode gravar no diretório indicado.",
            "Evite executar o Reader como root para corrigir permissões.",
        ]
    elif "segmentation fault" in lower or "sigsegv" in lower:
        title = "Um componente nativo encerrou inesperadamente"
        tips = [
            "Execute `novel-reader-cli --doctor`.",
            "Teste novamente com `--debug` e envie o arquivo de log.",
        ]

    return FriendlyError(
        title=title,
        happened=happened,
        try_next=tips,
        log_file=current_log_file(),
    )


def log_exception(exc: BaseException, *, context: str = "") -> FriendlyError:
    logger = get_logger("errors")
    logger.exception(
        "Exceção não tratada%s",
        f" | contexto={context}" if context else "",
        exc_info=exc,
    )
    return classify_exception(exc)


def format_friendly_error(error: FriendlyError, *, ansi: bool = True) -> str:
    red = "\033[31m" if ansi else ""
    yellow = "\033[33m" if ansi else ""
    bold = "\033[1m" if ansi else ""
    reset = "\033[0m" if ansi else ""

    lines = [
        f"{red}{bold}{error.title}{reset}",
        "",
        f"{bold}O que aconteceu{reset}",
        error.happened,
        "",
        f"{bold}O que tentar{reset}",
    ]
    lines.extend(f"- {tip}" for tip in error.try_next)
    lines += [
        "",
        f"{yellow}Log salvo em:{reset}",
        str(error.log_file),
    ]
    return "\n".join(lines)


def write_crash_report(exc: BaseException, *, context: str = "") -> Path:
    path = current_log_file().with_name("last-crash.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = [
        "Novel Reader crash report",
        f"Contexto: {context or 'não informado'}",
        f"Erro: {type(exc).__name__}: {exc}",
        "",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    path.write_text("\n".join(text), encoding="utf-8")
    return path
