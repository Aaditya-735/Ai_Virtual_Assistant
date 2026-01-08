# chatbot.py
"""
Standalone Chatbot client that:
- Uses Groq for streaming LLM completions (if Groq API key is present)
- Imports and uses JarvisModel from model.py for classification/routing (model.py is NOT included here)
- For 'automation' queries returns the model's structured action WITHOUT executing it
- For other queries calls Groq and streams/parses responses defensively
- Persists only user/assistant turns to Data/ChatLog.json
"""

from groq import Groq
from json import load, dump
from pathlib import Path
import datetime
from dotenv import dotenv_values
from typing import List, Dict, Any, Optional
import logging

# Logging
LOG = logging.getLogger("chatbot")
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
LOG.addHandler(handler)

# Try to import user's model (do NOT show or modify model.py here)
try:
    from Model import JarvisModel  # model.py must define JarvisModel
except Exception:
    JarvisModel = None

# Load env
env = dotenv_values(".env")
ASSISTANT_NAME = env.get("Assistantname", "Jarvis")
GROQ_API_KEY = env.get("GroqAPIKey")

# Initialize Groq client if possible
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        LOG.warning("Could not initialize Groq client: %s", e)
        client = None

# Data file setup
DATA_DIR = Path("Data")
CHATLOG_PATH = DATA_DIR / "ChatLog.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
if not CHATLOG_PATH.exists():
    with CHATLOG_PATH.open("w", encoding="utf-8") as f:
        dump([], f)

# System prompt
SYSTEM_PROMPT = (
    f"You are a very accurate and advanced AI chatbot named {ASSISTANT_NAME}, which has "
    "real-time, up-to-date information from the internet.\n"
    "*** Do not tell time until I ask, do not talk too much, just answer the question.***\n"
    "*** Reply only in English, even if the question is in Hindi, reply in English.***\n"
    "*** Do not provide notes in the output, just answer the question and never mention your training data. ***"
)
SYSTEM_MESSAGE = [{"role": "system", "content": SYSTEM_PROMPT}]

# Instantiate model if available
_model = JarvisModel() if JarvisModel is not None else None


def _realtime_info() -> str:
    now = datetime.datetime.now()
    return (
        "Please use this real-time information if needed,\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H')} hours :{now.strftime('%M')} minutes :{now.strftime('%S')} seconds.\n"
    )


def _answer_modifier(answer: str) -> str:
    lines = answer.splitlines()
    non_empty = [line.rstrip() for line in lines if line.strip()]
    return "\n".join(non_empty).strip()


def _load_chatlog() -> List[Dict[str, Any]]:
    try:
        with CHATLOG_PATH.open("r", encoding="utf-8") as f:
            data = load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_chatlog(messages: List[Dict[str, Any]]) -> None:
    try:
        with CHATLOG_PATH.open("w", encoding="utf-8") as f:
            dump(messages, f, indent=4, ensure_ascii=False)
    except Exception as e:
        LOG.warning("Failed to save chat log: %s", e)


from typing import Tuple

def _call_groq_stream(messages_payload: List[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """Call Groq streaming API defensively. Returns (answer, error_message)."""
    if client is None:
        return ("", "Groq client not configured")

    answer = ""
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            max_tokens=1024,
            temperature=0.7,
            top_p=1,
            stream=True,
            stop=None,
        )
    except Exception as e:
        LOG.exception("Failed to start Groq request")
        return ("", str(e))

    try:
        for chunk in completion:
            # Defensive parsing: support SDKs that return objects or dicts
            try:
                choices = getattr(chunk, "choices", None) or (chunk.get("choices") if isinstance(chunk, dict) else [])
                if not choices:
                    continue
                first = choices[0]
                delta = getattr(first, "delta", None) or (first.get("delta") if isinstance(first, dict) else {})
                content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
                if content:
                    answer += content
            except Exception:
                # ignore malformed chunk and continue
                continue
    except Exception as e:
        LOG.exception("Streaming error")
        return (_answer_modifier(answer), str(e))

    answer = answer.replace("</s>", "").strip()
    return (_answer_modifier(answer), None)


def ChatBot(query: str) -> str:
    """
    Main entrypoint:
    - Uses the project's model (if available) to classify queries.
    - If classified 'automation', returns the model's structured action (no execution).
    - Otherwise, sends conversation + realtime info to Groq and returns the assistant's reply.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")

    messages = _load_chatlog()
    messages.append({"role": "user", "content": query})

    # Let model classify if available
    classification = None
    if _model is not None:
        try:
            classification = _model.classify(query)
        except Exception as e:
            LOG.warning("Model classification failed: %s", e)
            classification = None

    # If automation => get structured action from model and do NOT call LLM
    if classification == "automation" and _model is not None:
        try:
            result = _model.process_query(query)
            # Persist user + assistant-style record (stringifies the result)
            messages.append({"role": "assistant", "content": str(result)})
            _save_chatlog(messages)
            return str(result)
        except Exception as e:
            LOG.exception("Failed to handle automation with model")
            return f"[Error handling automation: {e}]"

    # Otherwise call Groq
    payload_messages = SYSTEM_MESSAGE + [{"role": "system", "content": _realtime_info()}] + messages
    answer, error = _call_groq_stream(payload_messages)
    if error:
        return (f"{answer}\n\n[Error: {error}]" if answer else f"[Error: {error}]")

    # Persist and return
    messages.append({"role": "assistant", "content": answer})
    _save_chatlog(messages)
    return answer


if __name__ == "__main__":
    print("Chatbot CLI (type Ctrl+C to exit)")
    try:
        while True:
            user_input = input("Enter Your Question: ").strip()
            if not user_input:
                continue
            print(ChatBot(user_input))
    except KeyboardInterrupt:
        print("\nExiting.")
