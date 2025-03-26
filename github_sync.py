import os
import httpx
import base64
import tempfile
import shutil
from pathlib import Path
from fastapi import HTTPException

class GitHubSync:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.owner = os.getenv("GITHUB_REPO_OWNER")
        self.repo = os.getenv("GITHUB_REPO_NAME")
        self.branch = os.getenv("GITHUB_BRANCH", "main")
        self.db_path = os.getenv("GITHUB_DB_PATH", "database.db")
        
        # Validate required environment variables
        if not all([self.token, self.owner, self.repo]):
            raise ValueError("Missing required environment variables for GitHub sync")
    
    async def _get_file_sha(self):
        """Get the current SHA of the database file in GitHub."""
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.db_path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        params = {"ref": self.branch}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json().get("sha")
        elif response.status_code == 404:
            # File doesn't exist yet
            return None
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
    
    async def download_db(self, target_path):
        """Download database from GitHub to a local path."""
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.db_path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        params = {"ref": self.branch}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            # Decode content
            content_data = response.json()
            if content_data.get("encoding") == "base64":
                file_content = base64.b64decode(content_data.get("content"))
                
                # Write to target path
                with open(target_path, "wb") as f:
                    f.write(file_content)
                
                return True
        elif response.status_code == 404:
            # File doesn't exist yet - return False but don't raise an exception
            return False
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
    
    async def upload_db(self, source_path):
        """Upload database from local path to GitHub."""
        # Read the database file
        with open(source_path, "rb") as f:
            content = f.read()
        
        # Encode content as base64
        encoded_content = base64.b64encode(content).decode("utf-8")
        
        # Get current file SHA (if it exists)
        sha = await self._get_file_sha()
        
        # Prepare the API request
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.db_path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Prepare the request body
        data = {
            "message": "Update database",
            "content": encoded_content,
            "branch": self.branch
        }
        
        # If the file already exists, include the SHA
        if sha:
            data["sha"] = sha
        
        # Send the request
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=data)
        
        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to upload database: {response.text}"
            )
        
        return response.json()
    
    async def sync_database(self, local_db_path):
        """Synchronize the local database with GitHub."""
        # Create a temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Define temp paths
            temp_db_path = Path(temp_dir) / "temp_db.db"
            
            # First try to download the current database from GitHub
            downloaded = await self.download_db(temp_db_path)
            
            if downloaded:
                # Compare with local database
                # For now, we'll just overwrite GitHub with our version
                # In a real app, you might want to merge changes
                pass
            
            # Upload our database to GitHub
            result = await self.upload_db(local_db_path)
            
            return {
                "success": True,
                "message": "Database synced with GitHub successfully",
                "commit": result.get("commit", {}).get("html_url", "")
            }