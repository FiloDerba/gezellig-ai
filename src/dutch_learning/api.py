"""Thin HTTP client for the Django vocabulary API.

The Streamlit app talks only to this module; it holds no scheduling logic and no
database access of its own.
"""

import os
from datetime import date
from typing import Any

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api"
TIMEOUT = 15


class ApiError(RuntimeError):
    """Raised when the backend is unreachable or answers with an error status."""


def base_url() -> str:
    return os.environ.get("VOCAB_API_URL", DEFAULT_BASE_URL).rstrip("/")


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{base_url()}{path}"
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {url}. Is the Django server running?") from exc
    if not response.ok:
        raise ApiError(f"{method} {path} failed ({response.status_code}): {response.text[:200]}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


# --- reads -------------------------------------------------------------------


def overview() -> dict:
    return _request("GET", "/stats/overview/")


def activity(days: int = 21) -> list[dict]:
    return _request("GET", "/stats/activity/", params={"days": days})


def forecast(days: int = 14) -> list[dict]:
    return _request("GET", "/stats/forecast/", params={"days": days})


def chapters() -> list[dict]:
    return _request("GET", "/stats/chapters/")


def study_queue(limit: int) -> dict:
    return _request("GET", "/study/queue/", params={"limit": limit})


def words(
    chapter: str | None = None,
    search: str | None = None,
    maturity: str | None = None,
    page_size: int = 500,
) -> list[dict]:
    """All matching words, following pagination until the API runs out of pages."""
    params: dict[str, Any] = {"page_size": page_size}
    if chapter:
        params["chapter"] = chapter
    if search:
        params["search"] = search
    if maturity:
        params["maturity"] = maturity

    payload = _request("GET", "/words/", params=params)
    results = list(payload["results"])
    while payload.get("next"):
        payload = _request("GET", payload["next"].split("/api", 1)[1])
        results.extend(payload["results"])
    return results


# --- writes ------------------------------------------------------------------


def submit_review(word_id: int, quality: int) -> dict:
    return _request("POST", f"/study/{word_id}/review/", json={"quality": quality})


def add_word(dutch: str, english: str, word_type: str = "", chapter: str = "Custom") -> dict:
    return _request(
        "POST",
        "/words/",
        json={"dutch": dutch, "english": english, "word_type": word_type, "chapter": chapter},
    )


def delete_word(word_id: int) -> None:
    _request("DELETE", f"/words/{word_id}/")


def load_sample_deck() -> int:
    return _request("POST", "/words/load-sample/")["added"]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)
