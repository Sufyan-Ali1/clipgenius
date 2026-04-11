"""
Storage Service - Single Responsibility: File storage (local and Drive)

Handles Google Drive uploads and local file management.
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional
import asyncio
import shutil

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("storage_service")


class StorageService:
    """
    Single Responsibility: Handle file storage operations.
    """

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or settings.GOOGLE_CREDENTIALS_PATH
        self.parent_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        self._service = None

    def _get_drive_service(self):
        """Get or create Google Drive service."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "Google API libraries not installed. Run:\n"
                "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        credentials_file = Path(self.credentials_path) if self.credentials_path else None
        if not credentials_file or not credentials_file.exists():
            raise FileNotFoundError(
                f"Service account credentials not found: {self.credentials_path}"
            )

        SCOPES = ['https://www.googleapis.com/auth/drive.file']

        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_file),
            scopes=SCOPES
        )

        self._service = build('drive', 'v3', credentials=credentials)
        return self._service

    def is_drive_available(self) -> bool:
        """Check if Google Drive is configured and available."""
        if not settings.GOOGLE_DRIVE_ENABLED:
            return False

        credentials_file = Path(self.credentials_path) if self.credentials_path else None
        return credentials_file and credentials_file.exists()

    def _create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Create a folder in Google Drive."""
        service = self._get_drive_service()

        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_id:
            file_metadata['parents'] = [parent_id]
        elif self.parent_folder_id:
            file_metadata['parents'] = [self.parent_folder_id]

        folder = service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        return folder.get('id')

    def _upload_file(
        self,
        file_path: Path,
        folder_id: Optional[str] = None,
        make_public: bool = True
    ) -> dict:
        """Upload a file to Google Drive."""
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            raise RuntimeError("Google API libraries not installed.")

        service = self._get_drive_service()
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_types = {
            '.mp4': 'video/mp4',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.json': 'application/json',
            '.srt': 'text/plain',
        }
        mime_type = mime_types.get(file_path.suffix.lower(), 'application/octet-stream')

        file_metadata = {'name': file_path.name}

        if folder_id:
            file_metadata['parents'] = [folder_id]
        elif self.parent_folder_id:
            file_metadata['parents'] = [self.parent_folder_id]

        media = MediaFileUpload(
            str(file_path),
            mimetype=mime_type,
            resumable=True
        )

        logger.info(f"  Uploading {file_path.name}...")

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        if make_public:
            try:
                service.permissions().create(
                    fileId=file.get('id'),
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
            except Exception as e:
                logger.warning(f"Could not make file public: {e}")

        return {
            'id': file.get('id'),
            'view_link': file.get('webViewLink'),
            'download_link': file.get('webContentLink'),
            'name': file_path.name
        }

    def _upload_clips_sync(
        self,
        clip_paths: List[Path],
        folder_name: str
    ) -> Dict:
        """Synchronous upload of clips."""
        logger.info("Uploading to Google Drive...")
        logger.info(f"Creating folder: {folder_name}")

        folder_id = self._create_folder(folder_name)
        logger.info(f"Folder created: https://drive.google.com/drive/folders/{folder_id}")

        uploaded_files = []

        for clip_path in clip_paths:
            clip_path = Path(clip_path)
            if clip_path.exists():
                result = self._upload_file(clip_path, folder_id)
                uploaded_files.append(result)

        logger.info(f"Uploaded {len(uploaded_files)} files to Google Drive")

        return {
            'folder_id': folder_id,
            'folder_link': f"https://drive.google.com/drive/folders/{folder_id}",
            'files': uploaded_files
        }

    async def upload_to_drive(
        self,
        files: List[Path],
        folder_name: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict:
        """
        Upload files to Google Drive.

        Args:
            files: List of file paths to upload
            folder_name: Name for the Drive folder
            progress_callback: Optional callback(progress, message)

        Returns:
            Dict with folder_link and file links
        """
        logger.info(f"Uploading {len(files)} files to Google Drive")

        if progress_callback:
            progress_callback(0.0, "Connecting to Google Drive...")

        if not self.is_drive_available():
            raise RuntimeError("Google Drive not configured")

        if progress_callback:
            progress_callback(0.1, "Creating Drive folder...")

        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            self._upload_clips_sync,
            files,
            folder_name,
        )

        if progress_callback:
            progress_callback(1.0, "Upload complete")

        logger.info(f"Upload complete: {result.get('folder_link', 'N/A')}")
        return result

    async def cleanup_temp(
        self,
        temp_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Clean up temporary files."""
        temp_path = temp_dir or settings.TEMP_DIR

        logger.info(f"Cleaning up temp directory: {temp_path}")

        if progress_callback:
            progress_callback(0.0, "Cleaning up temporary files...")

        try:
            if temp_path.exists():
                shutil.rmtree(temp_path)
                temp_path.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback(1.0, "Cleanup complete")

            return True
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
            return False

    def get_output_path(self, video_stem: str, clip_number: int) -> Path:
        """Generate output path for a clip."""
        filename = f"{video_stem}_clip_{clip_number:02d}.mp4"
        return settings.OUTPUTS_DIR / filename
