from typing import Any

SUCCESS_CODE = 0
MSG_SUCCESS = "success"

ERR_UNKNOWN = 10000
ERR_VALIDATION = 10001
ERR_NOT_FOUND = 10002
ERR_CANDIDATE_NOT_FOUND = 20101
ERR_MINING_IN_PROGRESS = 20103
ERR_UPLOAD_FAILED = 30102

HTTP_STATUS_TO_CODE = {
    400: ERR_VALIDATION,
    404: ERR_NOT_FOUND,
}


def ok(data: Any, msg: str = MSG_SUCCESS) -> dict:
    return {"code": SUCCESS_CODE, "data": data, "msg": msg}


def fail(code: int, msg: str) -> dict:
    return {"code": code, "data": None, "msg": msg}


def code_for_http_status(status_code: int) -> int:
    if status_code in HTTP_STATUS_TO_CODE:
        return HTTP_STATUS_TO_CODE[status_code]
    if 400 <= status_code < 500:
        return ERR_VALIDATION
    if status_code >= 500:
        return ERR_UNKNOWN
    return ERR_UNKNOWN
