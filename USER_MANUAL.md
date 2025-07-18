# Project Image Upload System - User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Procore Projects Tab](#procore-projects-tab)
4. [Shopify Orders Tab](#shopify-orders-tab)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

## Introduction

The Project Image Upload System allows you to easily upload images for specific projects and automatically send them to the appropriate recipients by email or upload them to SharePoint. This system helps streamline the process of sharing project images with team members and stakeholders.

Key features include:
- Upload multiple images for Procore projects with status categorization and automatic email sending
- Upload Shopify order images directly to SharePoint with automatic folder organization
- Status-based categorization for both Procore and Shopify images
- Persistent data storage using Azure SQL database
- Simple, streamlined interface with auto-refresh functionality

## Getting Started

When you first open the application, you'll see two main tabs:
- **Procore Projects**: For uploading project images that will be sent via email
- **Shopify Orders**: For uploading order images directly to SharePoint

Before uploading any images, make sure the project or order you're working with exists in the database.

## Procore Projects Tab

To upload images for a Procore project:

1. Click on the **Procore Projects** tab
2. Select a **Project ID** from the dropdown menu or start typing to search
3. Select a **Status** from the dropdown menu:
   - **PRODUCTION**: For production-related images
   - **SHIPPED**: For shipping-related images
   - **PICKUP**: For pickup-related images
   - **INSTALLATION**: For installation-related images
4. Click the **Browse files** button to select images from your computer
   - You can select multiple images at once
   - Supported formats: PNG, JPG, JPEG, GIF, BMP, TIF, TIFF, PDF
5. Once you've selected your images, they will appear in the preview area
6. Click the **Send Images** button to process the images
7. The system will:
   - Verify the Project ID exists in the database
   - Rename the images with the selected status (e.g., "PRODUCTION-[unique-id].jpg")
   - Send the images to the email address associated with the project
   - Display a success message when complete
   - Automatically reset the form for a new submission

**Note**: If the Project ID doesn't exist in the system, you'll receive an error message.

**Email Format**: The email will have a subject line with the status (e.g., "PRODUCTION") and will include the renamed image files as attachments.

## Shopify Orders Tab

To upload images for a Shopify order to SharePoint:

1. Click on the **Shopify Orders** tab
2. Select an **OrderID** from the dropdown menu
   - The customer name will automatically display below the selection
3. Select a **Status** from the dropdown menu:
   - **PRODUCTION**: For production-related images
   - **SHIPPED**: For shipping-related images
   - **PICKUP**: For pickup-related images
   - **INSTALLATION**: For installation-related images
4. Click the **Browse files** button to select images for upload
   - You can select multiple images at once
   - Supported formats: PNG, JPG, JPEG, GIF, BMP, TIF, TIFF, PDF
5. Once you've selected your images, they will appear in the preview area
6. Click the **Upload to SharePoint** button to process the images
7. The system will:
   - Authenticate with SharePoint using secure credentials
   - Create a folder structure in SharePoint: CustomerName/Status/OrderID
   - Upload all selected images to the appropriate folder
   - Display a success message when complete
   - Automatically reset the form for a new submission

**Note**: The Shopify OrderIDs and customer names are pulled from the database. If you don't see an OrderID in the dropdown, it means it hasn't been added to the ShopifyProjectData table in the database.

## Troubleshooting

**Problem**: Project ID not found when uploading images in Procore Projects tab
- **Solution**: Check that you've selected a valid Project ID from the dropdown. If the Project ID doesn't appear in the dropdown, it means it hasn't been added to the database.

**Problem**: Images not sending to email
- **Solution**: Verify the database connection is working (check the status in the sidebar). If the connection is good but emails aren't sending, there might be an issue with the email server or credentials.

**Problem**: OrderID not found in Shopify Orders tab
- **Solution**: The OrderID must exist in the ShopifyProjectData table in the database. Contact your database administrator to add the missing OrderID.

**Problem**: SharePoint upload fails
- **Solution**: Check the database connection and ensure the SharePoint credentials are correctly configured in the Streamlit secrets. If the problem persists, there might be an issue with SharePoint permissions or connectivity.

**Problem**: Form doesn't reset after submission
- **Solution**: The form should automatically reset after a successful submission. If it doesn't, try refreshing the page or check for any error messages that might be displayed.

## FAQ

**Q: How many images can I upload at once?**
A: You can select multiple images at once, but very large uploads (over 25MB total) may take longer to process. For the Procore Projects tab, the email system has a limit for all attachments combined (typically 10MB). For the Shopify Orders tab, SharePoint has higher limits but uploading very large files may take longer.

**Q: What does the Status field do?**
A: The Status field categorizes your images. In the Procore Projects tab, it determines how images are renamed before being sent via email. In the Shopify Orders tab, it determines which folder the images are uploaded to in SharePoint (CustomerName/Status/OrderID).

**Q: Where are the Shopify images stored?**
A: Shopify order images are uploaded to a SharePoint library called "Shopify_orders_photos" in a folder structure based on CustomerName/Status/OrderID.

**Q: How do I add new Procore Projects or Shopify Orders to the system?**
A: Projects and orders are managed in the Azure SQL database. Contact your database administrator to add new projects or orders.

**Q: Can multiple people use the system at the same time?**
A: Yes, the system supports multiple users accessing it simultaneously. All data is stored in an Azure SQL database to ensure everyone sees the most up-to-date information.

**Q: How do I know if my uploads were successful?**
A: The system will display a success message after each action. For Procore Projects, you'll see "Images sent successfully!" For Shopify Orders, you'll see "Successfully uploaded X image(s)!"

**Q: What happens if there's no internet connection?**
A: The system requires an internet connection to function properly as it needs to connect to the Azure SQL database, send emails, and upload to SharePoint.

**Q: What file types can I upload?**
A: The system supports PNG, JPG, JPEG, GIF, BMP, TIF, TIFF, and PDF files.

**Q: Why does the form reset after I upload images?**
A: The form automatically resets after a successful upload to make it easier to start a new upload without having to manually clear the fields.
