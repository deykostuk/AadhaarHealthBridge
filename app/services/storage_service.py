import os
import requests
import mimetypes
import logging
from config import settings

logger = logging.getLogger(__name__)

def upload_document_to_storage(file_bytes, filename, folder="vault_docs"):
    """
    Hybrid Cloud Storage Controller:
    - If Azure credentials are in the environment, uploads to Azure Blob Storage.
    - If SUPABASE_URL and SUPABASE_KEY are configured, uploads to Supabase Storage.
    - Otherwise, saves to local upload folder.
    
    Returns the permanent accessible URL (HTTPS cloud URL or relative path).
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
                sas = azure_sas_token if azure_sas_token.startswith("?") else f"?{azure_sas_token}"
                account_url = f"https://{azure_account}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(account_url, credential=sas)
                
            blob_path = f"{folder}/{filename}" if folder else filename
            blob_client = blob_service_client.get_blob_client(container=azure_container, blob=blob_path)
            
            content_settings = ContentSettings(content_type=mime_type)
            blob_client.upload_blob(file_bytes, overwrite=True, content_settings=content_settings)
            
            public_url = f"https://{azure_account}.blob.core.windows.net/{azure_container}/{blob_path}"
            logger.info(f"Azure Storage: Successfully uploaded {filename} to Azure Blob using SDK.")
            return public_url
            
        except Exception as e:
            logger.error(f"Azure Storage Exception (SDK): {str(e)}. Cascading fallback.")

    # CASE 2: Cloud Supabase Storage Upload
    if supabase_url and supabase_key:
        try:
            base_url = supabase_url.rstrip("/")
            upload_url = f"{base_url}/storage/v1/object/{bucket_name}/{folder}/{filename}"
            
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": mime_type
            }
            
            response = requests.post(upload_url, data=file_bytes, headers=headers, timeout=15)
            if response.status_code == 200:
                public_url = f"{base_url}/storage/v1/object/public/{bucket_name}/{folder}/{filename}"
                logger.info(f"Supabase Cloud Storage: Successfully uploaded {filename} to cloud.")
                return public_url
            else:
                logger.error(
                    f"Supabase Cloud Storage Error: API responded with status {response.status_code} - {response.text}. Falling back to local disk."
                )
        except Exception as e:
            logger.error(f"Supabase Cloud Storage Exception: {str(e)}. Falling back to local disk.")

    # CASE 3: Local Private Storage (Development Offline Mode)
    try:
        upload_base = settings.UPLOAD_FOLDER
        upload_dir = os.path.join(upload_base, folder)
        os.makedirs(upload_dir, exist_ok=True)
        full_file_path = os.path.join(upload_dir, filename)
        
        with open(full_file_path, "wb") as f:
            f.write(file_bytes)
            
        logger.info(f"Local Private Disk Storage: Successfully saved {filename} in private folder.")
        return f"{folder}/{filename}"
    except Exception as e:
        logger.error(f"Local Storage Error: Failed to save file to private disk: {str(e)}")
        raise e


def delete_document_from_storage(file_path):
    """
    Unified Storage Deletion Controller:
    - Deletes from Azure Blob, Supabase, or local uploads.
    """
    if not file_path:
        return True

    # CASE 1: Cloud Azure Blob Storage Deletion
    azure_account = os.environ.get("AZURE_STORAGE_ACCOUNT")
    azure_container = os.environ.get("AZURE_STORAGE_CONTAINER", "medical-vaults")
    azure_sas_token = os.environ.get("AZURE_STORAGE_SAS_TOKEN")
    azure_conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if (azure_account and azure_sas_token) or azure_conn_str:
        try:
            from azure.storage.blob import BlobServiceClient
            if azure_conn_str:
                blob_service_client = BlobServiceClient.from_connection_string(azure_conn_str)
            else:
                sas = azure_sas_token if azure_sas_token.startswith("?") else f"?{azure_sas_token}"
                account_url = f"https://{azure_account}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(account_url, credential=sas)
                
            blob_path = file_path
            if file_path.startswith("http"):
                blob_path = file_path.split(f"/{azure_container}/")[-1]
                
            blob_client = blob_service_client.get_blob_client(container=azure_container, blob=blob_path)
            blob_client.delete_blob()
            logger.info(f"Azure Storage: Successfully deleted blob {blob_path}.")
            return True
        except Exception as e:
            logger.error(f"Azure Storage Deletion Exception: {str(e)}.")

    # CASE 2: Cloud Supabase Storage Deletion
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    bucket_name = os.environ.get("SUPABASE_BUCKET", "medical-vaults")

    if supabase_url and supabase_key and file_path.startswith("http"):
        try:
            base_url = supabase_url.rstrip("/")
            object_path = file_path.split(f"/public/{bucket_name}/")[-1]
            delete_url = f"{base_url}/storage/v1/object/{bucket_name}/{object_path}"
            
            headers = {
                "Authorization": f"Bearer {supabase_key}"
            }
            response = requests.delete(delete_url, headers=headers, timeout=15)
            if response.status_code == 200:
                logger.info(f"Supabase Storage: Successfully deleted {object_path}.")
                return True
            else:
                logger.error(f"Supabase Storage Deletion failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Supabase Storage Deletion Exception: {str(e)}.")

    # CASE 3: Local Private disk clean up
    try:
        upload_base = settings.UPLOAD_FOLDER
        full_path = os.path.join(upload_base, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Local Disk Deletion: Removed local copy of {file_path}")
        return True
    except Exception as e:
        logger.error(f"Local Disk Deletion Exception: {str(e)}.")
        return False
