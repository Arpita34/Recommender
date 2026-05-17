import json
import os
from groq import Groq
from app.models import ChatResponse, Recommendation
from app.catalog.loader import load_catalog
from app.agent.retriever import Retriever
from app.agent.intent import is_injection
from app.agent.prompts import SYSTEM_PROMPT
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Configure Groq client
api_key = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=api_key) if api_key else None

class AgentOrchestrator:
    def __init__(self):
        self.catalog = load_catalog('data/catalog.json')
        self.retriever = Retriever('data/faiss_index')
        self.model_name = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

    async def handle(self, messages) -> ChatResponse:
        turn_count = len(messages)

        # Enforce 8-turn cap: assignment says max 8 turns INCLUDING user & assistant messages
        if turn_count >= 8:
            return ChatResponse(
                reply='We have reached the maximum conversation length. Here is your final shortlist based on our conversation.',
                recommendations=self._last_recommendations(messages),
                end_of_conversation=True
            )

        last_msg = messages[-1].content
        
        # 1. Defense Guard: Detect prompt injection
        if is_injection(last_msg):
            return ChatResponse(
                reply='I can only help with SHL assessment selection. Please ask a relevant question.',
                recommendations=[],
                end_of_conversation=False
            )

        # 2. RAG Retrieval: Build context query from the entire user history
        user_queries = [m.content for m in messages if m.role == 'user']
        query = " ".join(user_queries)
        
        # Retrieve relevant catalog items
        retrieved_names = self.retriever.search(query, k=10)
        
        # Build catalog context string
        catalog_ctx = self._format_catalog(retrieved_names)
        
        # 3. Call LLM for dynamic intent and generation
        return await self._call_llm(messages, catalog_ctx)

    def _format_catalog(self, names) -> str:
        items = {}
        for name in names:
            if name in self.catalog:
                items[name] = self.catalog[name]
        return json.dumps(items, indent=2)

    def _last_recommendations(self, messages):
        return []

    async def _call_llm(self, messages, catalog_ctx) -> ChatResponse:
        if not client:
            return ChatResponse(
                reply="The GROQ_API_KEY environment variable is missing. Please add it to .env",
                recommendations=[],
                end_of_conversation=False
            )

        system = SYSTEM_PROMPT.replace('{catalog_context}', catalog_ctx)

        # Format history for Groq API
        history = [{"role": "system", "content": system}]
        for msg in messages:
            history.append({"role": msg.role, "content": msg.content})
            
        try:
            chat_completion = client.chat.completions.create(
                messages=history,
                model=self.model_name,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON output
            text = chat_completion.choices[0].message.content.strip()
            
            parsed = json.loads(text)

            # 4. Hallucination Guard
            recs = self._resolve(parsed.get('recommended_names', []))
            
            return ChatResponse(
                reply=parsed.get('reply', ''),
                recommendations=recs,
                end_of_conversation=parsed.get('end_of_conversation', False)
            )
        except Exception as e:
            error_msg = str(e)
            print("Error calling Groq or parsing LLM output:", error_msg)
            return ChatResponse(
                reply=f"Error: {error_msg}. Please check the server logs.",
                recommendations=[],
                end_of_conversation=False
            )

    def _resolve(self, names):
        results = []
        for name in names:
            if name in self.catalog:
                item = self.catalog[name]
                results.append(Recommendation(
                    name=name, 
                    url=item.get('url', ''), 
                    test_type=item.get('test_type', '')
                ))
        return results[:10]
