"""
Утилиты для поиска и загрузки портретов игроков.

Порядок источников:
1. Sports.ru
2. Wikipedia (MediaWiki API)

Если фото не найдено, вызывающий код должен использовать локальный плейсхолдер.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from functools import lru_cache
from urllib.parse import quote, urlencode

_REQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9",
}

_IMG_GET_HEADERS = {
    "User-Agent": _REQ_HEADERS["User-Agent"],
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

_SPORTS_HEADERS = {
    **_REQ_HEADERS,
    "Referer": "https://www.sports.ru/",
}

_WIKIPEDIA_HEADERS = {
    **_REQ_HEADERS,
    "Accept": "application/json",
}

_WIKIDATA_HEADERS = {
    "User-Agent": _REQ_HEADERS["User-Agent"],
    "Accept": "application/json",
}

_RU_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _normalize_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _latin_slug(value: str) -> str:
    value = value.lower().replace("'", "").replace("’", "")
    out = []
    for ch in value:
        if ch in _RU_TO_LAT:
            out.append(_RU_TO_LAT[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out)
    return re.sub(r"-+", "-", slug).strip("-")


def _name_to_slug_forms(name: str) -> list[str]:
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if not words:
        return []
    words = [_normalize_ascii(w) for w in words]
    latin_words = [_latin_slug(w) for w in words]
    full = "-".join([w for w in latin_words if w])
    first = latin_words[0] if latin_words else ""
    last = latin_words[-1] if latin_words else ""

    candidates: list[str] = []
    for candidate in [
        full,
        last,
        f"{first}-{last}" if first and last else "",
        f"{last}-{first}" if first and last else "",
    ]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _read_text(url: str, headers: dict[str, str]) -> str | None:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _read_json(url: str, headers: dict[str, str]) -> dict | None:
    raw = _read_text(url, headers)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@lru_cache(maxsize=512)
def _wikidata_english_name_candidates(player_name_ru: str) -> list[str]:
    """
    Возвращает английские label/aliases из Wikidata.
    Это помогает и со Sports.ru slug, и с поиском в Wikipedia.
    """
    candidates: list[str] = []
    search_url = (
        "https://www.wikidata.org/w/api.php"
        f"?action=wbsearchentities&format=json&language=ru&type=item&limit=5&search={quote(player_name_ru)}"
    )
    data = _read_json(search_url, _WIKIDATA_HEADERS)
    if not data:
        return candidates

    for item in data.get("search", [])[:3]:
        qid = item.get("id")
        if not qid:
            continue
        entity_url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbgetentities&format=json&ids={quote(qid)}&props=labels|aliases&languages=en"
        )
        entity_data = _read_json(entity_url, _WIKIDATA_HEADERS)
        if not entity_data:
            continue
        entity = entity_data.get("entities", {}).get(qid, {})
        en_label = entity.get("labels", {}).get("en", {}).get("value")
        if en_label and en_label not in candidates:
            candidates.append(en_label)
        for alias in entity.get("aliases", {}).get("en", [])[:5]:
            value = alias.get("value")
            if value and value not in candidates:
                candidates.append(value)
    return candidates


def _sports_candidate_slugs(player_name: str) -> list[str]:
    candidates: list[str] = []
    for en_name in _wikidata_english_name_candidates(player_name):
        for slug in _name_to_slug_forms(en_name):
            if slug not in candidates:
                candidates.append(slug)
    for slug in _name_to_slug_forms(player_name):
        if slug not in candidates:
            candidates.append(slug)
    return candidates


def fetch_sportsru_portrait_url(player_name: str) -> str | None:
    """Ищет фото игрока на Sports.ru по slug-кандидатам."""
    for slug in _sports_candidate_slugs(player_name):
        profile_url = f"https://www.sports.ru/football/person/{quote(slug)}/"
        html = _read_text(profile_url, _SPORTS_HEADERS)
        if not html:
            continue
        if "/football/person/" not in html and "tc_person" not in html:
            continue

        match = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if not match:
            continue

        img_url = match.group(1).strip()
        if not img_url.startswith("http"):
            continue
        if "tc_person" not in img_url and "photobooth.cdn.sports.ru" not in img_url:
            continue
        return img_url
    return None


def _wikipedia_search_titles(query: str, *, language: str, hint: str) -> list[str]:
    if not query.strip():
        return []
    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": f'intitle:"{query}" {hint}',
            "srlimit": "5",
            "srprop": "",
            "utf8": "1",
        }
    )
    url = f"https://{language}.wikipedia.org/w/api.php?{params}"
    data = _read_json(url, _WIKIPEDIA_HEADERS)
    if not data:
        return []
    titles: list[str] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title")
        if title and title not in titles:
            titles.append(title)
    return titles


def _wikipedia_page_image(title: str, *, language: str) -> str | None:
    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "original",
            "titles": title,
            "redirects": "1",
            "utf8": "1",
        }
    )
    url = f"https://{language}.wikipedia.org/w/api.php?{params}"
    data = _read_json(url, _WIKIPEDIA_HEADERS)
    if not data:
        return None
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        image_url = page.get("original", {}).get("source")
        if image_url and _is_probable_portrait_url(image_url):
            return image_url
    return None


def _is_probable_portrait_url(url: str) -> bool:
    lower = url.lower()
    if any(token in lower for token in ("wikipedia-wordmark", "wikimedia-button", "system-search")):
        return False
    return any(ext in lower for ext in (".jpg", ".jpeg", ".png", ".webp"))


def fetch_wikipedia_portrait_url(player_name: str) -> str | None:
    """
    Ищет главное изображение статьи футболиста в Wikipedia.
    Сначала ruwiki по исходному имени, затем enwiki по английским вариантам имени.
    """
    for title in _wikipedia_search_titles(player_name, language="ru", hint="футболист"):
        image_url = _wikipedia_page_image(title, language="ru")
        if image_url:
            return image_url

    for query in _wikidata_english_name_candidates(player_name):
        for title in _wikipedia_search_titles(query, language="en", hint="footballer"):
            image_url = _wikipedia_page_image(title, language="en")
            if image_url:
                return image_url

    return None


def download_url_bytes(url: str) -> bytes | None:
    """Скачивает байты изображения по URL."""
    req = urllib.request.Request(url, headers=_IMG_GET_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            return data if data else None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def fetch_sportsru_portrait_bytes(player_name: str) -> bytes | None:
    image_url = fetch_sportsru_portrait_url(player_name)
    if not image_url:
        return None
    return download_url_bytes(image_url)


def fetch_wikipedia_portrait_bytes(player_name: str) -> bytes | None:
    image_url = fetch_wikipedia_portrait_url(player_name)
    if not image_url:
        return None
    return download_url_bytes(image_url)


def fetch_player_portrait_url(player_name: str) -> tuple[str | None, str | None]:
    """
    Возвращает `(url, source)` в порядке Sports.ru -> Wikipedia.
    """
    sports_url = fetch_sportsru_portrait_url(player_name)
    if sports_url:
        return sports_url, "Sports.ru"

    wikipedia_url = fetch_wikipedia_portrait_url(player_name)
    if wikipedia_url:
        return wikipedia_url, "Wikipedia"

    return None, None


def fetch_player_portrait_bytes(player_name: str) -> tuple[bytes | None, str | None]:
    """
    Возвращает `(bytes, source)` в порядке Sports.ru -> Wikipedia.
    """
    sports_data = fetch_sportsru_portrait_bytes(player_name)
    if sports_data:
        return sports_data, "Sports.ru"

    wikipedia_data = fetch_wikipedia_portrait_bytes(player_name)
    if wikipedia_data:
        return wikipedia_data, "Wikipedia"

    return None, None


def fetch_player_portrait_bytes_with_report(player_name: str) -> tuple[bytes | None, str | None, list[dict[str, str]]]:
    """
    Возвращает `(bytes, source, report)`, где `report` описывает попытки по источникам.
    """
    report: list[dict[str, str]] = []

    sports_url = fetch_sportsru_portrait_url(player_name)
    if sports_url:
        sports_data = download_url_bytes(sports_url)
        if sports_data:
            report.append(
                {
                    "source": "Sports.ru",
                    "status": "success",
                    "message": "Найден URL и изображение успешно скачано",
                    "url": sports_url,
                }
            )
            return sports_data, "Sports.ru", report
        report.append(
            {
                "source": "Sports.ru",
                "status": "download_failed",
                "message": "URL найден, но скачать изображение не удалось",
                "url": sports_url,
            }
        )
    else:
        report.append(
            {
                "source": "Sports.ru",
                "status": "not_found",
                "message": "Подходящее фото или профиль игрока не найден",
                "url": "",
            }
        )

    wikipedia_url = fetch_wikipedia_portrait_url(player_name)
    if wikipedia_url:
        wikipedia_data = download_url_bytes(wikipedia_url)
        if wikipedia_data:
            report.append(
                {
                    "source": "Wikipedia",
                    "status": "success",
                    "message": "Найдено главное изображение статьи и успешно скачано",
                    "url": wikipedia_url,
                }
            )
            return wikipedia_data, "Wikipedia", report
        report.append(
            {
                "source": "Wikipedia",
                "status": "download_failed",
                "message": "Изображение статьи найдено, но скачать его не удалось",
                "url": wikipedia_url,
            }
        )
    else:
        report.append(
            {
                "source": "Wikipedia",
                "status": "not_found",
                "message": "Статья с подходящим изображением не найдена",
                "url": "",
            }
        )

    return None, None, report
