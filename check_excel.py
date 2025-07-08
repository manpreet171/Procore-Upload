import pandas as pd

# Load the Excel file
try:
    df = pd.read_excel('project_email.xlsx')
    
    # Print the column names
    print("Column names in the Excel file:")
    print(df.columns.tolist())
    
    # Print the first few rows
    print("\nFirst 5 rows of data:")
    print(df.head())
    
    # Check specifically for Project ID 999
    print("\nLooking for Project ID '999':")
    matching_row = df[df['Project ID'] == '999']
    if not matching_row.empty:
        print(f"Found! Email: {matching_row.iloc[0]['Email ID link']}")
    else:
        print("Not found. Checking for Project ID 999 as integer:")
        matching_row = df[df['Project ID'] == 999]
        if not matching_row.empty:
            print(f"Found! Email: {matching_row.iloc[0]['Email ID link']}")
        else:
            print("Project ID 999 not found in any format")
    
    # Print all Project IDs for reference
    print("\nAll Project IDs in the file:")
    print(df['Project ID'].tolist())
    
except Exception as e:
    print(f"Error reading Excel file: {e}")
