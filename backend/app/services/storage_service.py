import os
import requests
import mimetypes
from flask import current_app

def upload_document_to_storage(file_bytes, filename, folder="vault_docs"):
    """
    Hybrid Cloud Storage Controller:
    - If SUPABASE_URL and SUPABASE_KEY are in the environment, uploads directly to Supabase Storage.
    - If credentials are missing, falls back gracefully to local static folder storage.
    
    Returns the permanent accessible URL (HTTPS cloud URL or local static URL path).
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    bucket_name = os.environ.get("SUPABASE_BUCKET", "medical-vaults")

    # Determine file MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    # CASE 1: Cloud Azure Blob Storage Upload
    azure_account = os.environ.get("AZURE_STORAGE_ACCOUNT")
    azure_container = os.environ.get("AZURE_STORAGE_CONTAINER", "medical-vaults")
    azure_sas_token = os.environ.get("AZURE_STORAGE_SAS_TOKEN")
    azure_conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if (azure_account and azure_sas_token) or azure_conn_str:
        try:
            from azure.storage.blob import BlobServiceClient, ContentSettings
            
            if azure_conn_str:
                blob_service_client = BlobServiceClient.from_connection_string(azure_conn_str)
                azure_account = blob_service_client.account_name
            else:
                # Format SAS token query parameter prefix
                sas = azure_sas_token if azure_sas_token.startswith("?") else f"?{azure_sas_token}"
                account_url = f"https://{azure_account}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(account_url, credential=sas)
                
            blob_path = f"{folder}/{filename}" if folder else filename
            blob_client = blob_service_client.get_blob_client(container=azure_container, blob=blob_path)
            
            content_settings = ContentSettings(content_type=mime_type)
            blob_client.upload_blob(file_bytes, overwrite=True, content_settings=content_settings)
            
            public_url = f"https://{azure_account}.blob.core.windows.net/{azure_container}/{blob_path}"
            current_app.logger.info(f"Azure Storage: Successfully uploaded {filename} to Azure Blob using SDK.")
            return public_url
            
        except Exception as e:
            current_app.logger.error(f"Azure Storage Exception (SDK): {str(e)}. Cascading fallback.")

    # CASE 2: Cloud Supabase Storage Upload
    if supabase_url and supabase_key:
        try:
            # Clean Supabase URL formatting
            base_url = supabase_url.rstrip("/")
            # Target path: {SUPABASE_URL}/storage/v1/object/{bucket}/{folder}/{filename}
            upload_url = f"{base_url}/storage/v1/object/{bucket_name}/{folder}/{filename}"
            
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": mime_type
            }
            
            # Post binary payload directly to Supabase REST Storage API
            response = requests.post(upload_url, data=file_bytes, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # File uploaded successfully. Return the secure public URL
                public_url = f"{base_url}/storage/v1/object/public/{bucket_name}/{folder}/{filename}"
                current_app.logger.info(f"Supabase Cloud Storage: Successfully uploaded {filename} to cloud.")
                return public_url
            else:
                current_app.logger.error(
                    f"Supabase Cloud Storage Error: API responded with status {response.status_code} - {response.text}. Falling back to local disk."
                )
        except Exception as e:
            current_app.logger.error(f"Supabase Cloud Storage Exception: {str(e)}. Falling back to local disk.")

    # CASE 2: Local Static Fallback (Development Offline Mode)
    try:
        upload_dir = os.path.join(current_app.static_folder, folder)
        os.makedirs(upload_dir, exist_ok=True)
        full_file_path = os.path.join(upload_dir, filename)
        
        with open(full_file_path, "wb") as f:
            f.write(file_bytes)
            
        current_app.logger.info(f"Local Static Disk Storage: Successfully saved {filename} on local disk.")
        # Return path relative to static folder
        return f"{folder}/{filename}"
    except Exception as e:
        current_app.logger.error(f"Local Storage Error: Failed to save file to local disk: {str(e)}")
        raise e
