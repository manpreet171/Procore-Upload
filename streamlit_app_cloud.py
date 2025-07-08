import streamlit as st
import os
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import shutil
import uuid
import hashlib
import requests
import json

# Set page configuration
st.set_page_config(
    page_title="Project Image Upload",
    page_icon="📷",
    layout="centered"
)

# Configuration - use secrets if available, otherwise use defaults
# For local development, you can use .streamlit/secrets.toml
# For Streamlit Cloud, set these in the Streamlit Cloud dashboard
if 'EMAIL_SENDER' in st.secrets:
    EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
    EMAIL_SENDER_NAME = st.secrets.get("EMAIL_SENDER_NAME", "Project Upload")
    # For Brevo SMTP configuration
    BREVO_SMTP_SERVER = st.secrets.get("BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
    BREVO_SMTP_PORT = st.secrets.get("BREVO_SMTP_PORT", 587)
    BREVO_SMTP_LOGIN = st.secrets.get("BREVO_SMTP_LOGIN", "919624001@smtp-brevo.com")
    BREVO_SMTP_PASSWORD = st.secrets.get("BREVO_SMTP_PASSWORD", "JVgNcDARtEBXyKYG")
    # Get admin password from secrets if available
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    # Get Slack webhook URL if available
    SLACK_WEBHOOK_URL = st.secrets.get("SLACK_WEBHOOK_URL", "")
else:
    # Fallback for local development without secrets
    try:
        import config
        EMAIL_SENDER = config.EMAIL_SENDER
        EMAIL_SENDER_NAME = getattr(config, "EMAIL_SENDER_NAME", "Project Upload")
        # For Brevo SMTP configuration
        BREVO_SMTP_SERVER = getattr(config, "BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
        BREVO_SMTP_PORT = getattr(config, "BREVO_SMTP_PORT", 587)
        BREVO_SMTP_LOGIN = getattr(config, "BREVO_SMTP_LOGIN", "919624001@smtp-brevo.com")
        BREVO_SMTP_PASSWORD = getattr(config, "BREVO_SMTP_PASSWORD", "JVgNcDARtEBXyKYG")
        # Get admin password from config if available, otherwise use default
        ADMIN_PASSWORD = getattr(config, "ADMIN_PASSWORD", "admin123")
        # Get Slack webhook URL if available
        SLACK_WEBHOOK_URL = getattr(config, "SLACK_WEBHOOK_URL", "")
    except ImportError:
        st.error("No configuration found. Please set up secrets or create a config.py file.")
        st.stop()

# Other configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EXCEL_FILE = "project_email.xlsx"

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_email_for_project(project_id):
    """Get email address for a project ID from Excel file"""
    try:
        df = pd.read_excel(EXCEL_FILE)
        
        # Try to find the project ID as a string first
        matching_row = df[df['Project ID'].astype(str) == str(project_id)]
        
        if not matching_row.empty:
            return matching_row.iloc[0]['Email ID link']
        return None
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return None

def send_email(recipient_email, subject, body, file_paths):
    """Send email with attachments using Brevo SMTP"""
    try:
        # Check if files exist and are readable
        valid_files = []
        for file_path in file_paths:
            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                valid_files.append(file_path)
            else:
                st.error(f"❌ File not accessible: {file_path}")
        
        if not valid_files:
            st.error("No valid files to attach!")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add HTML body
        msg.attach(MIMEText(f"<html><body>{body}</body></html>", 'html'))
        
        # Attach files
        total_size = 0
        for file_path in valid_files:
            try:
                with open(file_path, 'rb') as file:
                    file_content = file.read()
                    total_size += len(file_content)
                    file_name = os.path.basename(file_path)
                    attachment = MIMEApplication(file_content, _subtype=file_path.split('.')[-1])
                    attachment.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                    msg.attach(attachment)
            except Exception as e:
                st.error(f"❌ Error attaching file {file_path}: {str(e)}")
                return False
        
        # Check if email size is too large (Brevo limit is 10MB)
        if total_size > 10 * 1024 * 1024:
            st.error("❌ Email size exceeds Brevo's 10MB limit!")
            return False
        
        # Connect to server and send email
        try:
            server = smtplib.SMTP(BREVO_SMTP_SERVER, BREVO_SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
            
            text = msg.as_string()
            
            # Send the email
            send_result = server.sendmail(EMAIL_SENDER, [recipient_email], text)
            
            # Check if there were any failed recipients
            if send_result:
                st.error("❌ Failed to deliver to some recipients")
                server.quit()
                return False
                
            server.quit()
            return True
            
        except smtplib.SMTPAuthenticationError:
            st.error("❌ Authentication failed! Please check your SMTP login and password.")
            return False
        except smtplib.SMTPException as e:
            st.error(f"❌ SMTP error: {str(e)}")
            return False
            
    except Exception as e:
        st.error(f"❌ Error sending email: {str(e)}")
        return False

def add_project_to_excel(project_id, email):
    """Add a new project ID and email to the Excel file"""
    try:
        # Create the Excel file if it doesn't exist
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Project ID', 'Email ID link'])
            df.to_excel(EXCEL_FILE, index=False)
        
        # Read existing data
        df = pd.read_excel(EXCEL_FILE)
        
        # Check if project ID already exists
        if str(project_id) in df['Project ID'].astype(str).values:
            return False, "Project ID already exists"
        
        # Add new row
        new_row = pd.DataFrame({'Project ID': [project_id], 'Email ID link': [email]})
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save back to Excel
        df.to_excel(EXCEL_FILE, index=False)
        return True, "Project added successfully"
    except Exception as e:
        return False, f"Error adding project: {e}"

def verify_password(password):
    """Verify if the provided password matches the admin password"""
    # In a production environment, use a more secure password hashing method
    return password == ADMIN_PASSWORD

def upload_images_tab():
    st.header("Upload Images")
    
    # Project ID input
    project_id = st.text_input("Enter Project ID")
    
    # File uploader
    uploaded_files = st.file_uploader("Upload Images", type=["png", "jpg", "jpeg", "gif"], accept_multiple_files=True)
    
    if st.button("Upload and Send"):
        if not project_id:
            st.error("Please enter a Project ID")
        elif not uploaded_files:
            st.error("Please upload at least one image")
        else:
            # Get email for project
            recipient_email = get_email_for_project(project_id)
            
            if not recipient_email:
                st.error(f"No email found for Project ID: {project_id}")
            else:
                # Create a unique directory for this upload
                upload_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save uploaded files
                saved_files = []
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(upload_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_files.append(file_path)
                
                # Send email
                subject = f"Images for Project ID: {project_id}"
                body = f"Please find attached images for Project ID: {project_id}"
                
                if send_email(recipient_email, subject, body, saved_files):
                    # Send Slack notification if webhook URL is configured
                    if SLACK_WEBHOOK_URL:
                        try:
                            slack_message = {
                                "text": f"✅ New images uploaded for Project ID: {project_id}"
                            }
                            requests.post(SLACK_WEBHOOK_URL, json=slack_message)
                        except Exception as e:
                            st.warning(f"Could not send Slack notification: {str(e)}")
                    
                    # Show success message without revealing email
                    st.success("✅ Images sent successfully!")
                    
                    # Clean up the temporary files
                    try:
                        shutil.rmtree(upload_dir)
                    except Exception as e:
                        st.warning(f"Could not clean up temporary files: {str(e)}")
                    
                    # More reliable way to refresh the page in Streamlit
                    st.experimental_rerun()
                else:
                    # Clean up the temporary files on failure
                    try:
                        shutil.rmtree(upload_dir)
                    except:
                        pass

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
    
    # Add new project section
    st.subheader("Add New Project")
    col1, col2 = st.columns(2)
    with col1:
        new_project_id = st.text_input("Project ID", placeholder="Enter new Project ID", key="new_project_id")
    with col2:
        new_email = st.text_input("Email Address", placeholder="Enter email address", key="new_email")
    
    if st.button("Add Project"):
        if new_project_id and new_email:
            success, message = add_project_to_excel(new_project_id, new_email)
            if success:
                st.success(message)
            else:
                st.error(message)
        else:
            st.warning("Please enter both Project ID and Email Address")
    
    # Display existing projects
    st.subheader("Existing Projects")
    try:
        df = pd.read_excel(EXCEL_FILE)
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("No projects found in the Excel file")
    except Exception as e:
        if "No such file or directory" in str(e):
            st.info("No Excel file found. Add a project to create it.")
        else:
            st.error(f"Error reading Excel file: {e}")

def main():
    st.title("Project Image Upload System")
    
    # Create tabs
    tab1, tab2 = st.tabs(["Upload Images", "Manage Projects"])
    
    with tab1:
        upload_images_tab()
    
    with tab2:
        manage_projects_tab()

if __name__ == "__main__":
    main()
