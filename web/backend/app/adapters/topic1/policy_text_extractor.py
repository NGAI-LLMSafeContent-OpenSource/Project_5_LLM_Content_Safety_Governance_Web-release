import re


def extract_mining_texts(input_texts: list[str]) -> list[str]:
    cleaned = []
    for text in input_texts:
        if not text:
            continue
        no_html = re.sub(r"<[^>]+>", " ", text)
        normalized = re.sub(r"\s+", " ", no_html).strip()
        if normalized:
            cleaned.append(normalized)
    return cleaned
