import requests
import msal

# Hardcoded credentials for testing
CLIENT_ID = "3144c832-252d-40d3-9496-92dfe72ebfa7"
CLIENT_SECRET = "mx18Q~d_gmItyuP4IbV_ksNrByKtZNx6txIqObLA"
TENANT_ID = "49302541-652f-4f88-a011-e33be6116bd3"

# Microsoft Graph API endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

def get_access_token():
    """Get access token using client credentials flow"""
    try:
        print("[AUTH] Getting access token...")
        
        app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET,
        )
        
        result = app.acquire_token_for_client(scopes=SCOPES)
        
        if "access_token" in result:
            print("[SUCCESS] Got access token!")
            return result["access_token"]
        else:
            print(f"[ERROR] Failed to get token: {result.get('error_description', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Exception getting token: {str(e)}")
        return None

def search_for_shopify_folder(token):
    """Search for Shopify Photos folder using different methods"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("\n" + "="*60)
    print("SEARCHING FOR SHOPIFY PHOTOS FOLDER")
    print("="*60)
    
    # Method 1: Search using Graph API search
    print("\n[METHOD 1] Using Graph API search...")
    try:
        search_url = "https://graph.microsoft.com/v1.0/search/query"
        search_data = {
            "requests": [
                {
                    "entityTypes": ["driveItem"],
                    "query": {
                        "queryString": "Shopify Photos"
                    },
                    "from": 0,
                    "size": 25
                }
            ]
        }
        
        response = requests.post(search_url, headers=headers, json=search_data)
        print(f"Search response status: {response.status_code}")
        
        if response.status_code == 200:
            search_results = response.json()
            print("[SUCCESS] Search completed")
            
            if search_results.get('value') and len(search_results['value']) > 0:
                hits = search_results['value'][0].get('hitsContainers', [])
                if hits and len(hits) > 0:
                    items = hits[0].get('hits', [])
                    print(f"Found {len(items)} search results:")
                    
                    for item in items:
                        resource = item.get('resource', {})
                        name = resource.get('name', 'Unknown')
                        web_url = resource.get('webUrl', 'No URL')
                        print(f"  - {name}")
                        print(f"    URL: {web_url}")
                        
                        if 'Shopify' in name:
                            return resource
                else:
                    print("No search results found")
            else:
                print("No search results returned")
        else:
            print(f"Search failed: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Search exception: {str(e)}")
    
    # Method 2: Try to access via direct path
    print("\n[METHOD 2] Trying direct path access...")
    try:
        # Try different path formats
        paths_to_try = [
            "https://graph.microsoft.com/v1.0/sites/root/drive/root:/Shopify Photos",
            "https://graph.microsoft.com/v1.0/sites/root/drives/Documents/root:/Shopify Photos",
        ]
        
        for path in paths_to_try:
            print(f"Trying path: {path}")
            response = requests.get(path, headers=headers)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                folder_data = response.json()
                print(f"  [SUCCESS] Found folder: {folder_data.get('name')}")
                print(f"  Folder ID: {folder_data.get('id')}")
                return folder_data
            elif response.status_code == 404:
                print("  [INFO] Path not found")
            else:
                print(f"  [ERROR] {response.text}")
                
    except Exception as e:
        print(f"[ERROR] Direct path exception: {str(e)}")
    
    # Method 3: List all drives and their contents
    print("\n[METHOD 3] Listing all drives and their root contents...")
    try:
        response = requests.get('https://graph.microsoft.com/v1.0/sites/root/drives', headers=headers)
        
        if response.status_code == 200:
            drives_data = response.json()
            
            for drive in drives_data.get('value', []):
                drive_name = drive.get('name', 'Unknown')
                drive_id = drive.get('id', 'Unknown')
                print(f"\n--- Drive: {drive_name} (ID: {drive_id}) ---")
                
                # Get root items for this drive
                try:
                    items_response = requests.get(
                        f'https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children',
                        headers=headers
                    )
                    
                    if items_response.status_code == 200:
                        items_data = items_response.json()
                        items = items_data.get('value', [])
                        print(f"Found {len(items)} items in {drive_name}:")
                        
                        for item in items:
                            item_name = item.get('name', 'Unknown')
                            item_type = 'Folder' if 'folder' in item else 'File'
                            print(f"  - {item_name} ({item_type})")
                            
                            if 'Shopify' in item_name:
                                print(f"    [FOUND SHOPIFY ITEM] ID: {item.get('id')}")
                                return item
                    else:
                        print(f"  Could not access items: {items_response.status_code}")
                        
                except Exception as e:
                    print(f"  Error accessing drive items: {str(e)}")
                    
    except Exception as e:
        print(f"[ERROR] Drive listing exception: {str(e)}")
    
    return None

def test_folder_permissions(token, folder_data):
    """Test permissions on the found folder"""
    if not folder_data:
        return
        
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    folder_id = folder_data.get('id')
    folder_name = folder_data.get('name', 'Unknown')
    
    print(f"\n[PERMISSIONS TEST] Testing permissions on {folder_name}...")
    
    # Test 1: Try to list contents
    try:
        response = requests.get(
            f'https://graph.microsoft.com/v1.0/drives/{folder_data.get("parentReference", {}).get("driveId", "unknown")}/items/{folder_id}/children',
            headers=headers
        )
        
        if response.status_code == 200:
            items = response.json().get('value', [])
            print(f"[SUCCESS] Can read folder contents ({len(items)} items)")
        else:
            print(f"[ERROR] Cannot read contents: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] Exception reading contents: {str(e)}")
    
    # Test 2: Try to create a test folder
    try:
        test_data = {
            "name": "API_TEST_FOLDER",
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        response = requests.post(
            f'https://graph.microsoft.com/v1.0/drives/{folder_data.get("parentReference", {}).get("driveId", "unknown")}/items/{folder_id}/children',
            headers=headers,
            json=test_data
        )
        
        if response.status_code == 201:
            created_folder = response.json()
            print(f"[SUCCESS] Can create folders")
            
            # Clean up - delete the test folder
            test_folder_id = created_folder.get('id')
            delete_response = requests.delete(
                f'https://graph.microsoft.com/v1.0/drives/{folder_data.get("parentReference", {}).get("driveId", "unknown")}/items/{test_folder_id}',
                headers=headers
            )
            
            if delete_response.status_code == 204:
                print("[SUCCESS] Test folder cleaned up")
            
        else:
            print(f"[ERROR] Cannot create folders: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Exception testing folder creation: {str(e)}")

def main():
    print("[START] Comprehensive Shopify Folder Search")
    print("="*60)
    
    # Get access token
    token = get_access_token()
    if not token:
        print("[ERROR] Cannot proceed without access token")
        return
    
    # Search for the folder
    folder_data = search_for_shopify_folder(token)
    
    if folder_data:
        print(f"\n[SUCCESS] Found Shopify folder: {folder_data.get('name')}")
        print(f"Folder ID: {folder_data.get('id')}")
        print(f"Web URL: {folder_data.get('webUrl', 'No URL')}")
        
        # Test permissions
        test_folder_permissions(token, folder_data)
    else:
        print("\n[ERROR] Could not find Shopify Photos folder")
        print("This could be due to:")
        print("- Folder permissions")
        print("- Different folder name")
        print("- Folder location")
        print("- API access limitations")
    
    print("\n" + "="*60)
    print("[COMPLETE] Search completed")
    print("="*60)

if __name__ == "__main__":
    main()
