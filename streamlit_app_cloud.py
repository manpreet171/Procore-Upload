import os
import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import time
import io
import git
import datetime
import requests
import shutil
import uuid
import tempfile
import subprocess
from PIL import Image
import pyodbc
import urllib.parse

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
DB_DRIVER = "{ODBC Driver 17 for SQL Server}"

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
    else:
        # Use environment variables as fallback
        DB_SERVER = os.getenv('AZURE_DB_SERVER', 'dw-sqlsvr.database.windows.net')
        DB_NAME = os.getenv('AZURE_DB_NAME', 'dw-sqldb')
        DB_USERNAME = os.getenv('AZURE_DB_USERNAME', 'manpreet')
        DB_PASSWORD = os.getenv('AZURE_DB_PASSWORD', 'KYqPn@!)')
        DB_DRIVER = os.getenv('AZURE_DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
except Exception as e:
    st.sidebar.error(f"Error loading secrets: {str(e)}")

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database connection function
def get_db_connection():
    """Create a connection to the Azure SQL database with enhanced error handling"""
    try:
        # Create connection string with connection timeout and connection pooling
        params = urllib.parse.quote_plus(f"DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};Connection Timeout=30;")
        conn_str = f"DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};Connection Timeout=30;"
        
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        
        # Set connection properties for better performance
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        
        return conn, None
    except pyodbc.Error as e:
        error_code = e.args[0] if len(e.args) > 0 else "Unknown"
        error_message = f"Database connection error [{error_code}]: {str(e)}"
        st.sidebar.error(error_message)
        return None, error_message
    except Exception as e:
        error_message = f"Unexpected database error: {str(e)}"
        st.sidebar.error(error_message)
        return None, error_message

# Initialize database tables if needed
def init_database():
    """Initialize database tables if they don't exist"""
    try:
        # Display database connection status in sidebar
        with st.sidebar:
            with st.spinner("Connecting to database..."):
                conn, error = get_db_connection()
                if error:
                    st.error("❌ Database connection failed")
                    st.error(error)
                    return False
                else:
                    st.success("✅ Connected to Azure SQL Database")
            
        cursor = conn.cursor()
        
        # Check if change log table exists, create if not
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ProcoreChangeLog')
        BEGIN
            CREATE TABLE ProcoreChangeLog (
                id INT IDENTITY(1,1) PRIMARY KEY,
                timestamp DATETIME,
                action VARCHAR(50),
                project_number VARCHAR(50),
                details VARCHAR(MAX)
            )
        END
        """)
        
        # Verify that ProcoreProjectData table exists
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ProcoreProjectData')
        BEGIN
            SELECT 'ProcoreProjectData table does not exist. Please create it with the required schema.' AS Warning
        END
        """)
        
        result = cursor.fetchone()
        if result:
            st.sidebar.warning(result[0])
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.sidebar.error(f"Error initializing database: {str(e)}")
        return False

# Git operations
def setup_github_auth():
    """Setup GitHub authentication using token from secrets"""
    try:
        # Check if we're in a git repository
        repo = git.Repo('.')
        
        # Configure Git user
        if 'GITHUB_USERNAME' in st.secrets and 'GITHUB_EMAIL' in st.secrets:
            repo.git.config('user.name', st.secrets['GITHUB_USERNAME'])
            repo.git.config('user.email', st.secrets['GITHUB_EMAIL'])
        
        # Set up HTTPS authentication with token
        if 'GITHUB_TOKEN' in st.secrets and 'GITHUB_USERNAME' in st.secrets:
            username = st.secrets['GITHUB_USERNAME']
            token = st.secrets['GITHUB_TOKEN']
            repo_name = st.secrets.get('GITHUB_REPO', 'Procore-Upload')
            
            # Set the remote URL with token authentication
            new_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
            
            # Check if remote exists
            try:
                remote_url = repo.git.remote('get-url', 'origin')
                # Update existing remote
                repo.git.remote('set-url', 'origin', new_url)
            except git.GitCommandError:
                # Remote doesn't exist, add it
                repo.git.remote('add', 'origin', new_url)
        
        return True, "GitHub authentication set up successfully"
    except Exception as e:
        return False, f"Error setting up GitHub authentication: {e}"

def git_pull():
    """Pull latest changes from GitHub repository"""
    try:
        # Set up GitHub authentication
        setup_github_auth()
        
        # Pull changes
        repo = git.Repo('.')
        try:
            repo.git.pull('origin', 'main')
        except git.GitCommandError:
            try:
                repo.git.pull('origin', 'master')
            except git.GitCommandError:
                pass  # Ignore if both fail
        
        return True, "Successfully pulled latest changes"
    except Exception as e:
        return False, f"Error pulling from GitHub: {e}"

def git_commit_and_push(file_path, commit_message):
    """Commit and push changes to GitHub repository"""
    try:
        # Set up GitHub authentication
        setup_github_auth()
        
        repo = git.Repo('.')
        
        # Add and commit
        repo.git.add(file_path)
        
        # Check if there are changes to commit
        if not repo.git.diff('--staged'):
            return True, "No changes to commit"
            
        repo.git.commit('-m', commit_message)
        
        # Try to push to main branch first, then master if that fails
        try:
            repo.git.push('origin', 'main')
        except git.GitCommandError:
            try:
                repo.git.push('origin', 'master')
            except git.GitCommandError:
                # If both fail, try to push to current branch
                current_branch = repo.active_branch.name
                try:
                    repo.git.push('origin', current_branch)
                except git.GitCommandError as e:
                    st.warning(f"Changes committed locally but not pushed to GitHub: {e}")
                    return True, "Changes saved locally (not pushed to GitHub)"
        
        return True, "Successfully pushed changes to GitHub"
    except Exception as e:
        return False, f"Error with Git operations: {e}"

# CSV operations
def get_projects_from_csv():
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
            SET ProjectNumber = ?, ProcorePhotoEmail = ? 
            WHERE ProjectNumber = ?
            """, new_project_id_str, new_email, old_project_id_str)
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
        INSERT INTO ProcoreChangeLog (timestamp, action, project_number, details)
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
        query = "SELECT timestamp, action, project_number, details FROM ProcoreChangeLog ORDER BY timestamp DESC"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error getting change history: {str(e)}")
        return pd.DataFrame(columns=['timestamp', 'action', 'project_number', 'details'])
    
    # Database is now the source of truth for projects and change logs
    # No need to create CSV files anymore

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

def send_email(recipient_email, subject, body, file_paths):
    """Send email with attachments using Brevo SMTP"""
    
    # Initialize email log in session state if it doesn't exist
    if 'email_log' not in st.session_state:
        st.session_state.email_log = []
    
    # Function to add log entries
    def log_entry(level, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state.email_log.append({"time": timestamp, "level": level, "message": message})
    
    try:
        # Clear previous logs if this is a new email attempt
        if len(st.session_state.email_log) > 20:  # Keep logs manageable
            st.session_state.email_log = []
        
        # Log email configuration
        log_entry("info", f"Starting email to: {recipient_email}")
        log_entry("info", f"SMTP Server: {BREVO_SMTP_SERVER}:{BREVO_SMTP_PORT}")
        log_entry("info", f"From: {EMAIL_SENDER}")
        
        # Check if files exist and are readable
        valid_files = []
        for file_path in file_paths:
            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                valid_files.append(file_path)
                log_entry("success", f"File valid: {os.path.basename(file_path)}")
            else:
                log_entry("error", f"File not accessible: {file_path}")
                st.error(f" File not accessible: {file_path}")
        
        if not valid_files:
            log_entry("error", "No valid files to attach!")
            st.error("No valid files to attach!")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"  # Fixed format
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add HTML body
        msg.attach(MIMEText(f"<html><body>{body}</body></html>", 'html'))
        log_entry("success", "Email body attached")
        
        # Attach files
        total_size = 0
        for file_path in valid_files:
            try:
                with open(file_path, 'rb') as file:
                    file_content = file.read()
                    total_size += len(file_content)
                    file_name = os.path.basename(file_path)
                    
                    # Get the correct file extension and MIME subtype
                    file_extension = os.path.splitext(file_path)[1].lower().lstrip('.')
                    
                    # Map common image extensions to MIME subtypes
                    mime_subtypes = {
                        'jpg': 'jpeg',
                        'jpeg': 'jpeg',
                        'png': 'png',
                        'gif': 'gif'
                    }
                    subtype = mime_subtypes.get(file_extension, 'octet-stream')
                    
                    attachment = MIMEApplication(file_content, _subtype=subtype)
                    attachment.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                    msg.attach(attachment)
                    
                    # Log attachment
                    log_entry("success", f"Attached: {file_name} ({len(file_content)/1024:.1f} KB, type: {subtype})")
            except Exception as e:
                log_entry("error", f"Error attaching file {file_path}: {str(e)}")
                st.error(f" Error attaching file {file_path}: {str(e)}")
                return False
        
        # Check if email size is too large (Brevo limit is 10MB)
        log_entry("info", f"Total email size: {total_size/1024/1024:.2f} MB")
        if total_size > 10 * 1024 * 1024:
            log_entry("error", f"Email size exceeds Brevo's 10MB limit! ({total_size/1024/1024:.2f} MB)")
            st.error(" Email size exceeds Brevo's 10MB limit!")
            return False
        
        # Connect to server and send email
        try:
            log_entry("info", "Connecting to SMTP server...")
            server = smtplib.SMTP(BREVO_SMTP_SERVER, BREVO_SMTP_PORT)
            log_entry("info", "Connected to SMTP server")
            
            log_entry("info", "Starting TLS...")
            server.ehlo()
            server.starttls()
            log_entry("info", "TLS started")
            
            log_entry("info", "Logging in...")
            server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
            log_entry("success", "Login successful")
            
            text = msg.as_string()
            
            # Send the email
            log_entry("info", f"Sending email to {recipient_email}...")
            send_result = server.sendmail(EMAIL_SENDER, [recipient_email], text)
            
            # Check if there were any failed recipients
            if send_result:
                log_entry("error", f"Failed to deliver to some recipients: {send_result}")
                st.error(" Failed to deliver to some recipients")
                server.quit()
                return False
            
            log_entry("success", "Email sent successfully!")
            server.quit()
            return True
            
        except smtplib.SMTPAuthenticationError as auth_error:
            log_entry("error", f"Authentication failed: {auth_error}")
            st.error(" Authentication failed! Please check your SMTP login and password.")
            return False
        except smtplib.SMTPException as smtp_error:
            log_entry("error", f"SMTP error: {smtp_error}")
            st.error(f" SMTP error: {str(smtp_error)}")
            return False
        except Exception as e:
            log_entry("error", f"Unexpected error during email sending: {e}")
            st.error(f" Error sending email: {str(e)}")
            return False
            
    except Exception as e:
        log_entry("error", f"General error in send_email function: {e}")
        st.error(f" Error sending email: {str(e)}")
        return False

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
        # Show a temporary success message
        st.success("Images sent successfully! Form has been reset.")
        # Force a rerun with clean state
        time.sleep(1.5)  # Give user time to see the message
        st.rerun()
    
    st.header("Upload Images")
    
    # Project ID input with dynamic key
    project_id = st.text_input("Project ID", placeholder="Enter the Project ID", key=project_id_key)
    
    # Status dropdown with dynamic key
    status_options = ["PRODUCTION", "SHIPPED", "PICKUP", "INSTALLATION"]
    status = st.selectbox("Status", options=status_options, key=status_key)
    
    # File upload with dynamic key
    uploaded_files = st.file_uploader(
        "Upload Images", 
        accept_multiple_files=True,
        type=list(ALLOWED_EXTENSIONS),
        key=file_uploader_key
    )
    
    if uploaded_files and project_id:
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
                else:
                    st.error("Failed to send email. Please check the logs.")
                    
                    # Clean up files if email failed
                    for file_path in saved_files:
                        if os.path.exists(file_path):
                            os.remove(file_path)

def manage_projects_tab():
    st.header("Project Management")
    
    # Password protection
    password = st.text_input("Enter admin password", type="password")
    if not password:
        st.warning("Please enter the admin password to access project management")
        return
    
    if not verify_password(password):
        st.error("Incorrect password")
        return
    
    # Show tabs for different management functions
    tab1, tab2, tab3, tab4 = st.tabs(["Add Project", "Edit Project", "Delete Project", "Bulk Import"])
    
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

def view_projects_tab():
    st.header("View Projects")
    
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

def view_logs_tab():
    st.header("Change History")
    
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
    tab1, tab2, tab3, tab4 = st.tabs(["Upload Images", "Manage Projects", "View Projects", "Change History"])
    
    with tab1:
        upload_images_tab()
    
    with tab2:
        manage_projects_tab()
        
    with tab3:
        view_projects_tab()
        
    with tab4:
        view_logs_tab()

if __name__ == "__main__":
    main()
