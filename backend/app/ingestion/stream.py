"""Receive bounded raw request bytes without buffering an entire upload in memory."""

import hashlib
import re
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path

import anyio
from starlette.requests import ClientDisconnect

from app.errors import ApiError


@dataclass(frozen=True)
class ReceivedUpload:
    byte_count: int
    sha256: str


def content_length(value: str | None, maximum: int) -> int | None:
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{1,20}", value) is None:
        raise ApiError(400, "invalid_content_length", "Content-Length must be a valid byte count.")
    length = int(value)
    if length > maximum:
        raise ApiError(413, "upload_too_large", f"CSV upload exceeds the {maximum}-byte limit.")
    return length


async def receive_upload(
    chunks: AsyncIterable[bytes], path: Path, *, maximum: int, expected_length: int | None
) -> ReceivedUpload:
    digest = hashlib.sha256()
    received = 0
    created = False
    try:
        async with await anyio.open_file(path, "xb") as output:
            created = True
            async for chunk in chunks:
                if len(chunk) > maximum - received:
                    raise ApiError(
                        413, "upload_too_large", f"CSV upload exceeds the {maximum}-byte limit."
                    )
                received += len(chunk)
                digest.update(chunk)
                await output.write(chunk)
        if received == 0:
            raise ApiError(400, "empty_upload", "Upload a nonempty UTF-8 CSV file.")
        if expected_length is not None and received != expected_length:
            raise ApiError(400, "incomplete_upload", "The upload ended before its declared length.")
        return ReceivedUpload(received, digest.hexdigest())
    except BaseException as error:
        if created:
            path.unlink(missing_ok=True)
        if isinstance(error, ClientDisconnect):
            raise ApiError(400, "upload_interrupted", "The upload was interrupted.") from None
        if isinstance(error, OSError):
            raise ApiError(
                503, "upload_storage_unavailable", "Upload storage is unavailable."
            ) from None
        raise
