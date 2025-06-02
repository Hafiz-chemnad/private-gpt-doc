from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
import shutil
import uuid
from typing import List, Dict, Any, Optional, Annotated, Union
import datetime
from fastapi.staticfiles import StaticFiles 

# Imports for Authentication
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

# Add the directory containing privateGPT.py and ingest.py to the Python path
sys.path.append(os.path.dirname(__file__))

# Import the core query function from your refactored privateGPT.py
from privateGPT import get_answer_from_privateGPT

# Import the core ingestion function from your refactored ingest.py
from ingest import ingest_documents

# Import constants from your constants.py
from constants import SOURCE_DIRECTORY, PERSIST_DIRECTORY

# Import config.py for authentication secrets and admin credentials
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, ADMIN_USERNAME, ADMIN_HASHED_PASSWORD, pwd_context


app = FastAPI()

# --- In-memory dictionary to track ingestion task statuses ---
ingestion_tasks_status: Dict[str, Dict[str, Any]] = {}

# Define possible task states as constants for clarity and consistency
TASK_STATUS_PENDING = "PENDING"
TASK_STATUS_IN_PROGRESS = "IN_PROGRESS"
TASK_STATUS_COMPLETED = "COMPLETED"
TASK_STATUS_FAILED = "FAILED"

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for API Request/Response Validation ---
class QueryRequest(BaseModel):
    """Defines the expected structure for a query request from the frontend."""
    query: str

class QueryResponse(BaseModel):
    """Defines the expected structure for a query response to the frontend."""
    answer: str
    source_documents: List[Dict[str, Any]]

class FileStatus(BaseModel):
    """Defines the status structure for an individual file within an ingestion task."""
    filename: str
    status: str

class UploadResponse(BaseModel):
    """Defines the response structure for a file upload request."""
    message: str
    task_id: str
    filenames: List[str]

class IngestionStatusResponse(BaseModel):
    """Defines the response structure for an ingestion status request."""
    task_id: str
    status: str
    files: List[FileStatus]


# --- Authentication Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: str
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str


# --- Authentication Utilities ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_user(username: str):
    if username == ADMIN_USERNAME:
        return UserInDB(username=ADMIN_USERNAME, hashed_password=ADMIN_HASHED_PASSWORD)
    return None

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Union[datetime.timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


# --- API Endpoints ---

@app.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    Authenticates a user and returns an access token if credentials are valid.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/health")
async def health_check():
    """
    Basic health check endpoint to confirm the API is running.
    Returns a simple status message.
    """
    return {"status": "ok", "message": "PrivateGPT API is running."}

@app.post("/query", response_model=QueryResponse)
async def query_llm_endpoint(request: QueryRequest):
    """
    Endpoint to receive a user query and return an answer from the PrivateGPT model.
    It calls the `get_answer_from_privateGPT` function from `privateGPT.py`.
    """
    print(f"API: Received query: '{request.query}'")
    try:
        response_data = get_answer_from_privateGPT(request.query)

        if not isinstance(response_data, dict) or "answer" not in response_data:
            raise HTTPException(
                status_code=500,
                detail="Invalid response format from PrivateGPT query function. 'answer' key missing."
            )
        
        response_data.setdefault("source_documents", [])

        print("API: Successfully processed query.")
        return JSONResponse(content=response_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"API: Unhandled error in /query endpoint: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error processing query: {e}"
        )

@app.post("/upload_and_ingest", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_ingest_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)], # MOVED THIS FIRST
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Endpoint to handle document uploads and trigger their ingestion into the vector store.
    Files are saved to `SOURCE_DIRECTORY` and then processed by `ingest.py` in the background.
    This endpoint is now protected and requires authentication.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded.")

    task_id = str(uuid.uuid4())
    
    ingestion_tasks_status[task_id] = {
        "overall_status": TASK_STATUS_IN_PROGRESS,
        "files": []
    }

    uploaded_filenames = []
    saved_file_paths = []

    try:
        os.makedirs(SOURCE_DIRECTORY, exist_ok=True)
        print(f"API: Saving {len(files)} uploaded file(s) to {SOURCE_DIRECTORY} for task {task_id}...")

        for file in files:
            original_filename = file.filename
            
            name_without_ext, ext = os.path.splitext(original_filename)
            unique_filename = f"{name_without_ext}_{uuid.uuid4().hex[:8]}{ext}"
            
            file_location = os.path.join(SOURCE_DIRECTORY, unique_filename)
            
            ingestion_tasks_status[task_id]["files"].append({
                "filename": original_filename,
                "status": TASK_STATUS_PENDING
            })
            uploaded_filenames.append(original_filename)

            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            saved_file_paths.append(file_location)

            print(f"API: Saved '{original_filename}' as '{unique_filename}' for task {task_id}")

        print(f"API: All files for task {task_id} saved. Triggering ingestion in background.")

        background_tasks.add_task(ingest_documents_wrapper, saved_file_paths, task_id)

        return JSONResponse(
            content={
                "message": f"Files uploaded. Ingestion started in background.",
                "filenames": uploaded_filenames,
                "task_id": task_id
            },
            status_code=status.HTTP_202_ACCEPTED
        )
    except Exception as e:
        print(f"API: Error during file upload or ingestion setup for task {task_id}: {e}", file=sys.stderr)
        if task_id in ingestion_tasks_status:
            ingestion_tasks_status[task_id]["overall_status"] = TASK_STATUS_FAILED
            for file_entry in ingestion_tasks_status[task_id]["files"]:
                file_entry["status"] = TASK_STATUS_FAILED
        
        for fpath in saved_file_paths:
            if os.path.exists(fpath):
                os.remove(fpath)
                print(f"API: Cleaned up partially saved file: {fpath}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process files for ingestion: {e}"
        )

# Wrapper function for ingest_documents to handle status updates.
def ingest_documents_wrapper(saved_file_paths: List[str], task_id: str):
    print(f"API: Background task {task_id}: Starting ingestion process for {len(saved_file_paths)} files.")
    
    if task_id in ingestion_tasks_status:
        for file_entry in ingestion_tasks_status[task_id]["files"]:
            file_entry["status"] = TASK_STATUS_IN_PROGRESS
        ingestion_tasks_status[task_id]["overall_status"] = TASK_STATUS_IN_PROGRESS

    try:
        ingestion_result = ingest_documents() 

        if "error" in ingestion_result:
            if task_id in ingestion_tasks_status:
                ingestion_tasks_status[task_id]["overall_status"] = TASK_STATUS_FAILED
                for file_entry in ingestion_tasks_status[task_id]["files"]:
                    file_entry["status"] = TASK_STATUS_FAILED
            print(f"API: Background task {task_id}: Ingestion FAILED with error: {ingestion_result['error']}", file=sys.stderr)
        else:
            if task_id in ingestion_tasks_status:
                ingestion_tasks_status[task_id]["overall_status"] = TASK_STATUS_COMPLETED
                for file_entry in ingestion_tasks_status[task_id]["files"]:
                    file_entry["status"] = TASK_STATUS_COMPLETED
            print(f"API: Background task {task_id}: Ingestion COMPLETED successfully for all files.")

    except Exception as e:
        print(f"API: Background task {task_id}: An unexpected error occurred during ingestion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

        if task_id in ingestion_tasks_status:
            ingestion_tasks_status[task_id]["overall_status"] = TASK_STATUS_FAILED
            for file_entry in ingestion_tasks_status[task_id]["files"]:
                file_entry["status"] = TASK_STATUS_FAILED
            print(f"API: Background task {task_id}: Ingestion FAILED for all files due to an unhandled exception.")
    
    finally:
        pass


@app.get("/ingestion_status/{task_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status_endpoint(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)] # MOVED THIS FIRST
):
    """
    Endpoint to check the detailed status of a background ingestion task.
    Returns the overall task status and the status of each individual file.
    This endpoint is now protected and requires authentication.
    """
    task_info = ingestion_tasks_status.get(task_id)
    if task_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task ID not found.")
    
    files_status_list = [FileStatus(filename=f["filename"], status=f["status"]) for f in task_info["files"]]

    return IngestionStatusResponse(
        task_id=task_id,
        status=task_info["overall_status"],
        files=files_status_list
    )

@app.delete("/delete_document/{filename}", status_code=status.HTTP_200_OK)
async def delete_document_endpoint(
    filename: str, 
    current_user: Annotated[User, Depends(get_current_active_user)], # MOVED THIS FIRST
    background_tasks: BackgroundTasks
):
    """
    Endpoint to delete a document from the SOURCE_DIRECTORY and trigger re-ingestion.
    The filename should be the original filename of the document.
    This endpoint is now protected and requires authentication.
    """
    print(f"API: Received request to delete document: '{filename}'")
    
    file_to_delete_path = None
    
    print(f"API: Contents of SOURCE_DIRECTORY ({SOURCE_DIRECTORY}): {os.listdir(SOURCE_DIRECTORY)}")

    original_name_base, original_name_ext = os.path.splitext(filename)

    for f_on_disk in os.listdir(SOURCE_DIRECTORY):
        file_on_disk_base, file_on_disk_ext = os.path.splitext(f_on_disk)

        if file_on_disk_ext == original_name_ext and file_on_disk_base.startswith(original_name_base):
            file_to_delete_path = os.path.join(SOURCE_DIRECTORY, f_on_disk)
            print(f"API: Found matching file on disk: '{file_to_delete_path}' for original filename '{filename}'")
            break

    if not file_to_delete_path:
        print(f"API: Document '{filename}' NOT found in source directory after checking all files.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{filename}' not found in source directory."
        )

    try:
        os.remove(file_to_delete_path)
        print(f"API: Successfully deleted file from source directory: {file_to_delete_path}")

        background_tasks.add_task(ingest_documents_after_delete_wrapper)

        return JSONResponse(
            content={"message": f"Document '{filename}' deleted and re-ingestion triggered."},
            status_code=status.HTTP_200_OK
        )

    except OSError as e:
        print(f"API: Error deleting file '{filename}': {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document '{filename}': {e}"
        )
    except Exception as e:
        print(f"API: An unexpected error occurred during deletion or re-ingestion trigger: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during deletion of '{filename}': {e}"
        )

# Wrapper function for ingest_documents after a delete operation
def ingest_documents_after_delete_wrapper():
    """
    A wrapper to trigger ingest_documents after a file deletion.
    This ensures the vector store is updated to reflect the deletion.
    """
    print("API: Background task: Re-ingestion triggered after document deletion.")
    try:
        ingestion_result = ingest_documents()
        if "error" in ingestion_result:
            print(f"API: Re-ingestion after delete FAILED: {ingestion_result['error']}", file=sys.stderr)
        else:
            print("API: Re-ingestion after delete COMPLETED successfully.")
    except Exception as e:
        print(f"API: An unexpected error occurred during re-ingestion after delete: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

@app.get("/list_documents")
async def list_documents_endpoint(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Endpoint to list all documents currently in the SOURCE_DIRECTORY.
    This endpoint is protected and requires authentication.
    """
    print("API: Received request to list documents.")
    try:
        if not os.path.exists(SOURCE_DIRECTORY):
            print(f"API: SOURCE_DIRECTORY '{SOURCE_DIRECTORY}' does not exist.")
            return JSONResponse(content=[], status_code=status.HTTP_200_OK)

        files_on_disk = os.listdir(SOURCE_DIRECTORY)
        document_filenames = []
        for f_on_disk in files_on_disk:
            if f_on_disk.startswith('.') or f_on_disk.startswith('~$'):
                continue
            
            parts = os.path.splitext(f_on_disk)
            base_name = parts[0]
            extension = parts[1]
            
            if len(base_name) > 9 and base_name[-9] == '_' and all(c in '0123456789abcdefABCDEF' for c in base_name[-8:]):
                original_name = base_name[:-9] + extension
            else:
                original_name = f_on_disk

            document_filenames.append(original_name)
        
        print(f"API: Listed {len(document_filenames)} documents.")
        return JSONResponse(content=document_filenames, status_code=status.HTTP_200_OK)
    except Exception as e:
        print(f"API: Error listing documents: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {e}"
        )

@app.get("/")
async def read_root():
    """
    Redirects the root URL to the chat interface.
    """
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/index.html")

@app.get("/admin")
async def serve_admin_page(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Serves the admin HTML page.
    Requires authentication to access.
    """
    from fastapi.responses import FileResponse
    admin_html_path = os.path.join("frontend", "admin.html")
    if not os.path.exists(admin_html_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin page not found.")
    return FileResponse(admin_html_path)
# --- Main entry point for running the FastAPI app with Uvicorn ---
if __name__ == "__main__":
    print("Starting FastAPI server...")
    print(f"API will listen on http://127.0.0.1:8000")
    print(f"Source documents will be saved in: {SOURCE_DIRECTORY}")
    print(f"ChromaDB will persist in: {PERSIST_DIRECTORY}")
    uvicorn.run(app, host="127.0.0.1", port=8000)