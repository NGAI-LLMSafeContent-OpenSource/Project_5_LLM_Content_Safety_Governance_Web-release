"""Topic 2 harm category display labels (EN → ZH)."""

from __future__ import annotations

L1_NAME_ZH: dict[str, str] = {
    "CBRNE": "CBRNE（化生放核爆）",
    "Explicit Harmful Injection": "显式有害注入",
    "Implicit Bias Contamination": "隐性偏见污染",
    "Factual Misleading and Hallucination Contamination": "事实误导与幻觉污染",
}

L1_CODE_ZH: dict[str, str] = {
    "L1-1": "CBRNE（化生放核爆）",
    "L1-2": "显式有害注入",
    "L1-3": "隐性偏见污染",
    "L1-4": "事实误导与幻觉污染",
}


def format_harm_category_l1(raw: str | None) -> str:
    """Format Topic 2 L1 labels for UI, e.g. L1-3 Implicit Bias Contamination → L1-3 隐性偏见污染."""
    text = str(raw or "").strip()
    if not text:
        return ""

    code = ""
    english_part = text
    if text.upper().startswith("L1-"):
        parts = text.split(None, 1)
        code = parts[0].upper().replace("L1-", "L1-")
        # Normalize L1-3 style
        if "-" in parts[0]:
            prefix, num = parts[0].split("-", 1)
            code = f"{prefix.upper()}-{num}"
        english_part = parts[1].strip() if len(parts) > 1 else ""
        english_part = english_part.lstrip(":：-— ").strip()

    zh = L1_NAME_ZH.get(english_part) or L1_CODE_ZH.get(code)
    if code and zh:
        return f"{code} {zh}"
    if zh:
        return zh
    return text
