from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.models import ChatRequest, ChatResponse
from app.agent.orchestrator import AgentOrchestrator

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

@app.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not orchestrator:
        return ChatResponse(reply="Service starting up...", recommendations=[])
    
    # Hand off the payload directly to the AI
    return await orchestrator.handle(request.messages)
