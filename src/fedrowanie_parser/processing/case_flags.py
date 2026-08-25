"""Detect procedural signals in recipient-side correspondence."""
from __future__ import annotations

import re

from ..models import CaseFlags

__all__ = [
    "classify_case_flags",
]


def classify_case_flags(
    document: str,
    *,
    has_unprocessed_attachment: bool = False,
) -> CaseFlags:
    """Classify independent procedural signals present in recipient correspondence."""
    text = document or ""

    return CaseFlags(
        requested_more_time=_matches_more_time(text),
        asked_about_anonymization=_matches_anonymization_question(text),
        requested_clarification=_matches_clarification_request(text),
        requested_processed_info_justification=_matches_processed_information_request(text),
        fee_notice=_matches_fee_notice(text),
        transferred_or_not_competent=_matches_transfer_or_noncompetence(text),
        formal_deficiency_request=_matches_formal_deficiency(text),
        refusal_detected=False,
        unprocessed_attachment=has_unprocessed_attachment,
    )


def _matches_more_time(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                przedłuż\w*\s+(?:termin|czas)
                |przedluz\w*\s+(?:termin|czas)
                |termin.{0,100}(?:wydłuż\w*|wydluz\w*|przedłuż\w*|przedluz\w*)
                |(?:udziel|przekaz|odpowied).{0,100}(?:w\s+terminie|do\s+dnia).{0,80}
                    (?:późniejsz|pozniejsz|30\s+dni|2\s+miesi|dwóch\s+miesi|dwoch\s+miesi)
                |(?:nie\s+jest\s+możliw|nie\s+jest\s+mozliw).{0,100}
                    (?:14\s*dni|ustawow\w*\s+termin)
            )
            """,
            text,
            re.X,
        )
    )


def _matches_anonymization_question(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                (?:prosimy|proszę|prosze|wnosimy).{0,180}
                    (?:potwierd|wskaz|wyjaś|wyjas).{0,180}
                    (?:anonimiz|zanonimiz|bez\s+imion|bez\s+danych\s+osobowych)
                |(?:czy|czy\s+możemy|czy\s+mozemy).{0,160}
                    (?:anonimiz|zanonimiz|bez\s+imion|bez\s+danych\s+osobowych)
                |(?:wyraż|wyraz).{0,120}zgod.{0,120}
                    (?:anonimiz|zanonimiz)
            )
            """,
            text,
            re.X,
        )
    )


def _matches_clarification_request(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                pros\w*.{0,100}(?:doprecyz|sprecyz|wyjaśn|wyjasn|wskazanie)
                |(?:wniosek|żądanie|zadanie).{0,120}
                    (?:wymaga|prosimy\s+o).{0,120}
                    (?:doprecyz|sprecyz|wyjaśn|wyjasn)
                |(?:jakich|których|ktorych).{0,100}(?:danych|informacj\w*).{0,80}
                    (?:dotyczy|oczekuj)
            )
            """,
            text,
            re.X,
        )
    )


def _matches_processed_information_request(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            informacj\w*\s+przetworzon\w*
            .{0,500}
            (?:
                szczególn\w*\s+interes\w*\s+publiczn\w*
                |szczegoln\w*\s+interes\w*\s+publiczn\w*
                |wykaz\w*.{0,100}(?:interes|istotnoś|istotnos)
                |uzasadn\w*
            )
            """,
            text,
            re.X,
        )
    )


def _matches_fee_notice(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                opłat\w*.{0,220}(?:udostępn|udostepn|informacj|koszt)
                |koszt\w*.{0,220}(?:przygotowan|udostępn|udostepn|przekształc|przeksztalc)
                |art\.?\s*15.{0,220}(?:ustaw|dostęp|dostep).{0,220}(?:opłat|koszt)
            )
            """,
            text,
            re.X,
        )
    )


def _matches_transfer_or_noncompetence(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                (?:przekaz\w*|przesł\w*|przesl\w*).{0,180}
                    (?:wniosek|spraw\w*).{0,180}
                    (?:właściw|wlasciw|kompetent)
                |(?:nie\s+jest\w*|nie\s+jesteśmy|nie\s+jestesmy).{0,100}
                    (?:właściw|wlasciw|kompetent|podmiotem\s+zobowiązanym|podmiotem\s+zobowiazanym)
                |(?:prosimy|należy|nalezy).{0,140}
                    (?:zwrócić|zwrocic|skierować|skierowac).{0,140}
                    (?:wniosek|zapytanie).{0,140}(?:do|podmiotu)
            )
            """,
            text,
            re.X,
        )
    )


def _matches_formal_deficiency(text: str) -> bool:
    return bool(
        re.search(
            r"""(?is)
            (?:
                brak\w*\s+formaln\w*
                |uzupełni\w*.{0,120}(?:wniosek|brak\w*|podpis|pełnomocnict|pelnomocnict)
                |uzupelni\w*.{0,120}(?:wniosek|brak\w*|podpis|pełnomocnict|pelnomocnict)
                |wezwan\w*.{0,120}(?:uzupełn|uzupeln|podpis|pełnomocnict|pelnomocnict)
            )
            """,
            text,
            re.X,
        )
    )
