from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.models import ChatRequest, ChatResponse
from app.agent.orchestrator import AgentOrchestrator
import os

# The brain of our application
orchestrator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    print("Application Startup: Loading catalog and FAISS index into Orchestrator...")
    orchestrator = AgentOrchestrator()
    yield
    print("Application Shutdown.")

app = FastAPI(title='SHL Assessment Recommender', lifespan=lifespan)

# Allow the local HTML file and any frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/', response_class=FileResponse)
def root():
    """Landing page."""
    return FileResponse(os.path.join(os.path.dirname(__file__), '..', 'landing.html'))

@app.get('/app', response_class=FileResponse)
def chat_ui():
    """Serve the chat advisor UI."""
    return FileResponse(os.path.join(os.path.dirname(__file__), '..', 'chat_test.html'))

@app.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not orchestrator:
        return ChatResponse(reply="Service starting up...", recommendations=[])
    
    # Hand off the payload directly to the AI
    return await orchestrator.handle(request.messages)
