import os
import sys
import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import time
import io
import datetime
import requests
import shutil
import uuid
import tempfile
import subprocess
from PIL import Image
import pyodbc
import urllib.parse
import msal

# Set page configuration
st.set_page_config(
    page_title="Project Image Upload",
    page_icon="📷",
    layout="centered"
)

# Display logo at the left
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    # Load image with PIL and resize with high quality
    img = Image.open("logo.jpg")
    # Resize with high quality resampling
    new_width = 150
    width_percent = (new_width / float(img.size[0]))
    new_height = int((float(img.size[1]) * float(width_percent)))
    img = img.resize((new_width, new_height), Image.LANCZOS)
    # Display the resized image
    st.image(img)

# File paths
UPLOAD_FOLDER = "uploads"

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tif', 'tiff', 'pdf'}

# Initialize with empty defaults
EMAIL_SENDER = ""
EMAIL_SENDER_NAME = "Project Upload"
BREVO_SMTP_SERVER = ""
BREVO_SMTP_PORT = 587
BREVO_SMTP_LOGIN = ""
BREVO_SMTP_PASSWORD = ""
ADMIN_PASSWORD = ""
SLACK_WEBHOOK_URL = ""

# Database Configuration
DB_SERVER = ""
DB_NAME = ""
DB_USERNAME = ""
DB_PASSWORD = ""
# Default driver - will be overridden based on platform
if os.name == 'nt':  # Windows
    DB_DRIVER = "{ODBC Driver 17 for SQL Server}"
else:  # Linux (including Streamlit Cloud)
    DB_DRIVER = "ODBC Driver 17 for SQL Server"

# SharePoint Configuration
SHAREPOINT_CLIENT_ID = ""
SHAREPOINT_CLIENT_SECRET = ""
SHAREPOINT_TENANT_ID = ""
SHAREPOINT_AUTHORITY = ""
SHAREPOINT_SCOPES = ["https://graph.microsoft.com/.default"]

# Override with secrets if available
try:
    if 'EMAIL_SENDER' in st.secrets:
        EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
        EMAIL_SENDER_NAME = st.secrets.get("EMAIL_SENDER_NAME", EMAIL_SENDER_NAME)
        BREVO_SMTP_SERVER = st.secrets.get("BREVO_SMTP_SERVER", BREVO_SMTP_SERVER)
        BREVO_SMTP_PORT = st.secrets.get("BREVO_SMTP_PORT", BREVO_SMTP_PORT)
        BREVO_SMTP_LOGIN = st.secrets.get("BREVO_SMTP_LOGIN", BREVO_SMTP_LOGIN)
        BREVO_SMTP_PASSWORD = st.secrets.get("BREVO_SMTP_PASSWORD", BREVO_SMTP_PASSWORD)
        ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", ADMIN_PASSWORD)
        SLACK_WEBHOOK_URL = st.secrets.get("SLACK_WEBHOOK_URL", SLACK_WEBHOOK_URL)
        
    # Load database credentials from secrets if available
    if 'DB_SERVER' in st.secrets:
        DB_SERVER = st.secrets.get("DB_SERVER", DB_SERVER)
        DB_NAME = st.secrets.get("DB_NAME", DB_NAME)
        DB_USERNAME = st.secrets.get("DB_USERNAME", DB_USERNAME)
        DB_PASSWORD = st.secrets.get("DB_PASSWORD", DB_PASSWORD)
        DB_DRIVER = st.secrets.get("DB_DRIVER", DB_DRIVER)
        
    # Load SharePoint credentials from secrets if available
    if 'SHAREPOINT_CLIENT_ID' in st.secrets:
        SHAREPOINT_CLIENT_ID = st.secrets.get("SHAREPOINT_CLIENT_ID", SHAREPOINT_CLIENT_ID)
        SHAREPOINT_CLIENT_SECRET = st.secrets.get("SHAREPOINT_CLIENT_SECRET", SHAREPOINT_CLIENT_SECRET)
        SHAREPOINT_TENANT_ID = st.secrets.get("SHAREPOINT_TENANT_ID", SHAREPOINT_TENANT_ID)
        SHAREPOINT_AUTHORITY = f"https://login.microsoftonline.com/{SHAREPOINT_TENANT_ID}"
        
        # Use appropriate driver format based on platform
        if os.name == 'nt':  # Windows
            DB_DRIVER = os.getenv('AZURE_DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
        else:  # Linux (including Streamlit Cloud)
            DB_DRIVER = os.getenv('AZURE_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
except Exception as e:
    st.sidebar.error(f"Error loading secrets: {str(e)}")

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
# Helper functions
def verify_password(password):
    """Verify if the provided password matches the admin password"""
    return password == ADMIN_PASSWORD

# SharePoint Helper Functions
def get_sharepoint_access_token():
    """Get access token for SharePoint using client credentials flow"""
    try:
        if not all([SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET, SHAREPOINT_TENANT_ID]):
            return None, "SharePoint credentials not configured"
            
        app = msal.ConfidentialClientApplication(
            SHAREPOINT_CLIENT_ID,
            authority=SHAREPOINT_AUTHORITY,
            client_credential=SHAREPOINT_CLIENT_SECRET,
        )
        
        result = app.acquire_token_for_client(scopes=SHAREPOINT_SCOPES)
        
        if "access_token" in result:
            return result["access_token"], None
        else:
            error_msg = result.get('error_description', 'Unknown authentication error')
            return None, f"Authentication failed: {error_msg}"
            
    except Exception as e:
        return None, f"Error getting access token: {str(e)}"

def get_shopify_orders_drive_id(token):
    """Get the drive ID for the Shopify_orders_photos library"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get('https://graph.microsoft.com/v1.0/sites/root/drives', headers=headers)
        
        if response.status_code == 200:
            drives_data = response.json()
            
            for drive in drives_data.get('value', []):
                if drive.get('name') == 'Shopify_orders_photos':
                    return drive.get('id'), None
                    
            return None, "Shopify_orders_photos library not found"
        else:
            return None, f"Failed to get drives: {response.status_code} - {response.text}"
            
    except Exception as e:
        return None, f"Error getting drive ID: {str(e)}"

def create_sharepoint_folder(token, drive_id, parent_folder_id, folder_name):
    """Create a folder in SharePoint"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        folder_data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        if parent_folder_id == "root":
            url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children'
        else:
            url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{parent_folder_id}/children'
        
        response = requests.post(url, headers=headers, json=folder_data)
        
        if response.status_code == 201:
            created_folder = response.json()
            return created_folder.get('id'), None
        else:
            return None, f"Failed to create folder: {response.status_code} - {response.text}"
            
    except Exception as e:
        return None, f"Error creating folder: {str(e)}"

def get_or_create_folder_path(token, drive_id, folder_path):
    """Get or create a folder path in SharePoint (e.g., 'CustomerName/Status/OrderID')"""
    try:
        folders = folder_path.strip('/').split('/')
        current_folder_id = "root"
        
        for folder_name in folders:
            if not folder_name:  # Skip empty folder names
                continue
                
            # Try to find existing folder first
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            if current_folder_id == "root":
                url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children'
            else:
                url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{current_folder_id}/children'
            
            response = requests.get(url, headers=headers)
            
            folder_found = False
            if response.status_code == 200:
                items = response.json().get('value', [])
                for item in items:
                    if item.get('name') == folder_name and 'folder' in item:
                        current_folder_id = item.get('id')
                        folder_found = True
                        break
            
            # Create folder if not found
            if not folder_found:
                new_folder_id, error = create_sharepoint_folder(token, drive_id, current_folder_id, folder_name)
                if error:
                    return None, f"Error creating folder '{folder_name}': {error}"
                current_folder_id = new_folder_id
        
        return current_folder_id, None
        
    except Exception as e:
        return None, f"Error creating folder path: {str(e)}"

def upload_file_to_sharepoint(token, drive_id, folder_id, file_path, file_name):
    """Upload a file to SharePoint"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
        }
        
        # Read file content
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        # Upload file
        if folder_id == "root":
            url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{file_name}:/content'
        else:
            url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}:/{file_name}:/content'
        
        response = requests.put(url, headers=headers, data=file_content)
        
        if response.status_code in [200, 201]:
            uploaded_file = response.json()
            return uploaded_file.get('webUrl'), None
        else:
            return None, f"Failed to upload file: {response.status_code} - {response.text}"
            
    except Exception as e:
        return None, f"Error uploading file: {str(e)}"

def send_email(recipient_email, subject, body, attachments=None):
    """Send email with optional attachments using Brevo SMTP"""
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add body to email
        msg.attach(MIMEText(body, 'html'))
        
        # Add attachments
        if attachments:
            for file_path in attachments:
                with open(file_path, 'rb') as file:
                    # Get the filename from the path
                    filename = os.path.basename(file_path)
                    part = MIMEApplication(file.read(), Name=filename)
                    part['Content-Disposition'] = f'attachment; filename="{filename}"'
                    msg.attach(part)
        
        # Connect to SMTP server and send email
        server = smtplib.SMTP(BREVO_SMTP_SERVER, BREVO_SMTP_PORT)
        server.starttls()
        server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        return False

# Database connection function
def get_db_connection():
    """Create a connection to the Azure SQL database with enhanced error handling"""
    try:
        conn_str = f"DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};Connection Timeout=30;"
        conn = pyodbc.connect(conn_str)
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        return conn, None
    except pyodbc.Error as e:
        error_code = e.args[0] if len(e.args) > 0 else "Unknown"
        error_message = f"Database error: {str(e)}"
        return None, error_message
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        return None, error_message

# Initialize database tables if needed
def test_database_connection():
    """Test the database connection and return status"""
    try:
        conn, error = get_db_connection()
        if error:
            return False, error
            
        # Try a simple query to verify connection
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return True, "Connected to database"
    except Exception as e:
        return False, f"Database connection error: {str(e)}"

def init_database():
    """Initialize database tables if they don't exist"""
    try:
        # Display database connection status in sidebar
        with st.sidebar:
            conn, error = get_db_connection()
            if error:
                st.error("❌ Database connection failed")
                return False
            else:
                st.success("✅ Connected to database")
            
        cursor = conn.cursor()
        
        # Check if change log table exists, create if not
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ProcoreProjectData]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[ProcoreProjectData] (
                [Id] INT IDENTITY(1,1) PRIMARY KEY,
                [ProjectNumber] NVARCHAR(50) NOT NULL UNIQUE,
                [ProjectName] NVARCHAR(255),
                [ProcorePhotoEmail] NVARCHAR(255) NOT NULL,
                [CreatedDate] DATETIME DEFAULT GETDATE()
            )
        END
        """)
        
        # Create change log table if it doesn't exist
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ChangeLog]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[ChangeLog] (
                [Id] INT IDENTITY(1,1) PRIMARY KEY,
                [Action] NVARCHAR(50) NOT NULL,
                [ProjectNumber] NVARCHAR(50) NOT NULL,
                [Details] NVARCHAR(MAX),
                [ChangeDate] DATETIME NOT NULL
            )
        END
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.sidebar.error(f"Error initializing database: {str(e)}")
        return False

# Database is the only storage mechanism - Git operations removed

# Database operations
def get_projects_from_db():
    try:
        conn, error = get_db_connection()
        if error:
            st.error(error)
            return pd.DataFrame(columns=['Project ID', 'Email ID link'])
            
        # Query the database for projects
        query = "SELECT ProjectNumber as 'Project ID', ProcorePhotoEmail as 'Email ID link' FROM dbo.ProcoreProjectData"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error reading from database: {str(e)}")
        return pd.DataFrame(columns=['Project ID', 'Email ID link'])
        
def get_all_project_ids():
    """Get all project IDs from the database for autocomplete"""
    try:
        conn, error = get_db_connection()
        if error:
            return []
            
        # Query the database for project IDs only
        query = "SELECT ProjectNumber FROM dbo.ProcoreProjectData ORDER BY ProjectNumber"
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Extract project IDs from the result
        project_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return project_ids
    except Exception as e:
        return []

def get_email_for_project(project_id):
    """Get email for a specific project ID"""
    try:
        # Add debug info to sidebar
        st.sidebar.markdown("### Email Lookup Debug")
        st.sidebar.write(f"Looking up email for Project ID: {project_id}")
        
        conn, error = get_db_connection()
        if error:
            st.error(error)
            st.sidebar.error(f"Database connection error when looking up email")
            return None
            
        cursor = conn.cursor()
        query = "SELECT ProcorePhotoEmail FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?"
        st.sidebar.write(f"Query: {query} with param: {str(project_id)}")
        
        cursor.execute(query, str(project_id))
        result = cursor.fetchone()
        
        if not result:
            st.sidebar.warning(f"No email found for Project ID: {project_id}")
            return None
            
        email = result[0]
        st.sidebar.success(f"Found email: {email}")
        conn.close()
        return email
    except Exception as e:
        st.error(f"Error getting email for project: {e}")
        st.sidebar.error(f"Exception: {str(e)}")
        return None

def add_project_to_db(project_id, email):
    """Add a new project to the database"""
    try:
        conn, error = get_db_connection()
        if error:
            return False, error
            
        cursor = conn.cursor()
        project_id_str = str(project_id)
        
        # Check if project already exists
        cursor.execute("SELECT COUNT(*) FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", project_id_str)
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.close()
            conn.close()
            return False, "Project ID already exists"
        
        # Add new project with minimal required fields
        cursor.execute("""
        INSERT INTO dbo.ProcoreProjectData 
        (ProjectNumber, ProjectName, ProcorePhotoEmail) 
        VALUES (?, ?, ?)
        """, project_id_str, f"Project {project_id_str}", email)
        
        # Log the change
        log_change("add", project_id_str, f"Added project with email: {email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Project added successfully"
    except Exception as e:
        return False, f"Error adding project: {str(e)}"

def edit_project_in_db(old_project_id, new_project_id, new_email):
    """Edit an existing project in the database"""
    try:
        conn, error = get_db_connection()
        if error:
            return False, error
            
        cursor = conn.cursor()
        old_project_id_str = str(old_project_id)
        new_project_id_str = str(new_project_id)
        
        # Check if old project exists
        cursor.execute("SELECT COUNT(*) FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", old_project_id_str)
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.close()
            conn.close()
            return False, "Project ID does not exist"
        
        # Check if new project ID already exists (unless it's the same as old)
        if old_project_id_str != new_project_id_str:
            cursor.execute("SELECT COUNT(*) FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", new_project_id_str)
            count = cursor.fetchone()[0]
            if count > 0:
                cursor.close()
                conn.close()
                return False, "New Project ID already exists"
            
            # Update the project ID and email
            cursor.execute("""
            UPDATE dbo.ProcoreProjectData 
            SET ProjectNumber = ?, ProjectName = ?, ProcorePhotoEmail = ? 
            WHERE ProjectNumber = ?
            """, new_project_id_str, f"Project {new_project_id_str}", new_email, old_project_id_str)
        else:
            # Update just the email
            cursor.execute("""
            UPDATE dbo.ProcoreProjectData 
            SET ProcorePhotoEmail = ? 
            WHERE ProjectNumber = ?
            """, new_email, old_project_id_str)
        
        # Log the change
        log_change("edit", new_project_id_str, f"Updated project from {old_project_id_str} to {new_project_id_str} with email: {new_email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Project updated successfully"
    except Exception as e:
        return False, f"Error editing project: {str(e)}"

def delete_project_from_db(project_id):
    """Delete a project from the database"""
    try:
        conn, error = get_db_connection()
        if error:
            return False, error
            
        cursor = conn.cursor()
        project_id_str = str(project_id)
        
        # Check if project exists and get email for logging
        cursor.execute("SELECT ProcorePhotoEmail FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", project_id_str)
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return False, "Project ID does not exist"
            
        email = result[0]
        
        # Delete the project
        cursor.execute("DELETE FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", project_id_str)
        
        # Log the change
        log_change("delete", project_id_str, f"Deleted project with email: {email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Project deleted successfully"
    except Exception as e:
        return False, f"Error deleting project: {str(e)}"

def bulk_import_projects(file):
    """Import multiple projects from an Excel or CSV file"""
    try:
        # Read the uploaded file
        if file.name.endswith('.csv'):
            import_df = pd.read_csv(file)
        elif file.name.endswith(('.xls', '.xlsx')):
            import_df = pd.read_excel(file)
        else:
            return False, "Unsupported file format. Please upload a CSV or Excel file."
        
        # Check if the file has the required columns
        required_columns = ['Project ID', 'Email ID link']
        if not all(col in import_df.columns for col in required_columns):
            return False, f"File must contain columns: {', '.join(required_columns)}"
        
        conn, error = get_db_connection()
        if error:
            return False, error
            
        cursor = conn.cursor()
        
        # Convert project IDs to strings
        import_df['Project ID'] = import_df['Project ID'].astype(str)
        
        # Track results
        added = 0
        skipped = 0
        
        # Process each row
        for _, row in import_df.iterrows():
            project_id = str(row['Project ID'])
            email = row['Email ID link']
            
            # Check if project already exists
            cursor.execute("SELECT COUNT(*) FROM dbo.ProcoreProjectData WHERE ProjectNumber = ?", project_id)
            count = cursor.fetchone()[0]
            
            if count > 0:
                skipped += 1
                continue
            
            # Add new project
            cursor.execute("""
            INSERT INTO dbo.ProcoreProjectData 
            (ProjectNumber, ProjectName, ProcorePhotoEmail) 
            VALUES (?, ?, ?)
            """, project_id, f"Project {project_id}", email)
            added += 1
            
            # Log the change
            log_change("add", project_id, f"Bulk import: Added project with email: {email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Import complete: {added} projects added, {skipped} skipped (already exist)"
    except Exception as e:
        return False, f"Error importing projects: {str(e)}"

def log_change(action, project_id, details):
    """Log a change to the change log table in the database"""
    try:
        timestamp = datetime.datetime.now()
        
        conn, error = get_db_connection()
        if error:
            st.error(error)
            return False
            
        cursor = conn.cursor()
        
        # Insert the log entry
        cursor.execute("""
        INSERT INTO dbo.ChangeLog (ChangeDate, Action, ProjectNumber, Details)
        VALUES (?, ?, ?, ?)
        """, timestamp, action, str(project_id), details)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        st.error(f"Error logging change: {str(e)}")
        return False

def get_change_history():
    """Get the change history from the change log table in the database"""
    try:
        conn, error = get_db_connection()
        if error:
            st.error(error)
            return pd.DataFrame(columns=['timestamp', 'action', 'project_number', 'details'])
            
        # Query the database for change history
        query = "SELECT ChangeDate as timestamp, Action as action, ProjectNumber as project_number, Details as details FROM dbo.ChangeLog ORDER BY ChangeDate DESC"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error getting change history: {str(e)}")
        return pd.DataFrame(columns=['timestamp', 'action', 'project_number', 'details'])
    
    # Database is now the source of truth for projects and change logs
    # No need to create CSV files anymore

# Shopify Database Functions
def get_shopify_order_ids():
    """Get all OrderIDs from ShopifyProjectData table for dropdown"""
    try:
        conn, error = get_db_connection()
        if error:
            return []
            
        # Query the database for OrderIDs only
        query = "SELECT DISTINCT OrderID FROM dbo.ShopifyProjectData WHERE OrderID IS NOT NULL ORDER BY OrderID"
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Extract OrderIDs from the result
        order_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return order_ids
    except Exception as e:
        st.error(f"Error getting Shopify OrderIDs: {str(e)}")
        return []

def get_shopify_customer_by_order(order_id):
    """Get CustomerName for a specific OrderID from ShopifyProjectData"""
    try:
        conn, error = get_db_connection()
        if error:
            return None
            
        cursor = conn.cursor()
        query = "SELECT CustomerName FROM dbo.ShopifyProjectData WHERE OrderID = ?"
        cursor.execute(query, str(order_id))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        return None
    except Exception as e:
        st.error(f"Error getting customer for OrderID {order_id}: {str(e)}")
        return None

def get_shopify_projects_from_db():
    """Get all Shopify projects from the database"""
    try:
        conn, error = get_db_connection()
        if error:
            st.error(error)
            return pd.DataFrame(columns=['OrderID', 'CustomerName', 'Status'])
            
        # Query the database for Shopify projects
        query = "SELECT OrderID, CustomerName, Status FROM dbo.ShopifyProjectData ORDER BY OrderID"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error retrieving Shopify projects from database: {str(e)}")
        return pd.DataFrame(columns=['OrderID', 'CustomerName', 'Status'])

# Other configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EXCEL_FILE = "project_email.xlsx"

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
# Function to test database connection with retry logic
def test_database_connection(max_retries=3, retry_delay=2):
    """Test database connection with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            conn, error = get_db_connection()
            if not error:
                conn.close()
                return True, None
            if attempt < max_retries:
                time.sleep(retry_delay)
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    return False, error

def verify_password(password):
    """Verify if the provided password matches the admin password"""
    return password == ADMIN_PASSWORD

def upload_images_tab():
    # Initialize session state variables if they don't exist
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
    # Only generate new form keys when the form is submitted successfully
    # or when the app first loads and keys don't exist
    if 'form_key_prefix' not in st.session_state or st.session_state.form_submitted:
        st.session_state.form_key_prefix = f"upload_form_{int(time.time())}"
    
    # Use the stored keys
    project_id_key = f"{st.session_state.form_key_prefix}_project_id"
    status_key = f"{st.session_state.form_key_prefix}_status"
    file_uploader_key = f"{st.session_state.form_key_prefix}_files"
    
    # Check if we need to reset the form
    if st.session_state.form_submitted:
        # Reset the flag
        st.session_state.form_submitted = False
        # Force a rerun with clean state - no message about form reset
        st.rerun()
    
    st.header("Upload Images")
    
    # Get all project IDs for autocomplete
    all_project_ids = get_all_project_ids()
    
    # Project ID input with autocomplete
    if all_project_ids:
        # Add an empty option at the beginning
        project_id_options = [""]
        project_id_options.extend(all_project_ids)
        
        # Use selectbox with autocomplete
        project_id = st.selectbox(
            "Project ID",
            options=project_id_options,
            key=project_id_key,
            placeholder="Select or type to search Project ID",
            index=0  # Default to empty option
        )
    else:
        # Fallback to regular text input if no project IDs are available
        project_id = st.text_input("Project ID", placeholder="Enter the Project ID", key=project_id_key)
    
    # Status dropdown with dynamic key
    status_options = ["", "PRODUCTION", "SHIPPED", "PICKUP", "INSTALLATION"]
    status = st.selectbox("Status", options=status_options, key=status_key, index=0)  # Default to blank option
    
    # File upload with dynamic key
    uploaded_files = st.file_uploader(
        "Upload Images", 
        accept_multiple_files=True,
        type=list(ALLOWED_EXTENSIONS),
        key=file_uploader_key
    )
    
    # Only show Send Images button if both Project ID and Status are selected (not blank)
    if project_id and status and uploaded_files:
        if st.button("Send Images"):
            recipient_email = get_email_for_project(project_id)
            
            if not recipient_email:
                st.error(f"No email found for Project ID: {project_id}")
            else:
                # Save uploaded files
                saved_files = []
                for uploaded_file in uploaded_files:
                    # Create a unique filename with status prefix
                    file_extension = os.path.splitext(uploaded_file.name)[1]
                    unique_filename = f"{status}_{uuid.uuid4()}{file_extension}"
                    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    
                    # Save the file
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    saved_files.append(file_path)
                
                # Send email with attachments
                subject = f"{status}"
                body = f"<p>{status}</p>"
                
                if send_email(recipient_email, subject, body, saved_files):
                    # Set flag to reset form on next rerun
                    st.session_state.form_submitted = True
                    st.success("Images sent successfully!")
                    
                    # Log to Slack if webhook URL is configured
                    if SLACK_WEBHOOK_URL:
                        try:
                            slack_message = {
                                "text": f"Images for Project ID: {project_id} with status '{status}' sent to {recipient_email}"
                            }
                            requests.post(SLACK_WEBHOOK_URL, json=slack_message)
                        except Exception as e:
                            st.warning(f"Could not send Slack notification: {e}")
                    
                    # Force a rerun to reset the form immediately
                    time.sleep(1)  # Give user time to see the success message
                    st.rerun()
                else:
                    st.error("Failed to send email. Please check the logs.")
                    
                    # Clean up files if email failed
                    for file_path in saved_files:
                        if os.path.exists(file_path):
                            os.remove(file_path)

def manage_projects_tab():
    st.header("Project Management")
    
    # Initialize authentication state if not already set
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    # Show password input only if not authenticated
    if not st.session_state.admin_authenticated:
        password = st.text_input("Enter admin password", type="password")
        if password:
            if verify_password(password):
                st.session_state.admin_authenticated = True
                st.rerun()  # Rerun to refresh the UI
            else:
                st.error("Incorrect password")
                return
        else:
            st.warning("Please enter the admin password to access project management")
            return
    
    # Add logout button in the sidebar
    with st.sidebar:
        if st.button("Logout from Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()
    
    # Show tabs for different management functions
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Add Project", "Edit Project", "Delete Project", "Bulk Import", "View Projects", "Change History"])
    
    with tab1:
        st.subheader("Add New Project")
        new_project_id = st.text_input("Project ID", key="new_project_id")
        new_email = st.text_input("Email", key="new_email")
        
        if st.button("Add Project"):
            if not new_project_id or not new_email:
                st.error("Please enter both Project ID and Email")
            else:
                success, message = add_project_to_db(new_project_id, new_email)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with tab2:
        st.subheader("Edit Project")
        
        # Get all projects
        projects_df = get_projects_from_db()
        
        if projects_df.empty:
            st.warning("No projects found")
        else:
            # Select project to edit
            project_options = projects_df['Project ID'].astype(str).tolist()
            selected_project = st.selectbox("Select Project", options=project_options, key="edit_select_project")
            
            # Get current email for selected project
            current_email = projects_df.loc[projects_df['Project ID'].astype(str) == selected_project, 'Email ID link'].iloc[0]
            
            # Edit form
            edited_project_id = st.text_input("Project ID", value=selected_project, key="edited_project_id_input")
            edited_email = st.text_input("Email", value=current_email, key="edited_email_input")
            
            if st.button("Update Project"):
                success, message = edit_project_in_db(selected_project, edited_project_id, edited_email)
                if success:
                    st.success(message)
                    # Force refresh to show updated data
                    st.rerun()
                else:
                    st.error(message)
    
    with tab3:
        st.subheader("Delete Project")
        
        # Get all projects
        projects_df = get_projects_from_db()
        
        if projects_df.empty:
            st.warning("No projects found")
        else:
            # Select project to delete
            project_options = projects_df['Project ID'].astype(str).tolist()
            selected_project = st.selectbox("Select Project", options=project_options, key="delete_select_project")
            
            if st.button("Delete Project", type="primary", use_container_width=True):
                # Confirm deletion
                if st.button("Confirm Deletion", key="confirm_delete", type="primary"):
                    success, message = delete_project_from_db(selected_project)
                    if success:
                        st.success(message)
                        # Force refresh to show updated data
                        st.rerun()
                    else:
                        st.error(message)
    
    with tab4:
        st.subheader("Bulk Import Projects")
        st.write("Upload a CSV or Excel file with columns: 'Project ID' and 'Email ID link'")
        
        uploaded_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"], key="bulk_import_file")
        
        if uploaded_file is not None:
            if st.button("Import Projects"):
                success, message = bulk_import_projects(uploaded_file)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with tab5:
        st.subheader("View Projects")
        
        # Get all projects from database
        projects_df = get_projects_from_db()
        
        if projects_df.empty:
            st.warning("No projects found")
        else:
            # Display projects in a table
            st.dataframe(projects_df, use_container_width=True)
            
            # Download option
            csv_data = projects_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Projects CSV",
                data=csv_data,
                file_name="projects.csv",
                mime="text/csv"
            )
    
    with tab6:
        st.subheader("Change History")
        
        # Get change history from database
        logs_df = get_change_history()
        
        if logs_df.empty:
            st.warning("No change history found")
        else:
            # Format timestamp for better display
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Display logs in a table
            st.dataframe(logs_df, use_container_width=True)
            
            # Download option
            csv_data = logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Change History CSV",
                data=csv_data,
                file_name="change_history.csv",
                mime="text/csv"
            )

# Note: view_projects_tab and view_logs_tab functions have been integrated into the manage_projects_tab function

def shopify_upload_tab():
    """Simple Shopify image upload tab"""
    st.header("Shopify Orders - Image Upload")
    
    # Get OrderIDs from database
    order_ids = get_shopify_order_ids()
    
    if not order_ids:
        st.warning("No Shopify OrderIDs found in database. Please add some OrderIDs to the ShopifyProjectData table first.")
        return
    
    # OrderID selection
    selected_order_id = st.selectbox(
        "Select OrderID",
        options=[""] + order_ids,
        index=0,
        placeholder="Choose an OrderID"
    )
    
    if selected_order_id:
        # Get customer name for selected order
        customer_name = get_shopify_customer_by_order(selected_order_id)
        
        if customer_name:
            st.info(f"Customer: **{customer_name}**")
            
            # Status selection
            status_options = ["PRODUCTION", "SHIPPED", "PICKUP", "INSTALLATION"]
            selected_status = st.selectbox(
                "Select Status",
                options=status_options,
                index=0
            )
            
            # File upload
            uploaded_files = st.file_uploader(
                "Upload Images for SharePoint",
                accept_multiple_files=True,
                type=list(ALLOWED_EXTENSIONS),
                help="Images will be uploaded to SharePoint in the folder structure: CustomerName/Status/OrderID/"
            )
            
            if uploaded_files:
                st.success(f"Ready to upload {len(uploaded_files)} image(s) to SharePoint")
                st.info(f"Folder path: **{customer_name}/{selected_status}/{selected_order_id}/**")
                
                if st.button("Upload to SharePoint", type="primary"):
                    # Implement SharePoint upload functionality
                    with st.spinner("Uploading to SharePoint..."):
                        try:
                            # Get SharePoint access token
                            access_token, error = get_sharepoint_access_token()
                            if error:
                                st.error(f"Authentication failed: {error}")
                                return
                            
                            # Get the Shopify_orders_photos drive ID
                            drive_id, error = get_shopify_orders_drive_id(access_token)
                            if error:
                                st.error(f"Failed to access SharePoint drive: {error}")
                                return
                            
                            # Create folder path: CustomerName/Status/OrderID
                            folder_path = f"{customer_name}/{selected_status}/{selected_order_id}"
                            folder_id, error = get_or_create_folder_path(access_token, drive_id, folder_path)
                            if error:
                                st.error(f"Failed to create folder structure: {error}")
                                return
                            
                            # Upload each file
                            upload_results = []
                            progress_bar = st.progress(0)
                            
                            for i, uploaded_file in enumerate(uploaded_files):
                                # Update progress
                                progress = (i + 1) / len(uploaded_files)
                                progress_bar.progress(progress)
                                
                                # Upload file to SharePoint
                                file_content = uploaded_file.getvalue()
                                success, error = upload_file_to_sharepoint(
                                    access_token, 
                                    drive_id, 
                                    folder_id, 
                                    uploaded_file.name, 
                                    file_content
                                )
                                
                                if success:
                                    upload_results.append(f"✅ {uploaded_file.name}")
                                else:
                                    upload_results.append(f"❌ {uploaded_file.name}: {error}")
                            
                            # Show results
                            progress_bar.empty()
                            
                            successful_uploads = [r for r in upload_results if r.startswith("✅")]
                            failed_uploads = [r for r in upload_results if r.startswith("❌")]
                            
                            if successful_uploads:
                                st.success(f"Successfully uploaded {len(successful_uploads)} file(s) to SharePoint!")
                                st.markdown("**Uploaded files:**")
                                for result in successful_uploads:
                                    st.markdown(f"- {result}")
                                
                                st.info(f"📁 Files saved to: `Shopify_orders_photos/{folder_path}/`")
                            
                            if failed_uploads:
                                st.error(f"Failed to upload {len(failed_uploads)} file(s):")
                                for result in failed_uploads:
                                    st.markdown(f"- {result}")
                            
                        except Exception as e:
                            st.error(f"Unexpected error during upload: {str(e)}")
                            st.exception(e)
        else:
            st.error(f"Customer not found for OrderID: {selected_order_id}")
    
    # Instructions
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("1. Select an OrderID from the dropdown")
    st.markdown("2. Choose the appropriate Status")
    st.markdown("3. Upload images that will be stored in SharePoint")
    st.markdown("4. Click 'Upload to SharePoint' to save images")
    st.markdown("\n**Note:** Images will be organized in SharePoint as: `CustomerName/Status/OrderID/[images]`")

def main():
    st.title("Project Image Upload System")
    
    # Add database status indicator in sidebar
    st.sidebar.markdown("### Database Status")
    db_status, error = test_database_connection()
    
    if db_status:
        st.sidebar.success("✅ Database connection successful")
    else:
        st.sidebar.error("❌ Database connection failed")
        st.sidebar.error(error)
    
    # Initialize application
    init_database()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Upload Images", "Manage Projects", "Shopify Orders"])
    
    with tab1:
        upload_images_tab()
    
    with tab2:
        manage_projects_tab()
    
    with tab3:
        shopify_upload_tab()

if __name__ == "__main__":
    main()
