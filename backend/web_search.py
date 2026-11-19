"""Google Search grounded web lookup: match returned game names to our data, keep summary + suggestions.

Gemini API Additional Terms (grounding): grounded results and search suggestions may only be used
to serve the one response they were produced for. They must not be cached, stored, logged,
analyzed, or used for evaluation or training. This module therefore keeps nothing after returning.
"""

import os
import re
import unicodedata

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
_MARKDOWN_WRAP = re.compile(r"[*_`]+")
_YEAR_SUFFIX = re.compile(r"\s*\(\d{4}\)\s*$")
_DASH_SPLIT = re.compile(r"\s+[-–—]\s+")
_names: dict[str, set[int]] | None = None  # name index built from our own data, not from web results


def _web_norm(s: str) -> str:
    """웹 이름 매칭 전용 정규화: 악센트 제거, 아포스트로피 제거 (Tzolk'in = Tzolkin, Café = Cafe). series 키는 건드리지 않는다"""
    text = unicodedata.normalize("NFKD", str(s))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _norm(re.sub(r"['’‘`]", "", text))


def _name_index() -> dict[str, set[int]]:
    global _names
    if _names is None:
        index: dict[str, set[int]] = {}
        pool = eng.df[eng.df["NumUserRatings"] >= MIN_REVIEWS]
        for bgg_id, name in zip(pool["BGGId"].tolist(), pool["Name"].tolist()):
            for form in {_web_norm(name), _web_norm(str(name).split(":", 1)[0])}:
                if form:
                    index.setdefault(form, set()).add(int(bgg_id))
        _names = index
    return _names


def _lines(text: str) -> list[str]:
    return [_LIST_MARK.sub("", line).strip() for line in text.splitlines() if line.strip()]


def _name_candidates(line: str) -> list[str]:
    """마크다운 강조(**), 연도 표기(1995), 부가 설명(' - ...')을 제거한 매칭 후보 문자열"""
    cleaned = _MARKDOWN_WRAP.sub("", line).strip()
    candidates = [cleaned]
    no_year = _YEAR_SUFFIX.sub("", cleaned).strip()
    if no_year != cleaned:
        candidates.append(no_year)
    head = _DASH_SPLIT.split(cleaned, maxsplit=1)[0].strip()
    if head != cleaned:
        candidates.append(head)
        head_no_year = _YEAR_SUFFIX.sub("", head).strip()
        if head_no_year != head:
            candidates.append(head_no_year)
    return candidates


def match_names(text: str) -> frozenset[int]:
    index = _name_index()
    ids: set[int] = set()
    for line in _lines(text):
        for candidate in _name_candidates(line):
            hits = index.get(_web_norm(candidate))
            if hits:
                ids |= hits
                break
    return frozenset(ids)


def _summary(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if len(blocks) >= 2:
        return " ".join(blocks[1:])
    lines = _lines(text)
    return lines[-1] if lines and len(lines[-1].split()) > 8 else ""


def lookup(query: str) -> tuple[frozenset[int], dict] | None:
    client = gemini.get_client()
    if client is None:
        return None
    try:
        gemini.charge()  # a web call is also a Gemini generate call: charge the general budget once
    except gemini.GeminiError:
        return None
    if not web_budget.try_spend(1):
        return None
    try:
        answer = client.web_search(query)
    except gemini.GeminiError:
        return None
    # 처음 1은 호출 전에 썼다. 나머지는 남은 한도 안에서 쓴다 (넘으면 건너뛰지 않고 남은 만큼만)
    extra = max(0, answer.search_count - 1)
    if extra:
        web_budget.try_spend(min(extra, web_budget.remaining()))
    # The terms require showing search suggestions with grounded results: no HTML means failure.
    if not answer.suggestions_html:
        return None
    return match_names(answer.text), {
        "summary": _summary(answer.text),
        "suggestions_html": answer.suggestions_html,
    }
