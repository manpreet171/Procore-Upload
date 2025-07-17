import os
import streamlit as st
import requests
from office365.runtime.auth.client_credential import ClientCredential
from office365.runtime.auth.authentication_context import AuthenticationContext
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
        
        # Print debug information about the client ID and secret format
        print(f"Client ID length: {len(client_id)}")
        print(f"Client Secret length: {len(client_secret)}")
        print(f"Client ID first 5 chars: {client_id[:5]}...")
        print(f"Client Secret first 5 chars: {client_secret[:5]}...")
        
        # Try both site URLs with detailed error logging
        site_urls = [
            "https://sdgny.sharepoint.com/sites/sharedadmin",
            "https://sdgny.sharepoint.com"
        ]
        
        # Extract tenant name from the SharePoint URL
        tenant_name = "sdgny"  # From sdgny.sharepoint.com
        
        # Try multiple authentication methods
        last_error = None
        
        # Method 1: Try using ClientCredential directly
        for site_url in site_urls:
            try:
                print(f"\nMethod 1: Attempting to connect to {site_url} using ClientCredential")
                client_credentials = ClientCredential(client_id, client_secret)
                ctx = ClientContext(site_url).with_credentials(client_credentials)
                ctx.request_form_digest = False  # Disable form digest
                
                # Test the connection
                web = ctx.web
                ctx.load(web)
                ctx.execute_query()
                
                print(f"Successfully connected to SharePoint site: {web.properties['Title']}")
                return ctx, None
            except Exception as e:
                last_error = str(e)
                print(f"Method 1 error for {site_url}: {last_error}")
        
        # Method 2: Try using AuthenticationContext
        for site_url in site_urls:
            try:
                print(f"\nMethod 2: Attempting to connect to {site_url} using AuthenticationContext")
                auth_context = AuthenticationContext(url=site_url)
                auth_context.acquire_token_for_app(client_id=client_id, client_secret=client_secret)
                
                ctx = ClientContext(site_url, auth_context)
                ctx.request_form_digest = False  # Disable form digest
                
                # Test the connection
                web = ctx.web
                ctx.load(web)
                ctx.execute_query()
                
                print(f"Successfully connected to SharePoint site: {web.properties['Title']}")
                return ctx, None
            except Exception as e:
                last_error = str(e)
                print(f"Method 2 error for {site_url}: {last_error}")
        
        # Method 3: Try using tenant URL for authentication but site URL for context
        tenant_url = f"https://{tenant_name}.sharepoint.com"
        for site_url in site_urls:
            try:
                print(f"\nMethod 3: Authenticating with {tenant_url}, connecting to {site_url}")
                auth_context = AuthenticationContext(url=tenant_url)
                auth_context.acquire_token_for_app(client_id=client_id, client_secret=client_secret)
                
                ctx = ClientContext(site_url, auth_context)
                ctx.request_form_digest = False  # Disable form digest
                
                # Test the connection
                web = ctx.web
                ctx.load(web)
                ctx.execute_query()
                
                print(f"Successfully connected to SharePoint site: {web.properties['Title']}")
                return ctx, None
            except Exception as e:
                last_error = str(e)
                print(f"Method 3 error for {site_url}: {last_error}")
        
        # If we get here, all attempts failed
        print("\nAll authentication methods failed. Please check:")
        print("1. Client ID and Client Secret are correct")
        print("2. App registration has proper SharePoint permissions")
        print("3. Admin consent has been granted for the permissions")
        print("4. The site URL is correct and accessible")
        
        return None, f"SharePoint authentication error: {last_error}"
    
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
