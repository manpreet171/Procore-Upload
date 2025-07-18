def upload_images_tab():
    """Tab for uploading images to Procore projects"""
    # Initialize session state variables if they don't exist
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
    # Only generate new form keys when the form is submitted successfully
    # or when the app first loads and keys don't exist
    if 'form_key_prefix' not in st.session_state or st.session_state.form_submitted:
        st.session_state.form_key_prefix = f"upload_form_{int(time.time())}"
    
    # Use the stored keys
    project_id_key = f"{st.session_state.form_key_prefix}_project_id"
    status_key = f"{st.session_state.form_key_prefix}_status"
    file_uploader_key = f"{st.session_state.form_key_prefix}_files"
    
    # Check if we need to reset the form
    if st.session_state.form_submitted:
        # Reset the flag
        st.session_state.form_submitted = False
        # Force a rerun with clean state - no message about form reset
        st.rerun()
    
    st.header("Upload Images")
    
    # Get all project IDs for autocomplete
    all_project_ids = get_all_project_ids()
    
    # Project ID input with autocomplete
    if all_project_ids:
        # Add an empty option at the beginning
        project_id_options = [""]
        project_id_options.extend(all_project_ids)
        
        # Use selectbox with autocomplete
        project_id = st.selectbox(
            "Project ID",
            options=project_id_options,
            key=project_id_key,
            placeholder="Select or type to search Project ID",
            index=0  # Default to empty option
        )
    else:
        # Fallback to regular text input if no project IDs are available
        project_id = st.text_input("Project ID", placeholder="Enter the Project ID", key=project_id_key)
    
    # Status dropdown with dynamic key
    status_options = ["", "PRODUCTION", "SHIPPED", "PICKUP", "INSTALLATION"]
    status = st.selectbox("Status", options=status_options, key=status_key, index=0)  # Default to blank option
    
    # File upload with dynamic key
    uploaded_files = st.file_uploader(
        "Upload Images", 
        accept_multiple_files=True,
        type=list(ALLOWED_EXTENSIONS),
        key=file_uploader_key
    )
    
    # Only show Send Images button if both Project ID and Status are selected (not blank)
    if project_id and status and uploaded_files:
        if st.button("Send Images"):
            recipient_email = get_email_for_project(project_id)
            
            if not recipient_email:
                st.error(f"No email found for Project ID: {project_id}")
            else:
                # Save uploaded files
                saved_files = []
                for uploaded_file in uploaded_files:
                    # Create a unique filename with status prefix
                    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                    unique_filename = f"{status}_{uuid.uuid4()}{file_extension}"
                    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    
                    # Get file content
                    file_content = uploaded_file.getbuffer()
                    
                    # Optimize image if it's an image file (not PDF)
                    if file_extension not in ['.pdf']:
                        try:
                            # Optimize the image to reduce size
                            optimized_content = optimize_image(file_content, max_size_kb=500)
                            
                            # Save the optimized file
                            with open(file_path, "wb") as f:
                                f.write(optimized_content)
                        except Exception as e:
                            # If optimization fails, save original file
                            with open(file_path, "wb") as f:
                                f.write(file_content)
                    else:
                        # For PDFs, save as is
                        with open(file_path, "wb") as f:
                            f.write(file_content)
                    
                    saved_files.append(file_path)
                
                # Send email with attachments
                subject = f"{status}"
                body = f"<p>{status}</p>"
                
                if send_email(recipient_email, subject, body, saved_files):
                    # Set flag to reset form on next rerun
                    st.session_state.form_submitted = True
                    st.success("Images sent successfully!")
                    
                    # Log to Slack if webhook URL is configured
                    if SLACK_WEBHOOK_URL:
                        try:
                            slack_message = {
                                "text": f"Images for Project ID: {project_id} with status '{status}' sent to {recipient_email}"
                            }
                            requests.post(SLACK_WEBHOOK_URL, json=slack_message)
                        except Exception as e:
                            st.warning(f"Could not send Slack notification: {e}")
                    
                    # Force a rerun to reset the form immediately
                    time.sleep(1)  # Give user time to see the success message
                    st.rerun()
                else:
                    st.error("Failed to send email. Please check the logs.")
                    
                    # Clean up files if email failed
                    for file_path in saved_files:
                        if os.path.exists(file_path):
                            os.remove(file_path)
