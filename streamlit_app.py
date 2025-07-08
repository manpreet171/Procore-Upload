import streamlit as st
import os
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import shutil
import config
from pathlib import Path
import time
import uuid

# Set page configuration
st.set_page_config(
    page_title="Project Image Upload",
    page_icon="📷",
    layout="centered"
)

# Create uploads directory if it doesn't exist
if not os.path.exists(config.UPLOAD_FOLDER):
    os.makedirs(config.UPLOAD_FOLDER)

# Define Google Drive scope
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_google_drive_service():
    """Get or create Google Drive API service"""
    creds = None
    
    # Load credentials from token.json if it exists
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_info(json.load(open(config.GOOGLE_TOKEN_FILE)))
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            st.warning("You need to authenticate with Google Drive.")
            auth_url, _ = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE,
                SCOPES
            ).authorization_url(prompt='consent')
            
            st.markdown(f"""
            ### Google Authentication Required
            1. Click the link below to authenticate with Google:
            2. [Click here to authenticate with Google]({auth_url})
            3. After authentication, you'll get a code. Copy that code.
            4. Paste the code in the text box below and click "Submit Code".
            """)
            
            auth_code = st.text_input("Enter the authorization code:", type="password")
            if st.button("Submit Code"):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        config.GOOGLE_CREDENTIALS_FILE,
                        SCOPES
                    )
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    # Save credentials for future use
                    with open(config.GOOGLE_TOKEN_FILE, 'w') as token:
                        token.write(creds.to_json())
                    
                    st.success("Authentication successful! Please refresh the page.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
            
            st.stop()
    
    # Build and return the Drive API service
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, project_id):
    """Upload a file to Google Drive in a folder named after the project ID"""
    try:
        service = get_google_drive_service()
        
        # Check if project folder exists, create if not
        folder_name = str(project_id)
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = results.get('files', [])
        
        if not folders:
            # Create folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
        else:
            folder_id = folders[0].get('id')
        
        # Upload file to the folder
        file_name = os.path.basename(file_path)
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        return file_id
    except Exception as e:
        st.error(f"Error uploading to Google Drive: {e}")
        return None

def get_email_for_project(project_id):
    """Get email address for a project ID from Excel file"""
    try:
        df = pd.read_excel(config.EXCEL_FILE)
        
        # Try to find the project ID as a string first
        matching_row = df[df['Project ID'].astype(str) == str(project_id)]
        
        if not matching_row.empty:
            return matching_row.iloc[0]['Email ID link']
        return None
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return None

def send_email(recipient_email, subject, body, file_paths):
    """Send email with attachments"""
    try:
        msg = MIMEMultipart()
        msg['From'] = config.EMAIL_SENDER
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach files
        for file_path in file_paths:
            with open(file_path, 'rb') as file:
                file_name = os.path.basename(file_path)
                attachment = MIMEApplication(file.read(), _subtype=file_path.split('.')[-1])
                attachment.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                msg.attach(attachment)
        
        # Connect to server and send email
        server = smtplib.SMTP(config.EMAIL_SMTP_SERVER, config.EMAIL_SMTP_PORT)
        server.starttls()
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(config.EMAIL_SENDER, recipient_email, text)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def main():
    st.title("Project Image Upload")
    
    # Project ID input
    project_id = st.text_input("Project ID", placeholder="Enter the Project ID")
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload Images", 
        accept_multiple_files=True,
        type=list(config.ALLOWED_EXTENSIONS)
    )
    
    if uploaded_files and project_id:
        if st.button("Process Images"):
            with st.spinner("Processing images..."):
                # Create a temporary directory for this upload
                temp_dir = os.path.join(config.UPLOAD_FOLDER, str(uuid.uuid4()))
                os.makedirs(temp_dir, exist_ok=True)
                
                # Save uploaded files to temp directory
                saved_files = []
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_files.append(file_path)
                
                # Get email for project
                email = get_email_for_project(project_id)
                
                if not email:
                    st.error(f"No email found for Project ID: {project_id}")
                    # Clean up temp files
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return
                
                # Upload files to Google Drive
                drive_file_ids = []
                for file_path in saved_files:
                    file_id = upload_to_drive(file_path, project_id)
                    if file_id:
                        drive_file_ids.append(file_id)
                
                # Send email with attachments
                if drive_file_ids:
                    subject = f"Images for Project ID: {project_id}"
                    body = f"Please find attached images for Project ID: {project_id}"
                    
                    email_sent = send_email(email, subject, body, saved_files)
                    
                    if email_sent:
                        st.success(f"Files uploaded to Drive and sent to {email}")
                    else:
                        st.error("Failed to send email")
                else:
                    st.error("Failed to upload files to Google Drive")
                
                # Clean up temp files
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Display information
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("1. Enter the Project ID")
    st.markdown("2. Upload one or more images (JPG, PNG, GIF)")
    st.markdown("3. Click 'Process Images' to upload to Google Drive and send via email")
    
    # Show example project IDs from Excel file
    try:
        df = pd.read_excel(config.EXCEL_FILE)
        st.markdown("---")
        st.markdown("### Available Project IDs")
        st.dataframe(df[['Project ID', 'Email ID link']])
    except Exception as e:
        st.warning(f"Could not load example Project IDs: {e}")

if __name__ == "__main__":
    main()
