import hashlib
import html
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

from bs4 import BeautifulSoup

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".html",
    ".htm",
}
SUPPORTED_BINARY_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".pdf"}
SUPPORTED_UPLOAD_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_BINARY_EXTENSIONS
SUPPORTED_TEXT_MIME_PREFIXES = ("text/",)
SUPPORTED_TEXT_MIME_TYPES = {
    "application/json",
    "application/csv",
    "application/xml",
}
SUPPORTED_BINARY_MIME_TYPES = {
    "application/pdf",
}


def clean_text(text: str) -> str:
    value = html.unescape(text or "")
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def best_effort_decode(raw: bytes) -> str:
    if not raw:
        return ""

    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unsupported text encoding")


def is_supported_upload(filename: str, content_type: str = "") -> bool:
    lowered_name = (filename or "").lower()
    lowered_type = (content_type or "").lower()
    return (
        lowered_name.endswith(tuple(SUPPORTED_UPLOAD_EXTENSIONS))
        or is_text_content_type(lowered_type)
        or lowered_type in SUPPORTED_BINARY_MIME_TYPES
    )


def is_text_content_type(content_type: str) -> bool:
    lowered_type = (content_type or "").lower()
    return lowered_type.startswith(SUPPORTED_TEXT_MIME_PREFIXES) or lowered_type in (
        SUPPORTED_TEXT_MIME_TYPES
    )


def looks_like_text(text: str) -> bool:
    if not text.strip():
        return False
    control_chars = sum(
        1 for char in text if ord(char) < 32 and char not in {"\n", "\r", "\t"}
    )
    replacement_chars = text.count("\ufffd")
    suspicious = control_chars + replacement_chars
    return suspicious / max(len(text), 1) <= 0.02


def extract_docx(raw: bytes) -> str:
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        fragments: list[str] = []
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                xml_text = archive.read(name).decode("utf-8", errors="ignore")
                fragments.extend(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml_text))
        return clean_text(" ".join(fragments))


def extract_pptx(raw: bytes) -> str:
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        fragments: list[str] = []
        slide_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for name in slide_names:
            xml_text = archive.read(name).decode("utf-8", errors="ignore")
            fragments.extend(re.findall(r"<a:t>(.*?)</a:t>", xml_text))
        return clean_text(" ".join(fragments))


def extract_xlsx(raw: bytes) -> str:
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        rows: list[str] = []
        shared_strings = _extract_xlsx_shared_strings(archive)

        worksheet_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("xl/worksheets/") and name.endswith(".xml")
        )
        for name in worksheet_names:
            worksheet_xml = archive.read(name).decode("utf-8", errors="ignore")
            rows.extend(_extract_xlsx_rows(worksheet_xml, shared_strings))

        return clean_text("\n".join(rows))


def _extract_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    shared_xml = archive.read("xl/sharedStrings.xml").decode("utf-8", errors="ignore")
    root = ET.fromstring(shared_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall(".//x:si", namespace):
        fragments = [node.text or "" for node in item.findall(".//x:t", namespace)]
        strings.append(clean_text("".join(fragments)))
    return strings


def _extract_xlsx_rows(worksheet_xml: str, shared_strings: list[str]) -> list[str]:
    root = ET.fromstring(worksheet_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[str] = []
    for row in root.findall(".//x:sheetData/x:row", namespace):
        values: list[str] = []
        for cell in row.findall("x:c", namespace):
            value = _extract_xlsx_cell_value(cell, shared_strings, namespace)
            if value:
                values.append(value)
        if values:
            rows.append(" | ".join(values))
    return rows


def _extract_xlsx_cell_value(
    cell: ET.Element,
    shared_strings: list[str],
    namespace: dict[str, str],
) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "s":
        value_node = cell.find("x:v", namespace)
        if value_node is None or value_node.text is None:
            return ""
        try:
            shared_index = int(value_node.text)
        except ValueError:
            return ""
        if 0 <= shared_index < len(shared_strings):
            return shared_strings[shared_index]
        return ""

    if cell_type == "inlineStr":
        fragments = [node.text or "" for node in cell.findall(".//x:t", namespace)]
        return clean_text("".join(fragments))

    value_node = cell.find("x:v", namespace)
    return clean_text(value_node.text or "") if value_node is not None else ""


def extract_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF parsing requires pypdf to be installed") from exc

    reader = PdfReader(BytesIO(raw))
    fragments = [page.extract_text() or "" for page in reader.pages]
    return clean_text("\n".join(fragments))


def extract_html(raw: bytes) -> str:
    soup = BeautifulSoup(best_effort_decode(raw), "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    parts = [
        node.get_text(" ", strip=True)
        for node in soup.find_all(["h1", "h2", "h3", "p", "li"])
    ]
    return clean_text("\n".join([part for part in [title, *parts] if part]))


def extract_text_from_bytes(filename: str, raw: bytes, content_type: str = "") -> str:
    lowered_name = (filename or "").lower()
    lowered_type = (content_type or "").lower()

    if lowered_name.endswith(".docx"):
        return extract_docx(raw)
    if lowered_name.endswith(".pptx"):
        return extract_pptx(raw)
    if lowered_name.endswith(".xlsx"):
        return extract_xlsx(raw)
    if lowered_name.endswith(".pdf") or "application/pdf" in lowered_type:
        return extract_pdf(raw)
    if lowered_name.endswith((".html", ".htm")) or "text/html" in lowered_type:
        return extract_html(raw)

    text = best_effort_decode(raw)
    if not looks_like_text(text):
        raise ValueError("uploaded file does not look like text")
    if "<html" in text.lower():
        return extract_html(raw)
    return clean_text(text)

