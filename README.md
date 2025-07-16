# Project Image Upload System

A Streamlit application for uploading images associated with Project IDs, sending them via email, and managing project information.

## Features

- **Upload Images**: Upload multiple images and send them via email based on Project ID
- **Manage Projects**: Add and view Project IDs and their associated email addresses
- **Azure SQL Database**: Store and retrieve project information from Azure SQL Database
- **GitHub Integration**: Backup data to GitHub repository

## Setup Instructions

### Local Development

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/project-image-upload.git
   cd project-image-upload
   ```

### Azure SQL Database Configuration

1. Create an Azure SQL Database or use an existing one
2. Configure your Streamlit secrets with the following Azure SQL credentials:
   ```toml
   # .streamlit/secrets.toml
   
   # Database credentials
   DB_SERVER = "your-server.database.windows.net"
   DB_NAME = "your-database"
   DB_USERNAME = "your-username"
   DB_PASSWORD = "your-password"
   DB_DRIVER = "ODBC Driver 17 for SQL Server"  # For Linux/Streamlit Cloud
   # DB_DRIVER = "{ODBC Driver 17 for SQL Server}"  # For Windows
   
   # Email credentials
   EMAIL_SENDER = "your-email@example.com"
   EMAIL_SENDER_NAME = "Project Upload"
   BREVO_SMTP_SERVER = "smtp-relay.brevo.com"
   BREVO_SMTP_PORT = 587
   BREVO_SMTP_LOGIN = "your-brevo-login"
   BREVO_SMTP_PASSWORD = "your-brevo-password"
   
   # Admin password
   ADMIN_PASSWORD = "your-admin-password"
   
   # GitHub credentials
   GITHUB_USERNAME = "your-github-username"
   GITHUB_EMAIL = "your-github-email"
   GITHUB_TOKEN = "your-github-token"
   GITHUB_REPO = "your-repo-name"
   ```

### Streamlit Cloud Deployment

1. Push your code to GitHub
2. Deploy on Streamlit Cloud and add the secrets from above
3. Streamlit Cloud has built-in support for SQL Server ODBC drivers, so no additional configuration is needed

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a configuration file named `config.py` with the following content:
   ```python
   # Email Configuration
   EMAIL_SENDER = "your-email@gmail.com"  # Replace with your email address
   EMAIL_PASSWORD = "your-app-password"    # Replace with your app password
   EMAIL_SMTP_SERVER = "smtp.gmail.com"
   EMAIL_SMTP_PORT = 587

   # Application Configuration
   UPLOAD_FOLDER = "uploads"  # Folder to temporarily store uploaded files
   ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

   # Excel File Configuration
   EXCEL_FILE = "project_email.xlsx"  # Excel file mapping project IDs to emails
   ```

4. Create the uploads directory:
   ```
   mkdir uploads
   ```

5. Run the application:
   ```
   streamlit run simple_email_app.py
   ```

### Streamlit Cloud Deployment

1. Fork this repository to your GitHub account

2. Sign up for [Streamlit Cloud](https://streamlit.io/cloud)

3. Create a new app and connect it to your GitHub repository

4. In the Streamlit Cloud dashboard, add the following secrets:
   ```
   EMAIL_SENDER = "your-email@gmail.com"
   EMAIL_PASSWORD = "your-app-password"
   EMAIL_SMTP_SERVER = "smtp.gmail.com"
   EMAIL_SMTP_PORT = 587
   ```

5. Deploy the app

## Important Notes

- For Gmail, you need to use an App Password (not your regular password)
- To create an App Password, you need to have 2-Step Verification enabled on your Google account
- The Excel file structure must have columns named "Project ID" and "Email ID link"

## License

MIT
