from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import pandas as pd
from werkzeug.utils import secure_filename
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json

# Import configuration
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Set configuration from config file
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Create uploads folder if it doesn't exist
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def get_google_drive_service():
    """Get or create Google Drive API service"""
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = None
    
    # Load credentials from token.json if it exists
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_info(json.load(open(config.GOOGLE_TOKEN_FILE)))
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, 
                SCOPES,
                redirect_uri='http://localhost:5000/oauth2callback'
            )
            creds = flow.run_local_server(port=5000)
        
        # Save credentials for future use
        with open(config.GOOGLE_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    # Build and return the Drive API service
    return build('drive', 'v3', credentials=creds)

def create_folder_if_not_exists(service, folder_name):
    """Create a folder in Google Drive if it doesn't exist and return its ID"""
    # Check if folder already exists
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    folders = results.get('files', [])
    
    if folders:
        # Folder exists, return its ID
        return folders[0]['id']
    else:
        # Create the folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(service, file_path, folder_id):
    """Upload a file to a specific Google Drive folder"""
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
    
    return file.get('id')

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
        print(f"Error reading Excel file: {e}")
        return None

def send_email_with_images(receiver_email, subject, body, image_paths):
    """Send email with multiple image attachments"""
    message = MIMEMultipart()
    message["From"] = config.EMAIL_SENDER
    message["To"] = receiver_email
    message["Subject"] = subject
    
    # Add body to email
    message.attach(MIMEText(body, "plain"))
    
    # Add images to email
    for image_path in image_paths:
        with open(image_path, "rb") as image_file:
            image = MIMEImage(image_file.read())
            image_name = os.path.basename(image_path)
            image.add_header('Content-Disposition', f'attachment; filename="{image_name}"')
            message.attach(image)
    
    # Connect to SMTP server
    server = smtplib.SMTP(config.EMAIL_SMTP_SERVER, config.EMAIL_SMTP_PORT)
    server.starttls()
    
    try:
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.send_message(message)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
    finally:
        server.quit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files part'}), 400
    
    project_id = request.form.get('projectId')
    if not project_id:
        return jsonify({'error': 'No project ID provided'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    # Get email for project ID
    email = get_email_for_project(project_id)
    if not email:
        return jsonify({'error': f'No email found for Project ID: {project_id}'}), 400
    
    uploaded_files = []
    
    try:
        # Get Google Drive service
        drive_service = get_google_drive_service()
        
        # Create or get folder ID
        folder_id = create_folder_if_not_exists(drive_service, project_id)
        
        # Save files locally and upload to Drive
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                uploaded_files.append(file_path)
                
                # Upload to Google Drive
                upload_to_drive(drive_service, file_path, folder_id)
        
        # Send email with images
        email_sent = send_email_with_images(
            receiver_email=email,
            subject=f"Images for Project {project_id}",
            body=f"Please find attached the images for Project {project_id}.",
            image_paths=uploaded_files
        )
        
        if email_sent:
            # Clean up local files after sending
            for file_path in uploaded_files:
                os.remove(file_path)
            
            return jsonify({'success': True, 'message': f'Files uploaded to Drive and sent to {email}'}), 200
        else:
            return jsonify({'error': 'Failed to send email'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Make sure no other application is using port 8080
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 8080))
        s.close()
        app.run(debug=True, port=8080)
    except socket.error:
        print("Port 8080 is in use. Please close any application using this port and try again.")
        print("Alternatively, update your Google Cloud Console redirect URI to use a different port.")
