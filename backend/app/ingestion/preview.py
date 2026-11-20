from pathlib import Path

from app.ingestion.models import DatasetPreview, ImportedDataset, PreviewCell
from app.schema.inspection import read_artifact

MAX_CELL_CHARACTERS = 128
MAX_PREVIEW_LIMIT = 25


def preview_rows(
    database: Path, imported: ImportedDataset, *, offset: int, limit: int
) -> DatasetPreview:
    if not 1 <= limit <= MAX_PREVIEW_LIMIT or offset < 0:
        raise ValueError("Invalid preview window.")
    row_count = imported.metadata.row_count
    assert row_count is not None
    columns = ['"' + column.safe_name.replace('"', '""') + '"' for column in imported.columns]
    projection = ", ".join(f"left({column}, {MAX_CELL_CHARACTERS + 1})" for column in columns)
    with read_artifact(database, imported) as connection:
        raw_rows = connection.execute(
            f"SELECT {projection} FROM data LIMIT ? OFFSET ?", [limit, offset]
        ).fetchall()
        if len(raw_rows) != min(limit, max(row_count - offset, 0)):
            raise ValueError("Preview row count differs from import metadata.")
    rows = [
        [
            PreviewCell(
                value=value[:MAX_CELL_CHARACTERS] if value is not None else None,
                truncated=value is not None and len(value) > MAX_CELL_CHARACTERS,
            )
            for value in row
        ]
        for row in raw_rows
    ]
    next_offset = offset + len(rows)
    return DatasetPreview(
        dataset_id=imported.metadata.id,
        dataset_version=imported.metadata.version,
        columns=imported.columns,
        rows=rows,
        offset=offset,
        next_offset=next_offset if next_offset < row_count else None,
        row_count=row_count,
    )
