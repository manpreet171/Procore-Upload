import streamlit as st
import requests
import msal
import json

# SharePoint/OneDrive connection test
st.set_page_config(page_title="SharePoint Connection Test", layout="wide")

st.title("SharePoint Connection Test")

# Hardcoded credentials for testing
CLIENT_ID = "your-client-id-here"
CLIENT_SECRET = "your-client-secret-here"
TENANT_ID = "your-tenant-id-here"

# Microsoft Graph API endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

def get_access_token():
    """Get access token using client credentials flow"""
    try:
        # Create a confidential client application
        app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET,
        )
        
        # Acquire token for client
        result = app.acquire_token_silent(SCOPES, account=None)
        
        if not result:
            result = app.acquire_token_for_client(scopes=SCOPES)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            st.error(f"Failed to acquire token: {result.get('error_description', 'Unknown error')}")
            return None
            
    except Exception as e:
        st.error(f"Error getting access token: {str(e)}")
        return None

def test_graph_api_access(token):
    """Test basic Microsoft Graph API access"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Test 1: Get organization info
    st.subheader("Test 1: Organization Info")
    try:
        response = requests.get('https://graph.microsoft.com/v1.0/organization', headers=headers)
        if response.status_code == 200:
            org_data = response.json()
            st.success("✅ Successfully connected to Microsoft Graph!")
            if org_data.get('value'):
                org_name = org_data['value'][0].get('displayName', 'Unknown')
                st.info(f"Organization: {org_name}")
        else:
            st.error(f"❌ Failed to get organization info: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error testing organization access: {str(e)}")
    
    # Test 2: Get sites (SharePoint)
    st.subheader("Test 2: SharePoint Sites Access")
    try:
        response = requests.get('https://graph.microsoft.com/v1.0/sites', headers=headers)
        if response.status_code == 200:
            sites_data = response.json()
            st.success("✅ Successfully accessed SharePoint sites!")
            if sites_data.get('value'):
                st.info(f"Found {len(sites_data['value'])} sites")
                for site in sites_data['value'][:3]:  # Show first 3 sites
                    st.write(f"- {site.get('displayName', 'Unknown')} ({site.get('webUrl', 'No URL')})")
        else:
            st.error(f"❌ Failed to get sites: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error testing sites access: {str(e)}")
    
    # Test 3: Get drives (OneDrive/SharePoint document libraries)
    st.subheader("Test 3: Drives Access")
    try:
        response = requests.get('https://graph.microsoft.com/v1.0/me/drives', headers=headers)
        if response.status_code == 200:
            drives_data = response.json()
            st.success("✅ Successfully accessed drives!")
            if drives_data.get('value'):
                st.info(f"Found {len(drives_data['value'])} drives")
                for drive in drives_data['value']:
                    st.write(f"- {drive.get('name', 'Unknown')} (Type: {drive.get('driveType', 'Unknown')})")
        else:
            st.error(f"❌ Failed to get drives: {response.status_code} - {response.text}")
            st.info("This might be expected if using application permissions instead of delegated permissions")
    except Exception as e:
        st.error(f"❌ Error testing drives access: {str(e)}")

def main():
    st.info("This test will verify if your Azure app registration has the correct permissions to access SharePoint/OneDrive")
    
    if st.button("Test SharePoint Connection"):
        with st.spinner("Testing connection..."):
            # Get access token
            token = get_access_token()
            
            if token:
                st.success("✅ Successfully obtained access token!")
                
                # Test API access
                test_graph_api_access(token)
                
            else:
                st.error("❌ Failed to get access token")
                st.info("Please check your Azure app registration and secrets configuration")

if __name__ == "__main__":
    main()
