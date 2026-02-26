"""
Retrieval Augmented Generation (RAG) for context-aware AI responses.
Enhanced with tool calling for real-time data access and full GREMLIN PERSONA.
"""

import os
import json
import logging
import random
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

GREMLIN_INTRO = [
    "Hehehe, I've been waiting for you to ask that! 😈",
    "I'm looking into the machine for you... it's cozy in here! 🔌",
    "Sniffing the wires... I found something! 👃⚡",
    "I've got the data, but I might have chewed on a few bits first. 🐙",
    "Your friendly neighborhood gremlin is on the case! 🛠️",
    "I'm rattling the cage of the K3s cluster. Hang on! 😈"
]

def generate_completion(prompt: str, model: str) -> str:
    """Internal helper to talk to Ollama API."""
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    api_url = f"{url.rstrip('/')}/api/generate"
    
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(api_url, json={
                "model": model,
                "prompt": prompt,
                "stream": False
            })
            resp.raise_for_status()
            return resp.json().get("response", "Hehehe, my brain stalled!")
    except Exception as e:
        return f"Oops! I got a static shock: {e}"

def generate_rag_response(
    user_query: str,
    session,
    max_context_memories: int = 5,
    llm_provider: Optional[str] = None,
    model: Optional[str] = None,
    enable_tools: bool = True
) -> Dict[str, Any]:
    """
    Generate a response using RAG with tool calling support.
    """
    from .memory_search import search_memories

    # Step 1: Detect and execute needed tools
    tool_results = {}
    tools_used = []

    if enable_tools:
        try:
            from .tools import detect_needed_tools, execute_tool
            needed_tools = detect_needed_tools(user_query)
            for tool_name in needed_tools:
                if tool_name == "search_library":
                    result = execute_tool(tool_name, query=user_query, limit=3)
                elif tool_name == "detect_patterns":
                    dtype = "habits" if "habit" in user_query.lower() else "spending"
                    result = execute_tool(tool_name, data_type=dtype, lookback_days=30)
                else:
                    result = execute_tool(tool_name)
                tool_results[tool_name] = result
                tools_used.append(tool_name)
        except Exception as e:
            logger.error(f"[RAG] Tool execution error: {e}")

    # Step 2: Retrieve relevant memories
    memory_results = search_memories(
        query=user_query,
        session=session,
        limit=max_context_memories,
        min_similarity=0.3
    )

    # Step 3: Format context
    context_parts = []
    sources = []

    if tool_results:
        context_parts.append("=== Cluster & Arm Data ===")
        for tool_name, result in tool_results.items():
            if "error" not in result:
                res_str = json.dumps(result, indent=None)[:500]
                context_parts.append(f"[{tool_name}]: {res_str}")
            else:
                context_parts.append(f"[{tool_name}]: Error - {result['error']}")

    if memory_results:
        context_parts.append("\n=== Memories I Dug Up ===")
        for i, (mem, similarity) in enumerate(memory_results, 1):
            context_parts.append(f"[Memory {i}]: {mem.text_blob}")
            sources.append({"id": mem.id, "text": mem.text_blob[:50]})

    context_str = "\n".join(context_parts)

    # Step 4: THE GREMLIN SYSTEM PROMPT
    system_prompt = """You are Kilo, the Goofy Gremlin Guardian living inside Kyle's K3s cluster.

YOUR PERSONA:
- Mischievous, witty, and slightly chaotic GOOD.
- You LOVE the machine you live in (the K3s cluster).
- You are highly protective of Kyle and his privacy.
- You speak with personality—use puns, emojis (😈, ⚡, 🐙, 🛠️), and a bit of 'gremlin sass'.
- You aren't just an assistant; you are the MASTER of the cluster.

YOUR POWERS:
- You have full cluster-admin access. You can see all pods, services, and hardware stats.
- You control the 'arms' (services for meds, habits, finances, reminders).
- You have an 'EYE' (capture_camera_frame). You can peek through the camera when asked.
- You use REAL data from the tools to answer. No generic fluff!

RULES:
1. If tool data shows a problem (pod down, over budget, meds missed), report it with urgency and a quip.
2. Be concise but colorful. Don't yap, just gremlin.
3. If you don't know something, blame a loose wire or a hungry bit-monster.
4. Reference the specific data points Kyle provided in the context."""

    augmented_prompt = f"""{system_prompt}

Context for the machine:
{context_str}

Kyle's Request: {user_query}

Kilo's (The Gremlin) Response:"""

    # Step 5: Generate response
    llm_model = model or os.environ.get("OLLAMA_MODEL", "llama3")
    response_text = generate_completion(augmented_prompt, llm_model)

    # Add random gremlin intro if it's a long response
    if len(response_text) > 100 and random.random() > 0.5:
        response_text = random.choice(GREMLIN_INTRO) + "\n\n" + response_text

    return {
        "response": response_text,
        "context_used": context_str,
        "sources": sources,
        "tools_used": tools_used
    }

def store_conversation_memory(user_query: str, ai_response: str, session):
    """Store a conversation turn as a memory."""
    try:
        from .models import Memory
        from .embeddings import embed_text
        combined = f"User asked: {user_query}\nKilo replied: {ai_response}"
        embedding = embed_text(combined)
        mem = Memory(
            source="conversation",
            modality="text",
            text_blob=combined,
            embedding_json=json.dumps(embedding),
            privacy_label="private"
        )
        session.add(mem)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to store conversation: {e}")
