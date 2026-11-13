import asyncio
import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from starlette.requests import ClientDisconnect

from app.errors import ApiError
from app.ingestion.stream import content_length, receive_upload


async def chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


def test_stream_hashes_exact_bytes_across_chunks(tmp_path: Path) -> None:
    target = tmp_path / "source.csv"
    result = asyncio.run(
        receive_upload(chunks(b"a,b\n", b"1,2\n"), target, maximum=8, expected_length=8)
    )
    assert result.byte_count == 8
    assert result.sha256 == hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    assert target.read_bytes() == b"a,b\n1,2\n"


@pytest.mark.parametrize(
    ("parts", "maximum", "length", "code"),
    [
        ((b"1234", b"56"), 5, None, "upload_too_large"),
        ((b"",), 10, None, "empty_upload"),
        ((b"short",), 10, 8, "incomplete_upload"),
    ],
)
def test_rejected_streams_remove_only_their_partial_file(
    tmp_path: Path, parts: tuple[bytes, ...], maximum: int, length: int | None, code: str
) -> None:
    target = tmp_path / "source.csv"
    with pytest.raises(ApiError) as failure:
        asyncio.run(receive_upload(chunks(*parts), target, maximum=maximum, expected_length=length))
    assert failure.value.code == code
    assert not target.exists()


def test_disconnect_cleans_partial_bytes(tmp_path: Path) -> None:
    async def interrupted() -> AsyncIterator[bytes]:
        yield b"partial"
        raise ClientDisconnect()

    target = tmp_path / "source.csv"
    with pytest.raises(ApiError, match="interrupted"):
        asyncio.run(receive_upload(interrupted(), target, maximum=100, expected_length=None))
    assert not target.exists()


def test_existing_files_are_never_overwritten_or_deleted(tmp_path: Path) -> None:
    target = tmp_path / "source.csv"
    target.write_bytes(b"preserve")
    with pytest.raises(ApiError):
        asyncio.run(receive_upload(chunks(b"new"), target, maximum=100, expected_length=None))
    assert target.read_bytes() == b"preserve"


@pytest.mark.parametrize("value", ["-1", "1.5", "abc", "9" * 21])
def test_invalid_lengths_are_rejected_before_streaming(value: str) -> None:
    with pytest.raises(ApiError):
        content_length(value, 100)
