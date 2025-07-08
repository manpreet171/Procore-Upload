"""
Configuration file for the Project Image Upload Application.
This file contains all the sensitive information and configuration settings.
"""

# Email Configuration
EMAIL_SENDER = "singh.manpreet171900@gmail.com"  # Replace with your email address
EMAIL_PASSWORD = "gqqmekiyrnoubjch"   # Replace with your app password
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# Google Drive Configuration
GOOGLE_CREDENTIALS_FILE = "credentials.json.json"  # Path to your Google API credentials file
GOOGLE_TOKEN_FILE = "token.json"  # Path to store the Google API token

# Application Configuration
UPLOAD_FOLDER = "uploads"  # Folder to temporarily store uploaded files
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Excel File Configuration
EXCEL_FILE = "project_email.xlsx"  # Excel file mapping project IDs to emails

# Flask Configuration
SECRET_KEY = "a8d7f6e5c4b3a2d1e9f8c7b6"  # Random secret key
