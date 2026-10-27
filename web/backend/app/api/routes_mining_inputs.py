from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import get_db
from app.services.document_parser import extract_text_from_bytes, is_supported_upload
from app.services.mining_input_service import (
    get_mining_input,
    save_source_document,
)


router = APIRouter(prefix="/api/mining-inputs", tags=["mining-inputs"])

MAX_UPLOAD_FILES = 30
MAX_DOCUMENT_CONTENT_LENGTH = 20000
MIN_PARSED_CONTENT_LENGTH = 10


def _is_pdf_upload(filename: str, content_type: str) -> bool:
    lowered_name = (filename or "").lower()
    lowered_type = (content_type or "").lower()
    return lowered_name.endswith(".pdf") or "application/pdf" in lowered_type


def _pdf_fallback_content(filename: str, reason: str) -> str:
    return (
        f"PDF 文件 {filename or 'unnamed.pdf'} 已上传，但自动文本提取结果不足。"
        f"可能原因：该 PDF 为扫描版、加密文件或文本层较少。"
        f"解析提示：{reason}。"
        "请结合文档链接、可复制文本版本或补充材料继续进行指标挖掘。"
    )


@router.post("/parse-uploaded-files")
async def parse_uploaded_files(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="please upload at least one file")
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400, detail=f"at most {MAX_UPLOAD_FILES} files are allowed"
        )

    parsed = []
    failures = []
    for upload in files:
        filename = upload.filename or "unknown"
        content_type = upload.content_type or ""
        if not is_supported_upload(upload.filename or "", upload.content_type or ""):
            failures.append(
                {
                    "name": filename,
                    "reason": "unsupported file type",
                }
            )
            continue
        raw = await upload.read()
        try:
            content = extract_text_from_bytes(filename, raw, content_type)
            if len(content) < MIN_PARSED_CONTENT_LENGTH:
                raise ValueError("parsed text is too short")
        except Exception as exc:
            if not _is_pdf_upload(filename, content_type):
                failures.append({"name": filename, "reason": str(exc)})
                continue
            content = _pdf_fallback_content(filename, str(exc))
            failures.append(
                {
                    "name": filename,
                    "reason": "PDF text extraction was incomplete; saved with a fallback note",
                }
            )
        parsed.append(
            await save_source_document(
                db,
                title=filename,
                content=content[:MAX_DOCUMENT_CONTENT_LENGTH],
                source_type="upload",
            )
        )

    if not parsed:
        detail = "; ".join(
            f"{item['name']}: {item['reason']}" for item in failures
        ) or "no supported files were parsed"
        raise HTTPException(status_code=400, detail=detail)

    return ok({"count": len(parsed), "files": parsed, "failures": failures})


@router.get("/{input_id}")
async def get_input(input_id: int, db: AsyncSession = Depends(get_db)):
    data = await get_mining_input(db, input_id)
    if data is None:
        raise HTTPException(status_code=404, detail="mining input not found")
    return ok(data)
