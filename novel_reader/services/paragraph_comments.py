from __future__ import annotations

from dataclasses import dataclass, field
import re

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ParagraphCommentsProbe:
    ui_present: bool
    login_required: bool
    visible_comment_candidates: int
    paragraph_count_markers: int
    notes: list[str] = field(default_factory=list)


class ParagraphCommentsInspector:
    """Diagnóstico conservador do DOM.

    Não usa endpoints privados e não tenta contornar login. Serve para responder:
    a página renderizada contém a UI/comentários visíveis no DOM atual?
    """

    def inspect(self, html: str) -> ParagraphCommentsProbe:
        soup = BeautifulSoup(html or "", "html.parser")
        page_text = soup.get_text(" ", strip=True)
        folded = page_text.casefold()

        ui_present = "paragraph comments" in folded
        login_required = ui_present and bool(
            re.search(r"paragraph comments.{0,300}\blogin\b", folded, re.I)
            or re.search(r"\blogin\b.{0,300}paragraph comments", folded, re.I)
        )

        # Counts shown beside paragraphs are often rendered in small badges/buttons.
        marker_count = 0
        for node in soup.find_all(["button", "span", "sup", "i"]):
            attrs = " ".join([
                " ".join(node.get("class", [])),
                str(node.get("aria-label") or ""),
                str(node.get("title") or ""),
                str(node.get("data-testid") or ""),
            ]).casefold()
            text = node.get_text(" ", strip=True)
            if ("comment" in attrs or "paragraph" in attrs) and re.fullmatch(r"\d+", text or ""):
                marker_count += 1

        # We only call something a visible candidate if the element itself looks
        # comment-specific and contains meaningful prose.
        candidates = 0
        for node in soup.find_all(True):
            attrs = " ".join([
                " ".join(node.get("class", [])),
                str(node.get("data-testid") or ""),
                str(node.get("id") or ""),
            ]).casefold()
            if "comment" not in attrs:
                continue
            text = node.get_text(" ", strip=True)
            if len(text) >= 20 and "what's your thought" not in text.casefold():
                candidates += 1

        notes: list[str] = []
        if ui_present:
            notes.append("A UI de comentários por parágrafo foi detectada.")
        else:
            notes.append("A UI de comentários por parágrafo não apareceu no DOM atual.")
        if login_required:
            notes.append("O DOM indica que login pode ser necessário para visualizar/interagir.")
        if candidates == 0:
            notes.append(
                "Nenhum corpo de comentário confiável foi encontrado no DOM; "
                "os comentários podem ser carregados apenas após interação/requisição dinâmica."
            )

        return ParagraphCommentsProbe(
            ui_present=ui_present,
            login_required=login_required,
            visible_comment_candidates=candidates,
            paragraph_count_markers=marker_count,
            notes=notes,
        )
