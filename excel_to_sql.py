"""
Excel to SQL Database Tool
This script imports Excel data into a SQLite database and provides querying functionality
"""

import pandas as pd
import sqlite3
import os
from pathlib import Path

from config import config
from utils.logger import get_logger
from utils.sql_guardrail import validate_sql

logger = get_logger("excel_to_sql")

class ExcelToSQL:
    def __init__(self, db_name=None):
        if db_name is None:
            db_name = config.DATABASE_PATH
        """
        Initialize the database connection
        
        Args:
            db_name (str): Name of the SQLite database file
        """
        self.db_name = db_name
        self.connection = None
        self.cursor = None
    
    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_name)
            self.cursor = self.connection.cursor()
            logger.info(f"Connected to database: {self.db_name}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.debug("Database connection closed")
    
    def import_excel_to_sql(self, excel_path, sheet_name=0, table_name=None):
        logger.info(f"Importing Excel: {excel_path} | sheet: {sheet_name} | table: {table_name}")
        try:
            if not os.path.exists(excel_path):
                raise FileNotFoundError(f"Excel file not found: {excel_path}")
            
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            logger.info(f"Excel loaded: {len(df)} rows, {len(df.columns)} columns")
            
            if table_name is None:
                table_name = Path(excel_path).stem.replace(' ', '_').replace('-', '_')
            
            df.to_sql(table_name, self.connection, if_exists='replace', index=False)
            logger.info(f"Data imported to table: {table_name} ({len(df)} rows)")
            
            return table_name
            
        except Exception as e:
            logger.error(f"Excel import failed: {e}")
            return None
    
    def list_tables(self):
        """List all tables in the database"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = self.cursor.fetchall()
        return [table[0] for table in tables]
    
    def execute_query(self, query, params=None, allow_write=True):
        logger.debug(f"Executing query: {query[:100]}...")

        if not allow_write:
            validation = validate_sql(query)
            if not validation.is_valid:
                logger.error(f"Blocked query under allow_write=False ({validation.reason}): {query[:120]}")
                return None, None

        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                results = self.cursor.fetchall()
                columns = [description[0] for description in self.cursor.description]
                logger.debug(f"Query returned {len(results)} rows, {len(columns)} columns")
                return results, columns
            else:
                self.connection.commit()
                logger.debug(f"Non-SELECT query: {self.cursor.rowcount} rows affected")
                return self.cursor.rowcount, None
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None, None
    
    def get_table_info(self, table_name):
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = self.cursor.fetchall()
            logger.debug(f"Table info fetched for '{table_name}': {len(columns)} columns")
            return columns
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            return None
    
    def preview_table(self, table_name, limit=5):
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        results, columns = self.execute_query(query)
        
        if results and columns:
            logger.info(f"Previewed '{table_name}': {len(results)} rows")
            print(f"\n[DATA] Preview of '{table_name}' (first {len(results)} rows):")
            print(f"Columns: {', '.join(columns)}")
            print("-" * 50)
            for row in results:
                print(row)
            return results, columns
        return None, None


def main(excel_file_path, db_name, table_name):
    """Main function to demonstrate the tool"""
    
    # Initialize the database tool
    db_tool = ExcelToSQL(db_name=db_name)
    
    # Connect to database
    if not db_tool.connect():
        return
    
    # ===== STEP 1: Import Excel data =====
    # Replace 'your_file.xlsx' with your actual Excel file path
    excel_file_path = excel_file_path #r"C:\Users\aysharma\Desktop\Projects\Old_Projects\New_Chat_bot_Query_data\sample\dbo.Accounts.xlsx"  # Change this to your Excel file path
    
    # # Create a sample Excel file for demonstration (remove this in production)
    # if not os.path.exists(excel_file_path):
    #     print(f"\n>> Creating sample Excel file: {excel_file_path}")
    #     sample_data = {
    #         'ID': [1, 2, 3, 4, 5],
    #         'Name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    #         'Age': [25, 30, 35, 28, 32],
    #         'Department': ['Sales', 'Engineering', 'Marketing', 'Sales', 'Engineering'],
    #         'Salary': [50000, 75000, 60000, 55000, 80000]
    #     }
    #     sample_df = pd.DataFrame(sample_data)
    #     sample_df.to_excel(excel_file_path, index=False)
    #     print(f"[OK] Created sample Excel file with 5 records")
    
    # Import Excel to SQL
    # table_name = db_tool.import_excel_to_sql(excel_file_path, table_name=table_name)
    
    # if table_name:
    #     print(f"\n[OK] Successfully imported data to table: '{table_name}'")
        
    #     # Preview the imported data
    #     db_tool.preview_table(table_name)
        
    #     # ===== STEP 2: Query the database using SQL =====
    #     print("\n" + "="*60)
    #     print("🔍 RUNNING SQL QUERIES")
    #     print("="*60)
        
    #     # Example 1: Select all data
    #     print("\n1. SELECT * FROM employees:")
    #     results, columns = db_tool.execute_query("SELECT * FROM employees")
    #     if results:
    #         for row in results:
    #             print(row)
        
    #     # Example 2: Filter with WHERE clause
    #     print("\n2. Employees with salary > 60000:")
    #     query = "SELECT Name, Department, Salary FROM employees WHERE Salary > ?"
    #     results, columns = db_tool.execute_query(query, (60000,))
    #     if results:
    #         print(f"{'Name':<10} {'Department':<15} {'Salary':<10}")
    #         print("-"*35)
    #         for row in results:
    #             print(f"{row[0]:<10} {row[1]:<15} {row[2]:<10}")
        
    #     # Example 3: Aggregation query
    #     print("\n3. Average salary by department:")
    #     query = """
    #     SELECT Department, 
    #            COUNT(*) as Employee_Count,
    #            AVG(Salary) as Avg_Salary,
    #            MIN(Salary) as Min_Salary,
    #            MAX(Salary) as Max_Salary
    #     FROM employees 
    #     GROUP BY Department
    #     """
    #     results, columns = db_tool.execute_query(query)
    #     if results:
    #         print(f"{'Department':<15} {'Count':<8} {'Avg Salary':<12} {'Min':<10} {'Max':<10}")
    #         print("-"*55)
    #         for row in results:
    #             print(f"{row[0]:<15} {row[1]:<8} ${row[2]:<11.2f} ${row[3]:<9} ${row[4]:<10}")
        
    #     # Example 4: Complex query with sorting
    #     print("\n4. Employees sorted by age (descending):")
    #     query = "SELECT Name, Age, Department FROM employees ORDER BY Age DESC"
    #     results, columns = db_tool.execute_query(query)
    #     if results:
    #         for row in results:
    #             print(f"{row[0]} - Age: {row[1]} - Dept: {row[2]}")
    
    # ===== STEP 3: Custom query input =====
    print("\n" + "="*60)
    print("[TIP] CUSTOM QUERY MODE")
    print("="*60)
    print("You can now run your own SQL queries!")
    print("Type 'exit' to quit, 'tables' to list tables, 'info <table>' for table info")
    
    while True:
        query = input("\n>> Enter SQL query: ").strip()
        
        if query.lower() == 'exit':
            break
        elif query.lower() == 'tables':
            tables = db_tool.list_tables()
            print(f"Tables in database: {', '.join(tables)}")
            continue
        elif query.lower().startswith('info'):
            parts = query.split()
            if len(parts) > 1:
                table_name = parts[1]
                info = db_tool.get_table_info(table_name)
                if info:
                    print(f"\nStructure of table '{table_name}':")
                    for col in info:
                        print(f"  - {col[1]} ({col[2]})")
                else:
                    print(f"Table '{table_name}' not found")
            else:
                print("Usage: info <table_name>")
            continue
        elif not query:
            continue
        
        # Execute custom query
        results, columns = db_tool.execute_query(query)
        
        if results is not None:
            if columns:  # SELECT query
                if len(results) == 0:
                    print("No results found")
                else:
                    print(f"\n[OK] Query returned {len(results)} row(s)")
                    print(f"Columns: {', '.join(columns)}")
                    print("-" * 50)
                    for row in results:
                        print(row)
            elif results is not None:  # INSERT/UPDATE/DELETE
                print(f"[OK] Query executed successfully. {results} row(s) affected.")
        else:
            print("Failed to execute query. Check your SQL syntax.")
    
    # Close connection
    db_tool.disconnect()
    
    print("\n" + "="*60)
    print("[FILE] Database file saved as:", db_tool.db_name)
    print("You can reuse this database later by running this script again!")
    print("="*60)


def load_existing_database(db_path=config.DATABASE_PATH):
    """
    Function to load an existing database and query it
    
    Args:
        db_path (str): Path to existing SQLite database file
    """
    print(f"\n[DB] Loading existing database: {db_path}")
    db_tool = ExcelToSQL(db_name=db_path)
    
    if db_tool.connect():
        tables = db_tool.list_tables()
        print(f"Found tables: {', '.join(tables)}")
        
        # Example: Query existing data
        for table in tables:
            print(f"\n[DATA] Previewing table: {table}")
            db_tool.preview_table(table)
        
        db_tool.disconnect()
        return db_tool
    return None


if __name__ == "__main__":
    # Run the main function
    main(excel_file_path=r"C:\Users\aysharma\Desktop\Projects\Old_Projects\New_Chat_bot_Query_data\excel_files\dbo.Accounts.xlsx", 
         db_name=config.DATABASE_PATH, 
         table_name="Accounts")