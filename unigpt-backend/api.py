from fastapi import FastAPI, UploadFile, File
import os
import shutil
from pathlib import Path
from pdf_parsing import process_pdf  # Import your existing function
from utils import make_output, modify_output  # Import the functions from utils.py
from sse_starlette.sse import EventSourceResponse  # Correct import for SSE
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel

app = FastAPI()

# Allow cross-origin requests from Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Update with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

class PDFResponse(BaseModel):
    summary: str

@app.post("/upload_pdf/", response_model=PDFResponse)
async def upload_pdf(file: UploadFile = File(...)):
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=422, 
            detail="Only PDF files are allowed"
        )

    # Validate file size (10MB max)
    max_size = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=422,
            detail="File size exceeds 10MB limit"
        )
    
    # Reset file cursor after reading
    await file.seek(0)
    
    try:
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        summary = process_pdf(str(file_path))
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"PDF processing failed: {str(e)}"
        )

class QueryRequest(BaseModel):
    query: str
    use_groq: bool = True

@app.post("/generate_output/")
async def generate_output(request: QueryRequest):
    try:
        response = make_output(request.query, request.use_groq)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate_output_stream/")
async def generate_output_stream(query: str, use_groq: bool = True):
    def event_generator():
        # Use make_output to generate a response
        response = make_output(query, use_groq)
        
        # Modify output by adding spaces with a delay (optional)
        for word in modify_output(response):
            yield f"{word} "
    
    return EventSourceResponse(event_generator())
