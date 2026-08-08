from __future__ import annotations


def evidence_label(confidence: str | None, verified: bool) -> str:
    """Normalize evidence state for API consumers."""

    normalized = (confidence or "").strip().lower()
    if verified and normalized in {"high", "medium"}:
        return "verified"
    if normalized == "high":
        return "verified"
    if normalized == "medium":
        return "supported"
    if normalized == "low":
        return "limited"
    return "unverified"
