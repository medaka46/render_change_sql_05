from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from typing import Optional
import uvicorn

from database import engine, get_db
import models, schemas
from github_sync import GitHubSync

# Load environment variables from .env file (for local development)
load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(title="GitHub SQLite Sync Demo")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Initialize GitHub sync
github_sync = GitHubSync()

# Root route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Check if GitHub token is configured
    token_available = bool(os.getenv("GITHUB_TOKEN"))
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request,
            "token_available": token_available
        }
    )

# Tasks list route
@app.get("/tasks", response_class=HTMLResponse)
async def list_tasks(
    request: Request,
    db: Session = Depends(get_db),
    message: Optional[str] = None,
    message_type: Optional[str] = None
):
    tasks = db.query(models.Task).all()
    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "tasks": tasks,
            "message": message,
            "message_type": message_type
        }
    )

# Create task route
@app.post("/tasks/create")
async def create_task(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Create new task
    new_task = models.Task(
        title=title,
        description=description,
        is_completed=False
    )
    db.add(new_task)
    db.commit()
    
    return RedirectResponse(
        url="/tasks?message=Task+created+successfully&message_type=success",
        status_code=status.HTTP_303_SEE_OTHER
    )

# Toggle task completion route
@app.get("/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    # Get task
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Toggle completion status
    task.is_completed = not task.is_completed
    db.commit()
    
    return RedirectResponse(
        url="/tasks?message=Task+updated&message_type=success",
        status_code=status.HTTP_303_SEE_OTHER
    )

# Delete task route
@app.get("/tasks/{task_id}/delete")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    # Get task
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete task
    db.delete(task)
    db.commit()
    
    return RedirectResponse(
        url="/tasks?message=Task+deleted&message_type=success",
        status_code=status.HTTP_303_SEE_OTHER
    )

# GitHub sync route
@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    return templates.TemplateResponse(
        "sync.html",
        {"request": request, "result": None}
    )

@app.post("/sync")
async def sync_database(request: Request):
    try:
        # Sync the database with GitHub
        result = await github_sync.sync_database("./app_data.db")
        
        return templates.TemplateResponse(
            "sync.html",
            {"request": request, "result": result}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "sync.html",
            {
                "request": request, 
                "result": {
                    "success": False,
                    "message": f"Error: {str(e)}"
                }
            }
        )

# Run the app
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)