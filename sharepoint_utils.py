import os
import streamlit as st
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File

def get_sharepoint_context():
    """Get SharePoint client context using credentials from Streamlit secrets"""
    try:
        # Check if SharePoint credentials exist in Streamlit secrets
        if "SHAREPOINT_USERNAME" not in st.secrets or "SHAREPOINT_PASSWORD" not in st.secrets:
            return None, "SharePoint credentials not found in Streamlit secrets. Please add SHAREPOINT_USERNAME and SHAREPOINT_PASSWORD."
        
        # Get SharePoint credentials from Streamlit secrets
        username = st.secrets["SHAREPOINT_USERNAME"]
        password = st.secrets["SHAREPOINT_PASSWORD"]
        site_url = "https://sdgny.sharepoint.com/sites/sharedadmin"
        
        # Create user credentials and client context
        user_credentials = UserCredential(username, password)
        ctx = ClientContext(site_url).with_credentials(user_credentials)
        
        return ctx, None
    except Exception as e:
        return None, f"SharePoint authentication error: {str(e)}"

def ensure_folder_exists(ctx, relative_folder_path):
    """Ensure a folder exists in SharePoint, creating it if necessary"""
    try:
        # Make sure we're working with the correct base path
        # The base document library in SharePoint is usually "Shared Documents"
        base_path = "Shared Documents"
        
        # Split the path into parts
        folder_parts = relative_folder_path.strip('/').split('/')
        current_path = base_path
        
        # Create each folder in the path if it doesn't exist
        for folder_name in folder_parts:
            if not folder_name:
                continue
                
            current_path = f"{current_path}/{folder_name}"
            
            # Check if folder exists
            try:
                folder = ctx.web.get_folder_by_server_relative_url(current_path)
                ctx.load(folder)
                ctx.execute_query()
            except Exception:
                # Folder doesn't exist, create it
                parent_path = "/".join(current_path.split('/')[:-1])
                parent_folder = ctx.web.get_folder_by_server_relative_url(parent_path)
                folder_name = current_path.split('/')[-1]
                parent_folder.folders.add(folder_name)
                ctx.execute_query()
        
        return True, current_path
    except Exception as e:
        return False, f"Error creating folder structure: {str(e)}"

def upload_file_to_sharepoint(ctx, file_path, target_folder):
    """Upload a file to SharePoint"""
    try:
        # Get the file name from the path
        file_name = os.path.basename(file_path)
        
        # Read the file content
        with open(file_path, 'rb') as content_file:
            file_content = content_file.read()
        
        # Upload the file to SharePoint
        target_url = f"{target_folder}/{file_name}"
        File.save_binary(ctx, target_url, file_content)
        
        return True, f"File {file_name} uploaded successfully"
    except Exception as e:
        return False, f"Error uploading file: {str(e)}"
