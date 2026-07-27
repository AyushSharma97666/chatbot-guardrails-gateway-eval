import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from excel_to_sql import ExcelToSQL
import pandas as pd

from config import config
from utils.logger import get_logger
from utils.sql_guardrail import validate_sql

logger = get_logger("data_extraction")
DATABASE_PATH = config.DATABASE_PATH


def load_database_and_query(db_path=DATABASE_PATH, query=None, table_name=None, filters=None):
    """
    Load an existing SQL database and execute queries to extract data
    
    Args:
        db_path (str): Path to the SQLite database file
        query (str): SQL query to execute (if None, will use table_name and filters)
        table_name (str): Name of table to query (used if query is None)
        filters (dict): Filters for WHERE clause e.g., {'Age': 30, 'Department': 'Sales'}
    
    Returns:
        dict: Dictionary containing query results, columns, and status
    """
    results = {
        'success': False,
        'data': None,
        'columns': None,
        'row_count': 0,
        'error': None
    }
    
    logger.info(f"Loading database: {db_path} | query: {str(query)[:60]}... | table: {table_name}")
    db_tool = ExcelToSQL(db_name=db_path)
    
    try:
        if not db_tool.connect():
            results['error'] = "Failed to connect to database"
            logger.error(f"Connection failed to database: {db_path}")
            return results
        
        tables = db_tool.list_tables()
        logger.info(f"Database loaded: {db_path} | tables: {', '.join(tables)}")
        print(f"\n[DB] Loaded database: {db_path}")
        print(f"[TBL] Available tables: {', '.join(tables)}")
        
        # If no query provided, build one from parameters
        if query is None and table_name:
            if table_name not in tables:
                results['error'] = f"Table '{table_name}' not found in database"
                db_tool.disconnect()
                return results
            
            # Build SELECT query
            query = f"SELECT * FROM {table_name}"
            
            # Add WHERE clause if filters provided
            if filters and isinstance(filters, dict):
                conditions = []
                params = []
                for key, value in filters.items():
                    conditions.append(f"{key} = ?")
                    params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                    print(f"\n[SRCH] Using filters: {filters}")
                    
                    # Execute with parameters
                    data, columns = db_tool.execute_query(query, tuple(params))
                else:
                    data, columns = db_tool.execute_query(query)
            else:
                data, columns = db_tool.execute_query(query)
        
        elif query:
            # Execute custom query
            print(f"\n[SRCH] Executing query: {query}")
            data, columns = db_tool.execute_query(query)
        
        else:
            results['error'] = "No query or table specified"
            db_tool.disconnect()
            return results
        
        logger.info(f"Query executed | rows: {len(data) if data else 0} | columns: {columns}")
        if data is not None and columns is not None:
            results['success'] = True
            results['data'] = data
            results['columns'] = columns
            results['row_count'] = len(data)
            
            # Display results
            print(f"\n[OK] Query successful! Retrieved {len(data)} row(s)")
            print(f"[DATA] Columns: {', '.join(columns)}")
            print("-" * 60)
            
            # Display first few rows
            for i, row in enumerate(data[:10]):  # Show first 10 rows
                print(f"Row {i+1}: {dict(zip(columns, row))}")
            
            if len(data) > 10:
                print(f"... and {len(data) - 10} more row(s)")
        
        elif data is not None:
            # For non-SELECT queries
            results['success'] = True
            results['row_count'] = data
            print(f"\n[OK] Query executed successfully. {data} row(s) affected.")
        
        else:
            results['error'] = "Query returned no results or failed"
        
    except Exception as e:
        results['error'] = str(e)
        logger.error(f"Database query failed: {e}")
        print(f"\n[ERR] Error: {e}")
    
    finally:
        db_tool.disconnect()
        logger.debug("Database connection closed")
    
    return results


def extract_data_with_query(db_path, query):
    logger.info(f"Extracting data | db: {db_path} | query: {str(query)[:80]}...")

    validation = validate_sql(query)
    if not validation.is_valid:
        logger.warning(f"Rejected non-SELECT/unsafe query ({validation.reason}): {str(query)[:120]}")
        return None, None

    db_tool = ExcelToSQL(db_name=db_path)

    if db_tool.connect():
        data, columns = db_tool.execute_query(validation.cleaned_sql, allow_write=False)
        db_tool.disconnect()
        
        if data and columns:
            logger.info(f"Data extracted: {len(data)} rows, {len(columns)} columns")
            print(f"\n[OK] Extracted {len(data)} rows")
            return data, columns
        else:
            logger.warning("No data found or query failed")
            print("[ERR] No data found or query failed")
            return None, None
    
    logger.error(f"Failed to connect to database: {db_path}")
    return None, None


def extract_table_data(db_path, table_name, limit=None, order_by=None):
    logger.info(f"Extracting table | table: {table_name} | limit: {limit} | order: {order_by}")
    db_tool = ExcelToSQL(db_name=db_path)
    
    if db_tool.connect():
        query = f"SELECT * FROM {table_name}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        
        data, columns = db_tool.execute_query(query)
        db_tool.disconnect()
        
        if data and columns:
            df = pd.DataFrame(data, columns=columns)
            logger.info(f"Table extracted: {len(df)} rows from '{table_name}'")
            print(f"\n[OK] Extracted {len(df)} rows from '{table_name}'")
            return df
        else:
            logger.warning(f"No data from table '{table_name}'")
            print(f"[ERR] Failed to extract data from '{table_name}'")
            return pd.DataFrame()
    
    logger.error(f"Connection failed for table extraction: {table_name}")
    return pd.DataFrame()


# ===== EXAMPLES OF HOW TO USE THESE FUNCTIONS =====

def query_data():
    """Demonstrate how to use the extraction functions"""
    
    # Example 1: Load database and run custom query
    print("="*60)
    print("EXAMPLE 1: Custom SQL Query")
    print("="*60)

    # custom_query = "update Encounters set [Attending Provider ID] = 9948 where [master patient id] = 100000 ;"
    custom_query = "SELECT DISTINCT [provider full name] from Physicians p inner join Encounters e ON e.[Attending Provider ID] = p.[Provider ID];"
#   h.[Hospital Name]
# FROM Hospitals AS h
# INNER JOIN Departments AS d
#   ON h.[Hospital ID] = d.[Hospital ID]
# INNER JOIN Encounters AS e
#   ON d.[Department ID] = e.[Department ID]
# INNER JOIN Physicians AS p
#   ON e.[Attending Provider ID] = p.[Provider ID]
# WHERE
#   p.[Provider Full Name] = 'Dodson, Donavon';" #SELECT name FROM sqlite_master WHERE type='table'
    result = load_database_and_query(
        db_path=DATABASE_PATH,
        query=custom_query
    )
    
    if result['success']:
        print(f"\n[CHART] Found {result['row_count']} employees ")
        # Access the data
        for row in result['data']:
            print(f"  - {row}")
    
    # # Example 2: Extract data with filters
    # print("\n" + "="*60)
    # print("EXAMPLE 2: Extract with Filters")
    # print("="*60)
    
    # result = load_database_and_query(
    #     db_path=DATABASE_PATH,
    #     table_name="employees",
    #     filters={'Department': 'Engineering', 'Age': 30}
    # )
    
    # # Example 3: Simple extraction function
    # print("\n" + "="*60)
    # print("EXAMPLE 3: Simple Query Function")
    # print("="*60)
    
    # data, columns = extract_data_with_query(
    #     DATABASE_PATH,
    #     "SELECT * FROM employees WHERE Department = 'Sales'"
    # )
    
    # if data:
    #     print(f"Columns: {columns}")
    #     for row in data:
    #         print(f"  {row}")
    
    # # Example 4: Extract as DataFrame
    # print("\n" + "="*60)
    # print("EXAMPLE 4: Extract as DataFrame")
    # print("="*60)
    
    # df = extract_table_data(
    #     DATABASE_PATH,
    #     table_name="employees",
    #     limit=5,
    #     order_by="Salary DESC"
    # )
    
    # if not df.empty:
    #     print("\nDataFrame preview:")
    #     print(df)
        
    #     # You can now use pandas for further analysis
    #     print(f"\n[DATA] Summary Statistics:")
    #     print(f"Average Salary: ${df['Salary'].mean():.2f}")
    #     print(f"Age Range: {df['Age'].min()} - {df['Age'].max()}")
    
    return result


# ===== ADVANCED EXTRACTION FUNCTION =====

class DatabaseExtractor:
    """
    Advanced class for extracting and manipulating data from database
    """
    
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.db_tool = None
    
    def connect(self):
        """Establish database connection"""
        self.db_tool = ExcelToSQL(self.db_path)
        return self.db_tool.connect()
    
    def disconnect(self):
        """Close database connection"""
        if self.db_tool:
            self.db_tool.disconnect()
    
    def extract_all(self, table_name):
        """Extract all data from a table"""
        if self.connect():
            data, columns = self.db_tool.execute_query(f"SELECT * FROM {table_name}")
            self.disconnect()
            return data, columns
        return None, None
    
    def extract_filtered(self, table_name, conditions):
        """
        Extract data with custom conditions
        
        Args:
            table_name (str): Name of the table
            conditions (str): WHERE clause conditions (e.g., "Age > 30 AND Department = 'Sales'")
        """
        if self.connect():
            query = f"SELECT * FROM {table_name} WHERE {conditions}"
            data, columns = self.db_tool.execute_query(query)
            self.disconnect()
            return data, columns
        return None, None
    
    def extract_custom(self, query):
        """Extract data using custom query"""
        if self.connect():
            data, columns = self.db_tool.execute_query(query)
            self.disconnect()
            return data, columns
        return None, None
    
    def extract_to_dataframe(self, query):
        """Extract query results as pandas DataFrame"""
        if self.connect():
            data, columns = self.db_tool.execute_query(query)
            self.disconnect()
            if data and columns:
                return pd.DataFrame(data, columns=columns)
        return pd.DataFrame()


# Example of using the DatabaseExtractor class
def advanced_extraction_example():
    """Demonstrate advanced extraction features"""
    
    extractor = DatabaseExtractor(DATABASE_PATH)
    
    # Extract all data
    data, columns = extractor.extract_all("employees")
    if data:
        print(f"All employees: {len(data)} records")
    
    # Extract with conditions
    data, columns = extractor.extract_filtered(
        "employees", 
        "Age > 28 AND Salary >= 60000"
    )
    if data:
        print(f"Senior employees: {len(data)} records")
    
    # Extract to DataFrame for analysis
    df = extractor.extract_to_dataframe(
        "SELECT Department, AVG(Salary) as avg_salary FROM employees GROUP BY Department"
    )
    if not df.empty:
        print("\nAverage salary by department:")
        print(df)


if __name__ == "__main__":
    # Run examples (make sure database exists first)
    # First, check if database exists
    if os.path.exists(DATABASE_PATH):
        query_data()
    else:
        print(f"Database '{DATABASE_PATH}' not found. Please load data first.")