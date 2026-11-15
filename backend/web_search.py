"""Google Search grounded web lookup: match returned game names to our data, keep summary + suggestions.

Gemini API Additional Terms (grounding): grounded results and search suggestions may only be used
to serve the one response they were produced for. They must not be cached, stored, logged,
analyzed, or used for evaluation or training. This module therefore keeps nothing after returning.
"""

import os
import re

try:
    from backend import gemini, limits, recommend_engine as eng
    from backend.series import _norm
except ImportError:
    import gemini
    import limits
    import recommend_engine as eng
    from series import _norm

MIN_REVIEWS = 1000
web_budget = limits.DailyBudget(int(os.environ.get("WEB_SEARCH_DAILY_LIMIT", "100")))
_LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_names: dict[str, set[int]] | None = None  # name index built from our own data, not from web results


def _name_index() -> dict[str, set[int]]:
    global _names
    if _names is None:
        index: dict[str, set[int]] = {}
        pool = eng.df[eng.df["NumUserRatings"] >= MIN_REVIEWS]
        for bgg_id, name in zip(pool["BGGId"].tolist(), pool["Name"].tolist()):
            for form in {_norm(name), _norm(str(name).split(":", 1)[0])}:
                if form:
                    index.setdefault(form, set()).add(int(bgg_id))
        _names = index
    return _names


def _lines(text: str) -> list[str]:
    return [_LIST_MARK.sub("", line).strip() for line in text.splitlines() if line.strip()]


def match_names(text: str) -> frozenset[int]:
    index = _name_index()
    ids: set[int] = set()
    for line in _lines(text):
        ids |= index.get(_norm(line), set())
    return frozenset(ids)


def _summary(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if len(blocks) >= 2:
        return " ".join(blocks[1:])
    lines = _lines(text)
    return lines[-1] if lines and len(lines[-1].split()) > 8 else ""


def lookup(query: str) -> tuple[frozenset[int], dict] | None:
    client = gemini.get_client()
    if client is None or web_budget.remaining() < 1:
        return None
    try:
        gemini.charge()  # a web call is also a Gemini generate call: charge the general budget once
        answer = client.web_search(query)
    except gemini.GeminiError:
        return None
    web_budget.try_spend(min(max(1, answer.search_count), web_budget.remaining()))
    # The terms require showing search suggestions with grounded results: no HTML means failure.
    if not answer.suggestions_html:
        return None
    return match_names(answer.text), {
        "summary": _summary(answer.text),
        "suggestions_html": answer.suggestions_html,
    }
