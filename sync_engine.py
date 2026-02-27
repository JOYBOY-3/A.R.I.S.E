# =================================================================
#   A.R.I.S.E. - Sync Engine
#   Handles data synchronization between local USB server and cloud
#
#   Architecture:
#     Local USB Server (master) --push--> Cloud Server (replica)
#     Full SQLite database snapshot sync via HTTP API
# =================================================================

import os
import io
import json
import sqlite3
import shutil
import datetime
import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


class SyncEngine:
    """
    Handles database synchronization between local and cloud A.R.I.S.E. servers.
    
    Strategy: Full database snapshot sync.
    - Local server is always the source of truth
    - Cloud receives full DB file when sync is triggered
    - Works even when cloud has ephemeral filesystem (Render.com free tier)
    """
    
    def __init__(self, db_path, cloud_url='', api_key='', is_cloud=False):
        self.db_path = db_path
        self.cloud_url = cloud_url.rstrip('/')
        self.api_key = api_key
        self.is_cloud = is_cloud
        self._auto_sync_thread = None
        self._stop_sync = threading.Event()
    
    def check_internet(self):
        """Check if internet is available by testing connectivity."""
        if not self.cloud_url:
            return False
        try:
            req = urllib.request.Request(
                f"{self.cloud_url}/api/health",
                method='GET'
            )
            req.add_header('User-Agent', 'ARISE-SyncEngine/2.0')
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False
    
    def export_database(self):
        """
        Export the entire SQLite database as binary bytes.
        Uses SQLite backup API for safe, consistent snapshots.
        """
        if not os.path.exists(self.db_path):
            logger.error(f"[SYNC] Database not found: {self.db_path}")
            return None
        
        try:
            # Use SQLite backup API for a consistent snapshot
            source = sqlite3.connect(self.db_path)
            buffer = io.BytesIO()
            
            # Create an in-memory copy using backup API
            dest = sqlite3.connect(':memory:')
            source.backup(dest)
            source.close()
            
            # Now dump the memory DB to bytes
            for line in dest.iterdump():
                buffer.write(f"{line}\n".encode('utf-8'))
            dest.close()
            
            buffer.seek(0)
            data = buffer.read()
            logger.info(f"[SYNC] Database exported: {len(data)} bytes")
            return data
            
        except Exception as e:
            logger.error(f"[SYNC] Export failed: {e}", exc_info=True)
            return None
    
    def export_database_binary(self):
        """Export database as raw binary file (more efficient)."""
        if not os.path.exists(self.db_path):
            return None
        
        try:
            # Make a safe copy first
            temp_path = self.db_path + '.sync_export'
            
            # Use SQLite backup API for consistency
            source = sqlite3.connect(self.db_path)
            dest = sqlite3.connect(temp_path)
            source.backup(dest)
            dest.close()
            source.close()
            
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            # Cleanup temp file
            os.remove(temp_path)
            
            logger.info(f"[SYNC] Database binary exported: {len(data)} bytes ({len(data)/1024:.1f} KB)")
            return data
        except Exception as e:
            logger.error(f"[SYNC] Binary export failed: {e}", exc_info=True)
            return None
    
    def import_database_binary(self, binary_data):
        """
        Import a full database binary snapshot (used by cloud server).
        Replaces the current database with the received snapshot.
        """
        if not binary_data:
            return False
        
        try:
            # Write to temp file first
            temp_path = self.db_path + '.sync_import'
            with open(temp_path, 'wb') as f:
                f.write(binary_data)
            
            # Verify the imported file is a valid SQLite database
            test_conn = sqlite3.connect(temp_path)
            test_conn.execute("SELECT count(*) FROM sqlite_master")
            test_conn.close()
            
            # Backup existing database (if exists)
            if os.path.exists(self.db_path):
                backup_path = self.db_path + '.pre_sync_backup'
                shutil.copy2(self.db_path, backup_path)
            
            # Replace the database
            shutil.move(temp_path, self.db_path)
            
            logger.info(f"[SYNC] Database imported successfully: {len(binary_data)} bytes")
            return True
            
        except Exception as e:
            logger.error(f"[SYNC] Import failed: {e}", exc_info=True)
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    def push_to_cloud(self):
        """
        Push the local database to the cloud server.
        Called from the LOCAL server when internet is available.
        """
        if not self.cloud_url:
            return {"status": "error", "message": "No cloud server URL configured"}
        
        if self.is_cloud:
            return {"status": "error", "message": "Cannot push from cloud server"}
        
        logger.info(f"[SYNC] Starting push to cloud: {self.cloud_url}")
        
        # Check internet first
        if not self.check_internet():
            return {"status": "offline", "message": "Cloud server unreachable"}
        
        # Export database
        db_data = self.export_database_binary()
        if not db_data:
            return {"status": "error", "message": "Failed to export database"}
        
        try:
            import base64
            
            # Prepare the sync payload
            payload = json.dumps({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "db_size": len(db_data),
                "db_data": base64.b64encode(db_data).decode('ascii'),
                "source": "local"
            }).encode('utf-8')
            
            # Send to cloud
            req = urllib.request.Request(
                f"{self.cloud_url}/api/sync/receive",
                data=payload,
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')
            req.add_header('X-Sync-API-Key', self.api_key)
            req.add_header('User-Agent', 'ARISE-SyncEngine/2.0')
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            logger.info(f"[SYNC] Push complete - Cloud response: {result.get('status', 'unknown')}")
            return {
                "status": "success",
                "message": f"Database synced to cloud ({len(db_data)} bytes)",
                "cloud_response": result
            }
            
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8', errors='replace')
            logger.error(f"[SYNC] Push failed - HTTP {e.code}: {error_msg}")
            return {"status": "error", "message": f"Cloud returned HTTP {e.code}: {error_msg}"}
        except Exception as e:
            logger.error(f"[SYNC] Push failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def get_sync_status(self):
        """Get current sync status information."""
        db_exists = os.path.exists(self.db_path)
        db_size = os.path.getsize(self.db_path) if db_exists else 0
        
        status = {
            "node_type": "cloud" if self.is_cloud else "local",
            "database_exists": db_exists,
            "database_size_bytes": db_size,
            "database_size_human": f"{db_size/1024:.1f} KB",
            "cloud_url": self.cloud_url or "not configured",
            "auto_sync": self._auto_sync_thread is not None and self._auto_sync_thread.is_alive()
        }
        
        if not self.is_cloud and self.cloud_url:
            status["cloud_reachable"] = self.check_internet()
        
        return status
    
    def start_auto_sync(self, interval_seconds=300):
        """Start automatic background sync at the given interval."""
        if self.is_cloud:
            logger.info("[SYNC] Auto-sync not needed on cloud server")
            return
        
        if not self.cloud_url:
            logger.warning("[SYNC] Cannot start auto-sync: no cloud URL configured")
            return
        
        if self._auto_sync_thread and self._auto_sync_thread.is_alive():
            logger.info("[SYNC] Auto-sync already running")
            return
        
        self._stop_sync.clear()
        
        def _sync_loop():
            logger.info(f"[SYNC] Auto-sync started (interval: {interval_seconds}s)")
            while not self._stop_sync.is_set():
                try:
                    if self.check_internet():
                        result = self.push_to_cloud()
                        logger.info(f"[SYNC] Auto-sync result: {result.get('status')}")
                    else:
                        logger.debug("[SYNC] Auto-sync skipped - offline")
                except Exception as e:
                    logger.error(f"[SYNC] Auto-sync error: {e}")
                
                # Wait for interval or until stopped
                self._stop_sync.wait(interval_seconds)
            
            logger.info("[SYNC] Auto-sync stopped")
        
        self._auto_sync_thread = threading.Thread(target=_sync_loop, daemon=True)
        self._auto_sync_thread.start()
    
    def stop_auto_sync(self):
        """Stop automatic background sync."""
        self._stop_sync.set()
        if self._auto_sync_thread:
            self._auto_sync_thread.join(timeout=5)
        logger.info("[SYNC] Auto-sync stopped")
