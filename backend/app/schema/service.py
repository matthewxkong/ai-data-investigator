from app.errors import ApiError
from app.ingestion.models import ImportedDataset
from app.ingestion.service import IngestionService
from app.schema.inference import ColumnEvidence
from app.schema.inspection import SchemaInspector
from app.schema.models import OverrideRequest, SchemaResponse, StoredOverrides
from app.schema.repository import SchemaRepository


class SchemaService:
    def __init__(self, ingestion: IngestionService, repository: SchemaRepository) -> None:
        self.ingestion = ingestion
        self.repository = repository
        self.inspector = SchemaInspector()

    @staticmethod
    def response(
        imported: ImportedDataset, evidence: tuple[ColumnEvidence, ...], stored: StoredOverrides
    ) -> SchemaResponse:
        assert imported.metadata.row_count is not None
        return SchemaResponse(
            dataset_id=imported.metadata.id,
            dataset_version=imported.metadata.version,
            source_sha256=imported.sha256,
            schema_revision=stored.revision,
            rows_examined=imported.metadata.row_count,
            columns=tuple(
                values.column(column, stored.overrides.get(column.safe_name))
                for column, values in zip(imported.columns, evidence, strict=True)
            ),
        )

    def inspect(self, imported: ImportedDataset) -> SchemaResponse:
        with self.inspector.capacity():
            evidence = self.inspector.scan(
                self.ingestion.artifact_path(imported.metadata) / "data.duckdb", imported
            )
            stored = self.repository.get(
                imported.metadata.id, owner_id=imported.metadata.session_id
            )
            return self.response(imported, evidence, stored)

    def replace(self, imported: ImportedDataset, request: OverrideRequest) -> SchemaResponse:
        names = {column.safe_name for column in imported.columns}
        if request.overrides.keys() - names:
            raise ApiError(
                422, "unknown_column", "Overrides must reference existing safe column names."
            )
        with self.inspector.capacity():
            evidence = self.inspector.scan(
                self.ingestion.artifact_path(imported.metadata) / "data.duckdb", imported
            )
            for column, values in zip(imported.columns, evidence, strict=True):
                override = request.overrides.get(column.safe_name)
                if override is not None and not values.accepts(override):
                    raise ApiError(
                        422,
                        "incompatible_override",
                        "An override does not match every non-null value, or needs a date order.",
                    )
            stored = self.repository.replace(
                imported.metadata.id, owner_id=imported.metadata.session_id, request=request
            )
            return self.response(imported, evidence, stored)
