import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from app.baseline.compare import compare_result
from app.baseline.execution import (
    DEVELOPMENT_ROOT,
    FIXTURE_ROOT,
    fixture_services,
    import_fixture,
    run_reference,
)
from app.baseline.models import BaselineReport, CaseResult, QueryEvidence, ResultValue, Tolerance
from app.fixtures.inventory import generate_inventory
from app.fixtures.references import load_development_suite
from app.fixtures.sales import generate_sales
from app.fixtures.tickets import generate_tickets
from app.ingestion.models import ImportedDataset

REPORT_PATH = DEVELOPMENT_ROOT / "baseline.json"
DEFAULT_ROW_LIMIT = 100


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def report_text(report: BaselineReport) -> str:
    return report.model_dump_json(indent=2) + "\n"


async def run_baseline(
    tolerance: Tolerance, *, row_limit: int = DEFAULT_ROW_LIMIT
) -> BaselineReport:
    suite = load_development_suite()
    generators = {
        "sales": generate_sales,
        "tickets": generate_tickets,
        "inventory": generate_inventory,
    }
    results: list[CaseResult] = []
    with TemporaryDirectory(prefix="adi-baseline-") as workspace:
        services = fixture_services(Path(workspace))
        imports: dict[str, ImportedDataset] = {}
        for case in suite.cases:
            dataset = case.dataset
            if dataset not in imports:
                fixture = (FIXTURE_ROOT / f"{dataset}.csv").read_bytes()
                if fixture != generators[dataset](suite.fixture_seed).csv_bytes():
                    raise ValueError(f"{dataset} fixture differs from the development suite seed.")
                imports[dataset] = await import_fixture(services, dataset, fixture)
            imported = imports[dataset]
            database = services.ingestion.artifact_path(imported.metadata) / "data.duckdb"
            sql, result = run_reference(database, imported, case, row_limit=row_limit)
            expected: list[list[ResultValue]] = [
                [value for value in row] for row in case.expected_rows
            ]
            mismatch = compare_result(result, case.columns, expected, tolerance)
            evidence = QueryEvidence(
                dataset=dataset,
                dataset_version=f"fixture-v{suite.generator_version}:{imported.sha256}",
                source_sha256=imported.sha256,
                sql_sha256=sha256(sql),
                result_sha256=sha256(result.model_dump_json().encode("utf-8")),
            )
            results.append(
                CaseResult(
                    case_id=case.id,
                    question=case.question,
                    evidence=evidence,
                    result=result,
                    expected_columns=case.columns,
                    expected_rows=expected,
                    passed=mismatch is None,
                    mismatch=mismatch,
                )
            )
    return BaselineReport(
        fixture_seed=suite.fixture_seed,
        fixture_generator_version=suite.generator_version,
        duckdb_version=duckdb.__version__,
        tolerance=tolerance,
        cases=results,
        passed=all(case.passed for case in results),
    )
