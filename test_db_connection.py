import os
import sys
import pyodbc
import streamlit as st

# Database Configuration
DB_SERVER = ""
DB_NAME = ""
DB_USERNAME = ""
DB_PASSWORD = ""
DB_DRIVER = ""

# Override with secrets if available
try:
    if 'DB_SERVER' in st.secrets:
        DB_SERVER = st.secrets.get("DB_SERVER", DB_SERVER)
        DB_NAME = st.secrets.get("DB_NAME", DB_NAME)
        DB_USERNAME = st.secrets.get("DB_USERNAME", DB_USERNAME)
        DB_PASSWORD = st.secrets.get("DB_PASSWORD", DB_PASSWORD)
        DB_DRIVER = st.secrets.get("DB_DRIVER", DB_DRIVER)
    else:
        # Use environment variables as fallback
        DB_SERVER = os.getenv('AZURE_DB_SERVER', '')
        DB_NAME = os.getenv('AZURE_DB_NAME', '')
        DB_USERNAME = os.getenv('AZURE_DB_USERNAME', '')
        DB_PASSWORD = os.getenv('AZURE_DB_PASSWORD', '')
        
        # Use appropriate driver format based on platform
        if os.name == 'nt':  # Windows
            DB_DRIVER = os.getenv('AZURE_DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
        else:  # Linux (including Streamlit Cloud)
            DB_DRIVER = os.getenv('AZURE_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
except Exception as e:
    print(f"Error loading secrets: {str(e)}")

def test_db_connection():
    """Test connection to Azure SQL Database"""
    print(f"Platform: {os.name}, Python: {sys.version}")
    print(f"Attempting to connect to: {DB_SERVER}/{DB_NAME} using driver: {DB_DRIVER}")
    
    try:
        conn_str = f"DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};Connection Timeout=30;"
        conn = pyodbc.connect(conn_str)
        
        print("Connection successful!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        row = cursor.fetchone()
        print(f"SQL Server version: {row[0]}")
        
        # Close connection
        cursor.close()
        conn.close()
        
        return True
    except pyodbc.Error as e:
        error_code = e.args[0] if len(e.args) > 0 else "Unknown"
        print(f"Database connection error [{error_code}]: {str(e)}")
        print(f"Driver: {DB_DRIVER}, Server: {DB_SERVER}, DB: {DB_NAME}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    test_db_connection()
