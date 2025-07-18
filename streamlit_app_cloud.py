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
import math

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
@st.cache_data(ttl=3300)  # Cache for 55 minutes (tokens usually last 60 minutes)
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

@st.cache_data(ttl=86400)  # Cache for 24 hours as drive IDs rarely change
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

@st.cache_data(ttl=3600)  # Cache folder paths for 1 hour
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
    """Upload a file to SharePoint from file path"""
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

def upload_file_content_to_sharepoint(token, drive_id, folder_id, file_name, file_content):
    """Upload file content directly to SharePoint"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
        }
        
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

# Image optimization function
def optimize_image(image_content, max_size_kb=500, quality=85):
    """Optimize image to reduce file size while maintaining reasonable quality"""
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_content))
        
        # Initial quality setting
        current_quality = quality
        output = io.BytesIO()
        
        # Save as JPEG with quality setting
        if img.mode in ('RGBA', 'LA'):
            # Convert transparent images to RGB with white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
            img = background
        
        # First attempt at compression
        img.save(output, format='JPEG', quality=current_quality, optimize=True)
        
        # Check if size is still too large and reduce quality if needed
        while output.tell() > max_size_kb * 1024 and current_quality > 30:
            output = io.BytesIO()
            current_quality -= 10
            img.save(output, format='JPEG', quality=current_quality, optimize=True)
        
        # If still too large, resize the image
        if output.tell() > max_size_kb * 1024:
            # Calculate new dimensions to maintain aspect ratio
            ratio = math.sqrt(max_size_kb * 1024 / output.tell())
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Try saving again
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=current_quality, optimize=True)
        
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        # If optimization fails, return original content
        return image_content

# Database connection function
# Database connection pool for reuse
DB_CONNECTION_POOL = None

def get_db_connection():
    """Create a connection to the Azure SQL database with connection pooling"""
    try:
        global DB_CONNECTION_POOL
        
        # If we already have a connection in the pool that's still valid, return it
        if DB_CONNECTION_POOL is not None:
            try:
                # Test if connection is still valid with a simple query
                cursor = DB_CONNECTION_POOL.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return DB_CONNECTION_POOL, None
            except Exception:
                # Connection is no longer valid, create a new one
                try:
                    DB_CONNECTION_POOL.close()
                except:
                    pass
                DB_CONNECTION_POOL = None
        
        # Create a new connection
        conn_str = f"DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};Connection Timeout=30;"
        conn = pyodbc.connect(conn_str)
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        
        # Store in pool for future use
        DB_CONNECTION_POOL = conn
        
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
        
@st.cache_data(ttl=300)  # Cache for 5 minutes
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
            log_change("add", project_id, f"Added project with email: {email} (bulk import)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Import complete: {added} projects added, {skipped} skipped (already exist)"
    except Exception as e:
        return False, f"Error importing projects: {str(e)}"

def log_change(action, project_id, details):
    """Log a change to the change log table in the database"""
    try:
        conn, error = get_db_connection()
        if error:
            st.error(error)
            return False
            
        cursor = conn.cursor()
        now = datetime.datetime.now()
        
        try:
            # Insert into change log
            cursor.execute("""
            INSERT INTO dbo.ChangeLog 
            (Action, ProjectNumber, Details, ChangeDate) 
            VALUES (?, ?, ?, ?)
            """, action, str(project_id), details, now)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            st.error(f"Error logging change: {str(e)}")
            return False
    except Exception as e:
        st.error(f"Error preparing database connection: {str(e)}")
        return False

def shopify_upload_tab():
    """Tab for uploading images to SharePoint for Shopify orders"""
    # Initialize session state variables if they don't exist
    if 'shopify_form_submitted' not in st.session_state:
        st.session_state.shopify_form_submitted = False
    
    # Only generate new form keys when the form is submitted successfully
    # or when the app first loads and keys don't exist
    if 'shopify_form_key_prefix' not in st.session_state or st.session_state.shopify_form_submitted:
        st.session_state.shopify_form_key_prefix = f"shopify_upload_form_{int(time.time())}"
    
    # Use the stored keys
    order_id_key = f"{st.session_state.shopify_form_key_prefix}_order_id"
    status_key = f"{st.session_state.shopify_form_key_prefix}_status"
    file_uploader_key = f"{st.session_state.shopify_form_key_prefix}_files"
    
    # Check if we need to reset the form
    if st.session_state.shopify_form_submitted:
        # Reset the flag
        st.session_state.shopify_form_submitted = False
        # Force a rerun with clean state - no message about form reset
        st.rerun()
    
    st.header("Upload Shopify Order Images")
    st.markdown("Upload images for Shopify orders to SharePoint")
    
    # Get all order IDs for autocomplete
    all_order_ids = get_shopify_order_ids()
    
    # Order ID input with autocomplete
    if all_order_ids:
        # Add an empty option at the beginning
        order_id_options = [""]
        order_id_options.extend(all_order_ids)
        
        # Use selectbox with autocomplete
        order_id = st.selectbox(
            "Order ID",
            options=order_id_options,
            key=order_id_key,
            placeholder="Select or type to search Order ID",
            index=0  # Default to empty option
        )
    else:
        # Fallback to regular text input if no order IDs are available
        order_id = st.text_input("Order ID", placeholder="Enter the Order ID", key=order_id_key)
    
    # Show customer name if order ID is selected
    customer_name = ""
    if order_id:
        customer_name = get_shopify_customer_by_order(order_id)
        if customer_name:
            st.info(f"Customer: {customer_name}")
        else:
            st.warning("No customer found for this Order ID")
    
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
    
    # Show folder path preview
    if customer_name and status and order_id:
        folder_path = f"{customer_name}/{status}/{order_id}"
        st.success(f"Files will be uploaded to: {folder_path}")
    
    # Only show Upload button if all required fields are filled
    if order_id and status and customer_name and uploaded_files:
        if st.button("Upload to SharePoint"):
            with st.spinner("Authenticating with SharePoint..."):
                # Get SharePoint access token
                token, error = get_sharepoint_access_token()
                if error:
                    st.error(f"Authentication failed: {error}")
                else:
                    # Get drive ID
                    drive_id, error = get_shopify_orders_drive_id(token)
                    if error:
                        st.error(f"Error getting drive ID: {error}")
                    else:
                        # Create folder path
                        folder_path = f"{customer_name}/{status}/{order_id}"
                        folder_id, error = get_or_create_folder_path(token, drive_id, folder_path)
                        
                        if error:
                            st.error(f"Error creating folder path: {error}")
                        else:
                            # Upload files
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            total_files = len(uploaded_files)
                            successful_uploads = 0
                            failed_uploads = 0
                            
                            for i, uploaded_file in enumerate(uploaded_files):
                                file_name = uploaded_file.name
                                status_text.text(f"Uploading {file_name}... ({i+1}/{total_files})")
                                
                                try:
                                    # Get file content
                                    file_content = uploaded_file.getbuffer()
                                    
                                    # Optimize image if it's an image file (not PDF)
                                    file_extension = os.path.splitext(file_name)[1].lower()
                                    if file_extension not in ['.pdf']:
                                        try:
                                            # Optimize the image to reduce size
                                            file_content = optimize_image(file_content, max_size_kb=500)
                                        except Exception as e:
                                            # If optimization fails, use original content
                                            st.warning(f"Could not optimize {file_name}: {str(e)}")
                                    
                                    # Upload to SharePoint
                                    file_url, error = upload_file_content_to_sharepoint(
                                        token, drive_id, folder_id, file_name, file_content
                                    )
                                    
                                    if error:
                                        st.error(f"Error uploading {file_name}: {error}")
                                        failed_uploads += 1
                                    else:
                                        successful_uploads += 1
                                        
                                except Exception as e:
                                    st.error(f"Exception uploading {file_name}: {str(e)}")
                                    failed_uploads += 1
                                
                                # Update progress
                                progress_bar.progress((i + 1) / total_files)
                            
                            # Show final status
                            if successful_uploads == total_files:
                                st.success(f"All {total_files} files uploaded successfully to {folder_path}!")
                                # Set flag to reset form on next rerun
                                st.session_state.shopify_form_submitted = True
                                # Force a rerun to reset the form after a delay
                                time.sleep(2)  # Give user time to see the success message
                                st.rerun()
                            else:
                                st.warning(f"Uploaded {successful_uploads} files, {failed_uploads} failed.")

def main():
    """Main function to run the Streamlit app"""
    # Initialize database if needed
    init_database()
    
    # Create tabs for different functions
    tab1, tab2 = st.tabs(["Procore Projects", "Shopify Orders"])
    
    with tab1:
        upload_images_tab()
    
    with tab2:
        shopify_upload_tab()

if __name__ == "__main__":
    main()
