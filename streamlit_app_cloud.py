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

# Set page configuration
st.set_page_config(
    page_title="Project Image Upload",
    page_icon="📷",
    layout="centered"
)

# Display logo at the top center
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.jpg", use_container_width=True, width=200)

# File paths
UPLOAD_FOLDER = "uploads"
CSV_FILE = "Procore Project Email List.csv"
CHANGE_LOG_FILE = "change_log.csv"

# Initialize with empty defaults
EMAIL_SENDER = ""
EMAIL_SENDER_NAME = "Project Upload"
BREVO_SMTP_SERVER = ""
BREVO_SMTP_PORT = 587
BREVO_SMTP_LOGIN = ""
BREVO_SMTP_PASSWORD = ""
ADMIN_PASSWORD = ""
SLACK_WEBHOOK_URL = ""

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
except Exception as e:
    st.sidebar.error(f"Error loading secrets: {str(e)}")

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
    """Get all projects from CSV file"""
    try:
        # Pull latest changes from GitHub
        git_pull()
        
        # Check if file exists, if not create it
        if not os.path.exists(CSV_FILE):
            df = pd.DataFrame(columns=['Project ID', 'Email ID link'])
            df.to_csv(CSV_FILE, index=False)
            git_commit_and_push(CSV_FILE, "Created projects CSV file")
        
        # Read CSV file
        df = pd.read_csv(CSV_FILE)
        return df
    except Exception as e:
        st.error(f"Error reading CSV file: {e}")
        return pd.DataFrame(columns=['Project ID', 'Email ID link'])

def get_email_for_project(project_id):
    """Get email for a specific project ID"""
    try:
        df = get_projects_from_csv()
        # Convert project_id to string for comparison
        project_id_str = str(project_id).strip()
        
        # Find the row with matching project ID
        matching_row = df[df['Project ID'].astype(str).str.strip() == project_id_str]
        
        if not matching_row.empty:
            return matching_row['Email ID link'].iloc[0]
        else:
            return None
    except Exception as e:
        st.error(f"Error getting email for project: {e}")
        return None

def add_project_to_csv(project_id, email):
    """Add a new project to CSV file"""
    try:
        # Get current projects
        df = get_projects_from_csv()
        
        # Check if project ID already exists
        if str(project_id) in df['Project ID'].astype(str).values:
            return False, "Project ID already exists"
        
        # Add new project
        new_row = pd.DataFrame({'Project ID': [project_id], 'Email ID link': [email]})
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save to CSV
        df.to_csv(CSV_FILE, index=False)
        
        # Log the change
        log_change("add", project_id, f"Added new project with email: {email}")
        
        # Commit and push changes
        success, message = git_commit_and_push(CSV_FILE, f"Added project {project_id}")
        if not success:
            return False, message
        
        return True, "Project added successfully"
    except Exception as e:
        return False, f"Error adding project: {e}"

def edit_project_in_csv(old_project_id, new_project_id, new_email):
    """Edit an existing project in CSV file"""
    try:
        # Get current projects
        df = get_projects_from_csv()
        
        # Check if project exists
        mask = df['Project ID'].astype(str) == str(old_project_id)
        if not mask.any():
            return False, f"Project ID {old_project_id} not found"
        
        # Check if new project ID already exists (if different from old one)
        if str(old_project_id) != str(new_project_id):
            if str(new_project_id) in df['Project ID'].astype(str).values:
                return False, f"Project ID {new_project_id} already exists"
        
        # Update project
        df.loc[mask, 'Project ID'] = new_project_id
        df.loc[mask, 'Email ID link'] = new_email
        
        # Save to CSV
        df.to_csv(CSV_FILE, index=False)
        
        # Log the change
        log_change("edit", old_project_id, f"Changed to Project ID: {new_project_id}, Email: {new_email}")
        
        # Commit and push changes
        success, message = git_commit_and_push(CSV_FILE, f"Edited project {old_project_id} to {new_project_id}")
        if not success:
            return False, message
        
        return True, "Project updated successfully"
    except Exception as e:
        return False, f"Error updating project: {e}"

def delete_project_from_csv(project_id):
    """Delete a project from CSV file"""
    try:
        # Get current projects
        df = get_projects_from_csv()
        
        # Check if project exists
        mask = df['Project ID'].astype(str) == str(project_id)
        if not mask.any():
            return False, f"Project ID {project_id} not found"
        
        # Get email before deleting (for logging)
        email = df.loc[mask, 'Email ID link'].iloc[0]
        
        # Delete project
        df = df[~mask]
        
        # Save to CSV
        df.to_csv(CSV_FILE, index=False)
        
        # Log the change
        log_change("delete", project_id, f"Deleted project with email: {email}")
        
        # Commit and push changes
        success, message = git_commit_and_push(CSV_FILE, f"Deleted project {project_id}")
        if not success:
            return False, message
        
        return True, "Project deleted successfully"
    except Exception as e:
        return False, f"Error deleting project: {e}"

def bulk_import_projects(file):
    """Import multiple projects from Excel or CSV file"""
    try:
        # Read uploaded file
        if file.name.endswith('.csv'):
            import_df = pd.read_csv(file)
        elif file.name.endswith(('.xlsx', '.xls')):
            import_df = pd.read_excel(file)
        else:
            return False, "Unsupported file format. Please upload a CSV or Excel file."
        
        # Check required columns
        required_columns = ['Project ID', 'Email ID link']
        if not all(col in import_df.columns for col in required_columns):
            return False, f"File must contain columns: {', '.join(required_columns)}"
        
        # Get current projects
        df = get_projects_from_csv()
        
        # Track import results
        added_count = 0
        skipped_count = 0
        errors = []
        
        # Process each row
        for _, row in import_df.iterrows():
            project_id = row['Project ID']
            email = row['Email ID link']
            
            # Skip empty rows
            if pd.isna(project_id) or pd.isna(email) or str(project_id).strip() == '' or str(email).strip() == '':
                skipped_count += 1
                continue
            
            # Check if project ID already exists
            if str(project_id) in df['Project ID'].astype(str).values:
                skipped_count += 1
                continue
            
            # Add new project
            new_row = pd.DataFrame({'Project ID': [project_id], 'Email ID link': [email]})
            df = pd.concat([df, new_row], ignore_index=True)
            added_count += 1
        
        # Save to CSV if any projects were added
        if added_count > 0:
            df.to_csv(CSV_FILE, index=False)
            
            # Log the change
            log_change("bulk_import", "", f"Bulk imported {added_count} projects")
            
            # Commit and push changes
            success, message = git_commit_and_push(CSV_FILE, f"Bulk imported {added_count} projects")
            if not success:
                return False, message
        
        # Return results
        result_message = f"Import complete. Added: {added_count}, Skipped: {skipped_count}"
        if errors:
            result_message += f", Errors: {len(errors)}"
        
        return True, result_message
    except Exception as e:
        return False, f"Error importing projects: {e}"

def log_change(action, project_id, details):
    """Log a change to the change log CSV file"""
    try:
        # Create change log file if it doesn't exist
        if not os.path.exists(CHANGE_LOG_FILE):
            log_df = pd.DataFrame(columns=['timestamp', 'action', 'project_id', 'details'])
            log_df.to_csv(CHANGE_LOG_FILE, index=False)
        else:
            log_df = pd.read_csv(CHANGE_LOG_FILE)
        
        # Add new log entry
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_log = pd.DataFrame({
            'timestamp': [timestamp],
            'action': [action],
            'project_id': [project_id],
            'details': [details]
        })
        
        log_df = pd.concat([new_log, log_df], ignore_index=True)
        
        # Save to CSV
        log_df.to_csv(CHANGE_LOG_FILE, index=False)
        
        # Commit and push changes
        git_commit_and_push(CHANGE_LOG_FILE, f"Logged {action} for project {project_id}")
        
        return True
    except Exception as e:
        st.error(f"Error logging change: {e}")
        return False

def get_change_history():
    """Get change history from change log CSV file"""
    try:
        # Pull latest changes from GitHub
        git_pull()
        
        # Check if file exists
        if not os.path.exists(CHANGE_LOG_FILE):
            return pd.DataFrame(columns=['timestamp', 'action', 'project_id', 'details'])
        
        # Read CSV file
        df = pd.read_csv(CHANGE_LOG_FILE)
        return df
    except Exception as e:
        st.error(f"Error getting change history: {e}")
        return pd.DataFrame(columns=['timestamp', 'action', 'project_id', 'details'])

def init_csv_files():
    """Initialize CSV files if they don't exist"""
    # Pull latest changes from GitHub
    git_pull()
    
    # Create projects CSV file if it doesn't exist
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['Project ID', 'Email ID link'])
        df.to_csv(CSV_FILE, index=False)
        git_commit_and_push(CSV_FILE, "Created projects CSV file")
    
    # Create change log CSV file if it doesn't exist
    if not os.path.exists(CHANGE_LOG_FILE):
        log_df = pd.DataFrame(columns=['timestamp', 'action', 'project_id', 'details'])
        log_df.to_csv(CHANGE_LOG_FILE, index=False)
        git_commit_and_push(CHANGE_LOG_FILE, "Created change log CSV file")

# Other configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EXCEL_FILE = "project_email.xlsx"

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
            # Get email for project
            recipient_email = get_email_for_project(project_id)
            
            if not recipient_email:
                st.error(f"No email found for Project ID: {project_id}")
            else:
                # Create a unique directory for this upload
                upload_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save uploaded files with renamed format based on status
                saved_files = []
                for i, uploaded_file in enumerate(uploaded_files, 1):
                    # Get file extension
                    _, file_extension = os.path.splitext(uploaded_file.name)
                    
                    # Create new filename with status and index
                    new_filename = f"{status}-{i}{file_extension}"
                    file_path = os.path.join(upload_dir, new_filename)
                    
                    # Save the file with new name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_files.append(file_path)
                
                # Send email
                subject = f"{status} Images"
                body = f"Please find attached {status} images."
                
                if send_email(recipient_email, subject, body, saved_files):
                    # Send Slack notification if webhook URL is configured
                    if SLACK_WEBHOOK_URL:
                        try:
                            slack_message = {
                                "text": f"New images uploaded for Project ID: {project_id}"
                            }
                            requests.post(SLACK_WEBHOOK_URL, json=slack_message)
                        except Exception as e:
                            st.warning(f"Could not send Slack notification: {str(e)}")
                    
                    # Show success message without revealing email
                    st.success("Images sent successfully!")
                    
                    # Clean up the temporary files
                    try:
                        shutil.rmtree(upload_dir)
                    except Exception as e:
                        st.warning(f"Could not clean up temporary files: {str(e)}")
                    
                    # Set the form submitted flag to trigger a complete reset on next rerun
                    st.session_state.form_submitted = True
                    
                    # Force a complete refresh
                    time.sleep(1)  # Give user time to see the success message
                    st.rerun()

def bulk_import_projects(uploaded_file):
    """Import multiple projects from an uploaded Excel or CSV file"""
    try:
        # Determine file type and read accordingly
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            return False, "Unsupported file format. Please upload a CSV or Excel file."
        
        # Check if the dataframe has the required columns
        required_columns = ['Project ID', 'Email ID link']
        if not all(col in df.columns for col in required_columns):
            return False, f"File must contain these columns: {', '.join(required_columns)}"
        
        # Track import stats
        added = 0
        skipped = 0
        errors = []
        
        # Process each row
        for _, row in df.iterrows():
            try:
                project_id = str(row['Project ID'])
                email = row['Email ID link']
                
                # Skip empty rows
                if pd.isna(project_id) or pd.isna(email) or not project_id or not email:
                    skipped += 1
                    continue
                
                # Check if project ID already exists
                if str(project_id) in get_projects_from_csv()['Project ID'].astype(str).values:
                    skipped += 1
                    continue
                
                # Add new project
                success, message = add_project_to_csv(project_id, email)
                if success:
                    added += 1
                else:
                    errors.append(message)
            except Exception as e:
                errors.append(f"Row {_ + 2}: {str(e)}")
        
        # Prepare result message
        result_message = f"Successfully added {added} projects, skipped {skipped} duplicates."
        if errors:
            result_message += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                result_message += f"\n...and {len(errors) - 10} more errors."
        
        return True, result_message
        
    except Exception as e:
        return False, f"Error importing projects: {str(e)}"

def manage_projects_tab():
    st.header("Manage Projects")
    
    # Password protection
    password_placeholder = st.empty()
    password_input = password_placeholder.text_input("Enter Admin Password", type="password")
    
    if not password_input:
        st.info("Please enter the admin password to access project management.")
        return
    
    if not verify_password(password_input):
        st.error("Incorrect password. Access denied.")
        return
    
    # If password is correct, remove the password field and show the content
    password_placeholder.empty()
    
    # Initialize session state for edit mode
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
        st.session_state.edit_project_id = ""
        st.session_state.edit_email = ""
    
    # Create tabs for different project management functions
    tab1, tab2, tab3 = st.tabs(["Add/Edit Projects", "Bulk Import", "View/Export Data"])
    
    # Tab 1: Add/Edit Projects
    with tab1:
        # Add new project section
        st.subheader("Add New Project")
        col1, col2 = st.columns(2)
        with col1:
            new_project_id = st.text_input("Project ID", placeholder="Enter new Project ID", key="new_project_id")
        with col2:
            new_email = st.text_input("Email Address", placeholder="Enter email address", key="new_email")
        
        if st.button("Add Project"):
            if new_project_id and new_email:
                success, message = add_project_to_csv(new_project_id, new_email)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("Please enter both Project ID and Email Address")
        
        # Edit and Delete section
        st.subheader("Edit or Delete Project")
        
        try:
            # Get projects from CSV
            df = get_projects_from_csv()
            
            if not df.empty:
                # Project selection for edit/delete
                project_options = [""] + df['Project ID'].astype(str).tolist()
                selected_project = st.selectbox("Select Project ID", options=project_options, key="select_project")
                
                if selected_project:
                    col1, col2 = st.columns(2)
                    
                    # Get the current email for the selected project
                    current_email = df[df['Project ID'].astype(str) == selected_project]['Email ID link'].iloc[0]
                    
                    # Edit mode
                    with col1:
                        if st.button("Edit Selected Project"):
                            st.session_state.edit_mode = True
                            st.session_state.edit_project_id = selected_project
                            st.session_state.edit_email = current_email
                            st.rerun()
                    
                    # Delete mode
                    with col2:
                        if st.button("Delete Selected Project"):
                            success, message = delete_project_from_csv(selected_project)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                # Edit form (shown only in edit mode)
                if st.session_state.edit_mode:
                    st.subheader("Edit Project")
                    col1, col2 = st.columns(2)
                    with col1:
                        edited_project_id = st.text_input("New Project ID", value=st.session_state.edit_project_id, key="edited_project_id_input")
                    with col2:
                        edited_email = st.text_input("New Email Address", value=st.session_state.edit_email, key="edited_email_input")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Save Changes"):
                            success, message = edit_project_in_csv(st.session_state.edit_project_id, edited_project_id, edited_email)
                            if success:
                                st.success(message)
                                st.session_state.edit_mode = False
                                st.rerun()
                            else:
                                st.error(message)
                    with col2:
                        if st.button("Cancel Edit"):
                            st.session_state.edit_mode = False
                            st.rerun()
            else:
                st.info("No projects found in the database")
        except Exception as e:
            if "no such table" in str(e).lower():
                st.info("No projects table found in the database. Add a project to create it.")
            else:
                st.error(f"Error reading database: {e}")
    
    # Tab 2: Bulk Import
    with tab2:
        st.subheader("Bulk Import Projects")
        
        # File upload
        st.write("Upload an Excel or CSV file with columns 'Project ID' and 'Email ID link'")
        
        # Show sample format
        with st.expander("View Sample Format"):
            sample_df = pd.DataFrame({
                'Project ID': ['123', '456', '789'],
                'Email ID link': ['email1@example.com', 'email2@example.com', 'email3@example.com']
            })
            st.dataframe(sample_df)
            
            # Sample download buttons
            col1, col2 = st.columns(2)
            with col1:
                csv = sample_df.to_csv(index=False)
                st.download_button(
                    label="Download Sample CSV",
                    data=csv,
                    file_name="sample_projects.csv",
                    mime="text/csv"
                )
            
            with col2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    sample_df.to_excel(writer, index=False)
                excel_data = buffer.getvalue()
                st.download_button(
                    label="Download Sample Excel",
                    data=excel_data,
                    file_name="sample_projects.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        uploaded_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])
        
        if uploaded_file is not None:
            # Preview the uploaded file
            st.subheader("File Preview")
            
            if uploaded_file.name.endswith('.csv'):
                df_preview = pd.read_csv(uploaded_file)
                uploaded_file.seek(0)  # Reset file pointer after reading
            else:  # Excel file
                df_preview = pd.read_excel(uploaded_file)
                uploaded_file.seek(0)  # Reset file pointer after reading
            
            st.dataframe(df_preview.head(5))
            
            # Import button
            if st.button("Import Projects"):
                success, message = bulk_import_projects(uploaded_file)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    # Tab 3: View/Export Data
    with tab3:
        st.subheader("View All Projects")
        
        try:
            # Get projects from CSV
            df = get_projects_from_csv()
            
            if not df.empty:
                # Display the dataframe
                st.dataframe(df)
                
                # Add download buttons
                st.subheader("Download Project Data")
                col1, col2 = st.columns(2)
                
                # Convert dataframe to CSV
                csv = df.to_csv(index=False)
                with col1:
                    st.download_button(
                        label="Download as CSV",
                        data=csv,
                        file_name="project_data.csv",
                        mime="text/csv"
                    )
                
                # Convert dataframe to Excel
                with col2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    excel_data = buffer.getvalue()
                    st.download_button(
                        label="Download as Excel",
                        data=excel_data,
                        file_name="project_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                # View change history
                st.subheader("Change History")
                if st.button("Show Change History"):
                    try:
                        df = get_change_history()
                        if not df.empty:
                            st.dataframe(df)
                        else:
                            st.info("No change history found")
                    except Exception as e:
                        st.error(f"Error retrieving change history: {e}")
            else:
                st.info("No projects found in the database")
        except Exception as e:
            if "no such table" in str(e).lower():
                st.info("No projects table found in the database. Add a project to create it.")
            else:
                st.error(f"Error reading database: {e}")

def init_csv_files():
    """Initialize CSV files if they don't exist"""
    # Pull latest changes from GitHub
    git_pull()
    
    # Create projects CSV file if it doesn't exist
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['Project ID', 'Email ID link'])
        df.to_csv(CSV_FILE, index=False)
        git_commit_and_push(CSV_FILE, "Created projects CSV file")
    
    # Create change log CSV file if it doesn't exist
    if not os.path.exists(CHANGE_LOG_FILE):
        log_df = pd.DataFrame(columns=['timestamp', 'action', 'project_id', 'details'])
        log_df.to_csv(CHANGE_LOG_FILE, index=False)
        git_commit_and_push(CHANGE_LOG_FILE, "Created change log CSV file")

# Other configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EXCEL_FILE = "project_email.xlsx"

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def main():
    st.title("Project Image Upload System")
    
    # Initialize CSV files
    init_csv_files()
    
    # Create tabs
    tab1, tab2 = st.tabs(["Upload Images", "Manage Projects"])
    
    with tab1:
        upload_images_tab()
    
    with tab2:
        manage_projects_tab()

if __name__ == "__main__":
    main()
