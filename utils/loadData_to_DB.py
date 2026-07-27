import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
from excel_to_sql import ExcelToSQL
from config import config
from utils.logger import get_logger

logger = get_logger("loadData_to_DB")

table_name = "Accounts"
excel_file_path = r"C:\Users\aysharma\Desktop\Projects\Old_Projects\New_Chat_bot_Query_data\excel_files\dbo.Accounts.xlsx"
db_name = config.DATABASE_PATH

def loadData_inDB(excel_file_path, db_name, table_name):
    logger.info(f"Loading data | excel: {excel_file_path} | db: {db_name} | table: {table_name}")
    db_tool = ExcelToSQL(db_name=db_name)

    if not db_tool.connect():
        logger.error("Database connection failed, aborting data load")
        return

    table_name = db_tool.import_excel_to_sql(excel_file_path, table_name=table_name)
    logger.info(f"Data loaded to table: {table_name}")
    print(f"Data imported to table: {table_name}")


def rebuild_database_from_excel(excel_folder=None, db_name=None):
    """
    Recreate the SQLite database from every `dbo.<Table>.xlsx` file in excel_folder.
    Each file replaces its corresponding table (df.to_sql(if_exists="replace")).

    Returns a list of dicts: {"file", "table", "rows", "status", "error"}
    """
    excel_folder = excel_folder or getattr(config, "EXCEL_FOLDER", "excel_files")
    db_name = db_name or config.DATABASE_PATH
    excel_dir = Path(excel_folder)

    logger.info(f"Rebuilding database '{db_name}' from Excel folder '{excel_dir}'")

    if not excel_dir.exists():
        logger.error(f"Excel folder not found: {excel_dir}")
        return [{"file": str(excel_dir), "table": None, "rows": 0, "status": "error", "error": "Excel folder not found"}]

    excel_files = sorted(excel_dir.glob("*.xlsx"))
    if not excel_files:
        logger.warning(f"No .xlsx files found in {excel_dir}")
        return []

    db_tool = ExcelToSQL(db_name=db_name)
    if not db_tool.connect():
        logger.error("Database connection failed, aborting rebuild")
        return [{"file": str(excel_dir), "table": None, "rows": 0, "status": "error", "error": "Database connection failed"}]

    results = []
    try:
        for excel_path in excel_files:
            table = excel_path.stem
            if table.lower().startswith("dbo."):
                table = table[4:]

            try:
                imported_table = db_tool.import_excel_to_sql(str(excel_path), table_name=table)
                if imported_table:
                    row_count = db_tool.cursor.execute(f"SELECT COUNT(*) FROM {imported_table}").fetchone()[0]
                    results.append({"file": excel_path.name, "table": imported_table, "rows": row_count, "status": "success", "error": None})
                    logger.info(f"Rebuilt table '{imported_table}' from {excel_path.name} ({row_count} rows)")
                else:
                    results.append({"file": excel_path.name, "table": table, "rows": 0, "status": "error", "error": "Import failed"})
            except Exception as e:
                logger.error(f"Failed to import {excel_path.name}: {e}")
                results.append({"file": excel_path.name, "table": table, "rows": 0, "status": "error", "error": str(e)})
    finally:
        db_tool.disconnect()

    success_count = sum(1 for r in results if r["status"] == "success")
    logger.info(f"Database rebuild complete: {success_count}/{len(results)} tables loaded successfully")
    return results


if __name__ == "__main__":
    # Run the loadData_inDB function
    loadData_inDB(excel_file_path, db_name, table_name)


