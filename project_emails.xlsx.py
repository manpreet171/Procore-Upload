import pandas as pd
import os

# Sample data mapping project IDs to email addresses
data = {
    'Project ID': ['999', 'PRJ002', 'PRJ003', 'PRJ004', 'PRJ005'],
    'Email ID link': [
        'upload-sandbox-test-project-ikqyp6it8t@us02.procore.com',
        'project2@example.com', 
        'project3@example.com', 
        'project4@example.com', 
        'project5@example.com'
    ]
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to Excel file
excel_file = 'project_email.xlsx'
df.to_excel(excel_file, index=False)

print(f"Sample Excel file '{excel_file}' created successfully!")
print(f"The file contains {len(data['Project ID'])} project mappings.")
print("\nSample data:")
print(df.head())
