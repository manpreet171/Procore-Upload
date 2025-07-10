# Project Image Upload System - User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Uploading Images](#uploading-images)
4. [Managing Projects](#managing-projects)
   - [Adding Projects](#adding-projects)
   - [Editing Projects](#editing-projects)
   - [Deleting Projects](#deleting-projects)
   - [Bulk Import](#bulk-import)
   - [Viewing and Exporting Data](#viewing-and-exporting-data)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

## Introduction

The Project Image Upload System allows you to easily upload images for specific projects and automatically send them to the appropriate recipients by email. This system helps streamline the process of sharing project images with team members and stakeholders.

Key features include:
- Upload multiple images for specific projects with status categorization
- Automatic email sending to project contacts with status-labeled attachments
- Project management (add, edit, delete projects)
- Bulk import of project data
- View and export project data
- Persistent data storage using GitHub integration

## Getting Started

When you first open the application, you'll see two main tabs:
- **Upload Images**: For uploading project images
- **Manage Projects**: For adding, editing, and managing project information

Before uploading any images, make sure the project you're working with has been added to the system with the correct email address.

## Uploading Images

To upload images for a project:

1. Click on the **Upload Images** tab
2. Enter the **Project ID** in the text field
3. Select a **Status** from the dropdown menu:
   - **PRODUCTION**: For production-related images
   - **SHIPPED**: For shipping-related images
   - **PICKUP**: For pickup-related images
   - **INSTALLATION**: For installation-related images
4. Click the **Browse files** button to select images from your computer
   - You can select multiple images at once
   - Supported formats: JPG, JPEG, PNG
5. Once you've selected your images, they will appear in the preview area
6. Click the **Send Images** button to process the images
7. The system will:
   - Verify the Project ID exists
   - Rename the images with the selected status (e.g., "PRODUCTION-1.jpg")
   - Send the images to the email address associated with the project
   - Display a success message when complete
   - Automatically reset the form for a new submission

**Note**: If the Project ID doesn't exist in the system, you'll receive an error message. You'll need to add the project first using the Manage Projects tab.

**Email Format**: The email will have a subject line with the status (e.g., "PRODUCTION Images") and will include the renamed image files as attachments.

## Managing Projects

The Manage Projects tab requires an admin password for access. Once you enter the correct password, you'll see three sub-tabs:

### Adding Projects

To add a new project:

1. Go to the **Add/Edit Projects** tab
2. In the "Add New Project" section:
   - Enter the Project ID
   - Enter the Email Address that should receive images for this project
3. Click the **Add Project** button
4. You'll see a success message when the project is added

### Editing Projects

To edit an existing project:

1. Go to the **Add/Edit Projects** tab
2. In the "Edit or Delete Project" section:
   - Select the Project ID from the dropdown menu
3. Click the **Edit Selected Project** button
4. Update the Project ID and/or Email Address in the form that appears
5. Click **Save Changes** to update the project information
   - Or click **Cancel Edit** to discard your changes

### Deleting Projects

To delete a project:

1. Go to the **Add/Edit Projects** tab
2. In the "Edit or Delete Project" section:
   - Select the Project ID from the dropdown menu
3. Click the **Delete Selected Project** button
4. The project will be removed from the system

### Bulk Import

If you have many projects to add at once, you can use the bulk import feature:

1. Go to the **Bulk Import** tab
2. Prepare your data file:
   - Create an Excel or CSV file with two columns: "Project ID" and "Email ID link"
   - You can download a sample template by clicking **Download Sample CSV** or **Download Sample Excel**
3. Click **Browse files** to select your prepared file
4. Review the file preview to ensure your data looks correct
5. Click **Import Projects**
6. You'll see a summary showing:
   - How many projects were added successfully
   - How many were skipped (duplicates)
   - Any errors that occurred

### Viewing and Exporting Data

To view or export your project data:

1. Go to the **View/Export Data** tab
2. You'll see a table with all projects and their associated email addresses
3. To download this data:
   - Click **Download as CSV** for a CSV file
   - Click **Download as Excel** for an Excel file
4. To view the change history (additions, edits, deletions):
   - Click the **Show Change History** button
   - A table will display showing all changes with timestamps

## Troubleshooting

**Problem**: Project ID not found when uploading images
- **Solution**: Check that you've entered the correct Project ID. Go to the Manage Projects tab to verify the project exists or to add it.

**Problem**: Images not sending to email
- **Solution**: Verify the email address associated with the project is correct by checking in the Manage Projects tab. If the email address is correct, check the Email Sending Log in the Upload Images tab for detailed information about any errors.

**Problem**: Can't access Manage Projects tab
- **Solution**: Make sure you're entering the correct admin password. If you've forgotten the password, contact your system administrator.

**Problem**: Bulk import shows many skipped entries
- **Solution**: Skipped entries are usually duplicates (Project IDs that already exist in the system). Check your import file for duplicate Project IDs.

**Problem**: Form doesn't reset after submission
- **Solution**: The form should automatically reset after a successful submission. If it doesn't, try refreshing the page or check for any error messages in the Email Sending Log.

## FAQ

**Q: How many images can I upload at once?**
A: You can select multiple images at once, but very large uploads (over 25MB total) may take longer to process. The email system has a 10MB limit for all attachments combined.

**Q: What does the Status field do?**
A: The Status field categorizes your images and determines how they are renamed before being sent. For example, selecting "PRODUCTION" will rename your images as "PRODUCTION-1.jpg", "PRODUCTION-2.jpg", etc. This helps the recipient identify the type of images they're receiving.

**Q: Can I change the email address for a project?**
A: Yes, use the Edit function in the Manage Projects tab to update the email address.

**Q: Is there a limit to how many projects I can add?**
A: No, you can add as many projects as needed.

**Q: Can multiple people use the system at the same time?**
A: Yes, the system supports multiple users accessing it simultaneously. All data is synchronized using GitHub to ensure everyone sees the most up-to-date information.

**Q: How do I know if my changes were saved?**
A: The system will display a success message after each action. You can also check the change history in the View/Export Data tab.

**Q: Can I see who made changes to the project data?**
A: The change history shows when changes were made, but not who made them. Contact your administrator if you need user-specific tracking.

**Q: What happens if there's no internet connection?**
A: The system will continue to work with local data storage. When the connection is restored, it will automatically synchronize with GitHub.

**Q: Can I see details about email sending errors?**
A: Yes, the Upload Images tab includes an Email Sending Log that shows detailed information about the email sending process, including any errors that occur.
