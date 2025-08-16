from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class BackupSnapshotSummary(BaseModel):
    backup_start: str = Field(..., description="Backup start time", example="2025-08-13T08:30:32.081825223Z")
    backup_end: str = Field(..., description="Backup end time", example="2025-08-13T08:30:32.817532575Z")
    files_new: int = Field(..., description="Number of new files", example=0)
    files_changed: int = Field(..., description="Number of changed files", example=0)
    files_unmodified: int = Field(..., description="Number of unmodified files", example=3471)
    dirs_new: int = Field(..., description="Number of new directories", example=0)
    dirs_changed: int = Field(..., description="Number of changed directories", example=0)
    dirs_unmodified: int = Field(..., description="Number of unmodified directories", example=357)
    data_blobs: int = Field(..., description="Number of data blobs", example=0)
    tree_blobs: int = Field(..., description="Number of tree blobs", example=0)
    data_added: int = Field(..., description="Data added in bytes", example=0)
    data_added_packed: int = Field(..., description="Packed data added in bytes", example=0)
    total_files_processed: int = Field(..., description="Total files processed", example=3471)
    total_bytes_processed: int = Field(..., description="Total bytes processed", example=255549458)

class BackupSnapshot(BaseModel):
    time: str = Field(..., description="Snapshot creation time", example="2025-08-13T08:30:32.081825223Z")
    parent: Optional[str] = Field(None, description="Parent snapshot ID", example="604ac31654021f426a9ab702ada8ab608d001c870681d648aed733fbf0df5e57")
    tree: str = Field(..., description="Tree hash", example="39911524fc59687d401bced629acf9892cfa63a41dbf27dc055a1a25ad9d2721")
    paths: List[str] = Field(..., description="Paths included in the snapshot", example=["/wp_bl0zt_mysql_data", "/wp_bl0zt_wordpress"])
    hostname: str = Field(..., description="Hostname of the backup", example="websoft9-backup-host")
    username: str = Field(..., description="Username of the backup creator", example="root")
    tags: List[str] = Field(..., description="Tags associated with the snapshot", example=["wp_bl0zt"])
    program_version: str = Field(..., description="Restic program version", example="restic 0.18.0")
    summary: BackupSnapshotSummary = Field(..., description="Summary of the snapshot")
    id: str = Field(..., description="Snapshot ID", example="2b1112d4a102b501c45fbbd39a5467e58036d23eaac54bfc6b8ed2284d61a609")
    short_id: str = Field(..., description="Shortened snapshot ID", example="2b1112d4")
