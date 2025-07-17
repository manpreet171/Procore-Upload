import os
import streamlit as st
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File

def get_sharepoint_context():
    """Get SharePoint client context using Azure AD App-Only authentication"""
    try:
        # Check if SharePoint app credentials exist in Streamlit secrets
        if "SHAREPOINT_CLIENT_ID" not in st.secrets or "SHAREPOINT_CLIENT_SECRET" not in st.secrets:
            return None, "SharePoint app credentials not found in Streamlit secrets. Please add SHAREPOINT_CLIENT_ID and SHAREPOINT_CLIENT_SECRET."
        
        # Get SharePoint app credentials from Streamlit secrets
        client_id = st.secrets["SHAREPOINT_CLIENT_ID"]
        client_secret = st.secrets["SHAREPOINT_CLIENT_SECRET"]
        
        # Try different SharePoint site URLs
        # First try the tenant root site
        site_url = "https://sdgny.sharepoint.com"
        
        # Print debug information
        print(f"Attempting to connect to SharePoint with client ID: {client_id[:5]}...")
        print(f"Site URL: {site_url}")
        
        try:
            # Create client credentials and client context
            client_credentials = ClientCredential(client_id, client_secret)
            ctx = ClientContext(site_url).with_credentials(client_credentials)
            
            # Test the connection by getting the web title
            web = ctx.web
            ctx.load(web)
            ctx.execute_query()
            
            print(f"Successfully connected to SharePoint site: {web.properties['Title']}")
            return ctx, None
        except Exception as e:
            error_msg = str(e)
            print(f"Error connecting to {site_url}: {error_msg}")
            
            # Try the specific site collection as fallback
            site_url = "https://sdgny.sharepoint.com/sites/sharedadmin"
            print(f"Trying alternate site URL: {site_url}")
            
            try:
                client_credentials = ClientCredential(client_id, client_secret)
                ctx = ClientContext(site_url).with_credentials(client_credentials)
                web = ctx.web
                ctx.load(web)
                ctx.execute_query()
                
                print(f"Successfully connected to SharePoint site: {web.properties['Title']}")
                return ctx, None
            except Exception as e2:
                error_msg = str(e2)
                print(f"Error connecting to {site_url}: {error_msg}")
                return None, f"SharePoint authentication error: {error_msg}"
    except Exception as e:
        print(f"General error: {str(e)}")
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
