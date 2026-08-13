from __future__ import annotations

from sqlalchemy import Engine, inspect


MIGRATION_ID = "20260812_01_six_module_ocr_snapshots"
OCR_TEXT_MIGRATION_ID = "20260812_02_ocr_debug_text"


def _columns(engine: Engine, table: str) -> set[str]:
    return {item["name"] for item in inspect(engine).get_columns(table)}


def migrate(engine: Engine) -> None:
    """Idempotent, additive migration. It never drops tables, columns or rows."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = connection.exec_driver_sql(
            "SELECT 1 FROM schema_migrations WHERE id = ?", (MIGRATION_ID,)
        ).first()
        additions = {
            "resume_versions": {
                "source_type": "TEXT",
                "parser_method": "TEXT",
                "ocr_used": "BOOLEAN",
                "ocr_metadata_json": "TEXT",
                "structured_resume_json": "TEXT",
                "structured_prompt_version": "TEXT",
            },
            "jobs": {
                "parser_method": "TEXT",
                "ocr_used": "BOOLEAN",
                "ocr_metadata_json": "TEXT",
                "structured_jd_json": "TEXT",
                "structured_prompt_version": "TEXT",
            },
            "generations": {
                "resume_structure_json": "TEXT",
                "jd_analysis_json": "TEXT",
                "resume_structure_prompt_version": "TEXT",
                "jd_analysis_prompt_version": "TEXT",
                "structured_repair_prompt_version": "TEXT",
            },
        }
        if not applied:
            for table, columns in additions.items():
                existing = _columns(engine, table)
                for name, sql_type in columns.items():
                    if name not in existing:
                        connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
            connection.exec_driver_sql("INSERT INTO schema_migrations (id) VALUES (?)", (MIGRATION_ID,))

        ocr_text_applied = connection.exec_driver_sql(
            "SELECT 1 FROM schema_migrations WHERE id = ?", (OCR_TEXT_MIGRATION_ID,)
        ).first()
        if not ocr_text_applied:
            for table in ("resume_versions", "jobs"):
                if "ocr_text" not in _columns(engine, table):
                    connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "ocr_text" TEXT')
            connection.exec_driver_sql("INSERT INTO schema_migrations (id) VALUES (?)", (OCR_TEXT_MIGRATION_ID,))
