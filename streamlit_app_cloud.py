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
    EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
    EMAIL_SMTP_SERVER = st.secrets["EMAIL_SMTP_SERVER"]
    EMAIL_SMTP_PORT = st.secrets["EMAIL_SMTP_PORT"]
    # Get admin password from secrets if available
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
else:
    # Fallback for local development without secrets
    try:
        import config
        EMAIL_SENDER = config.EMAIL_SENDER
        EMAIL_PASSWORD = config.EMAIL_PASSWORD
        EMAIL_SMTP_SERVER = config.EMAIL_SMTP_SERVER
        EMAIL_SMTP_PORT = config.EMAIL_SMTP_PORT
        # Get admin password from config if available, otherwise use default
        ADMIN_PASSWORD = getattr(config, "ADMIN_PASSWORD", "admin123")
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
    """Send email with attachments"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
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
        server = smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, recipient_email, text)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error sending email: {e}")
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
    project_id = st.text_input("Project ID", placeholder="Enter the Project ID", key="upload_project_id")
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload Images", 
        accept_multiple_files=True,
        type=list(ALLOWED_EXTENSIONS)
    )
    
    if uploaded_files and project_id:
        if st.button("Send Images"):
            with st.spinner("Processing images..."):
                # Create a temporary directory for this upload
                temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
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
                
                # Send email with attachments
                subject = f"Images for Project ID: {project_id}"
                body = f"Please find attached images for Project ID: {project_id}"
                
                email_sent = send_email(email, subject, body, saved_files)
                
                if email_sent:
                    st.success(f"Images sent to {email}")
                else:
                    st.error("Failed to send email")
                
                # Clean up temp files
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Display information
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("1. Enter the Project ID")
    st.markdown("2. Upload one or more images (JPG, PNG, GIF)")
    st.markdown("3. Click 'Send Images' to email them to the associated address")

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
