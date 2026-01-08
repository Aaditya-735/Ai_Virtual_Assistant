# RealtimeSearchEngine.py
from googlesearch import search
from groq import Groq
from json import load, dump, JSONDecodeError
import datetime
from dotenv import dotenv_values
import os
import requests
from bs4 import BeautifulSoup
from typing import List

# Load environment variables from .env
env_vars = dotenv_values(".env")

# Retrieve environment variables for the chatbot configuration (fallback to defaults)
Username = env_vars.get("Username") or "User"
Assistantname = env_vars.get("Assistantname") or "Assistant"
GroqAPIKey = env_vars.get("GroqAPIKey") or ""

# Initialize the groq client with the provided api key.
client = Groq(api_key=GroqAPIKey)

# Define the system instructions for the chatbot.
System = (
    f"Hello, I am {Username}. You are a very accurate and advanced AI chatbot named {Assistantname} "
    "which has real-time up-to-date information from the internet.\n"
    "*** Provide answers in a professional way — use proper punctuation and grammar. ***\n"
    "*** Answer only from the provided data when asked to do so. ***"
)

# Ensure data directory and chatlog file exist and load messages.
DATA_DIR = os.path.join("Data")
CHATLOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")
os.makedirs(DATA_DIR, exist_ok=True)

try:
    with open(CHATLOG_PATH, "r", encoding="utf-8") as f:
        messages = load(f)
        if not isinstance(messages, list):
            # ensure the stored content is a list
            messages = []
except (FileNotFoundError, JSONDecodeError):
    messages = []
    with open(CHATLOG_PATH, "w", encoding="utf-8") as f:
        dump(messages, f, indent=4, ensure_ascii=False)

# Function to perform a Google search and return a formatted string.
def GoogleSearch(query: str, max_results: int = 5) -> str:
    """
    Uses googlesearch.search to retrieve URLs and optionally fetches page titles.
    If requests/bs4 fail to get a title, it will fall back to the URL only.
    """
    try:
        urls = list(search(query, num_results=max_results))
    except TypeError:
        # Some versions of googlesearch use different param names; try an alternative signature
        urls = list(search(query, num=max_results, stop=max_results, pause=2.0))

    result_lines: List[str] = [f"The search results for '{query}' are:", "[start]"]

    for idx, url in enumerate(urls, start=1):
        title = None
        desc = None
        # Try to get a page title (best-effort; may be slow)
        try:
            resp = requests.get(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
            if resp.ok:
                soup = BeautifulSoup(resp.text, "html.parser")
                t = soup.title
                if t and t.string:
                    title = t.string.strip()
                # meta description
                meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                if meta and meta.get("content"):
                    desc = meta.get("content").strip()
        except Exception:
            # ignore network or parsing errors here; we'll fallback to URL only
            pass

        if title:
            result_lines.append(f"{idx}. Title: {title}")
        else:
            result_lines.append(f"{idx}. URL: {url}")

        if desc:
            result_lines.append(f"   Description: {desc}")
        result_lines.append("")  # blank line between entries

    result_lines.append("[end]")
    return "\n".join(result_lines)


# Function to clean up the answer by removing empty lines.
def AnswerModifier(answer: str) -> str:
    lines = answer.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    return "\n".join(non_empty_lines)


# Predefined chatbot conversation system message and an initial user message.
SystemChatBot = [
    {"role": "system", "content": System},
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello, how can I help you?"},
]


# Function to get real-time information like the current date and time.
def Information() -> str:
    now = datetime.datetime.now()
    data = (
        "Use this real-time information if needed:\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H')} hours, {now.strftime('%M')} minutes, {now.strftime('%S')} seconds.\n"
    )
    return data


# Function to handle real-time search and response generation.
def RealtimeSearchEngine(prompt: str) -> str:
    global SystemChatBot, messages

    # load latest chat log (defensive)
    try:
        with open(CHATLOG_PATH, "r", encoding="utf-8") as f:
            messages = load(f)
            if not isinstance(messages, list):
                messages = []
    except (FileNotFoundError, JSONDecodeError):
        messages = []

    # append the user's prompt to the messages (chat log)
    messages.append({"role": "user", "content": prompt})

    # add google search results to the system chatbot messages (temporary)
    search_content = GoogleSearch(prompt)
    SystemChatBot.append({"role": "system", "content": search_content})

    # Prepare messages for the model: base system + realtime info + chat history
    model_messages = SystemChatBot + [{"role": "system", "content": Information()}] + messages

    # generate a response using the Groq client.
    Answer = ""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=model_messages,
            temperature=0.7,
            max_tokens=2048,
            top_p=1,
            stream=True,  # streaming when supported
            stop=None,
        )

        # If streaming, `completion` is an iterator of chunk-like objects
        for chunk in completion:
            # Chunk structure depends on SDK version; handle common shapes defensively
            try:
                # Try attribute access first
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
            except Exception:
                # Try dictionary-like access
                try:
                    content = chunk["choices"][0]["delta"].get("content")
                except Exception:
                    content = None

            if content:
                Answer += content

    except TypeError:
        # If streaming isn't supported by the client, call without stream and extract full text
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=model_messages,
            temperature=0.7,
            max_tokens=2048,
            top_p=1,
            stream=False,
            stop=None,
        )
        # Try to extract text from response (handle different response shapes)
        try:
            # object style
            Answer = resp.choices[0].message.content
        except Exception:
            # dict-like
            Answer = resp.get("choices", [{}])[0].get("message", {}).get("content", "")

    # Clean up the response
    Answer = Answer.strip().replace("</s>", "")

    # Append assistant response to chat log and save
    messages.append({"role": "assistant", "content": Answer})
    with open(CHATLOG_PATH, "w", encoding="utf-8") as f:
        dump(messages, f, indent=4, ensure_ascii=False)

    # Remove the temporary system message that contained the search results
    SystemChatBot.pop()

    return AnswerModifier(Answer)


# Main entry point for interactive querying.
if __name__ == "__main__":
    print("RealtimeSearchEngine is running. Press Ctrl+C to exit.")
    try:
        while True:
            prompt = input("Enter your query: ").strip()
            if not prompt:
                continue
            try:
                response = RealtimeSearchEngine(prompt)
                print(response)
            except Exception as e:
                print(f"Error while generating response: {e}")
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")

