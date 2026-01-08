# Automation.py — corrected version

# imports
from AppOpener import close, open as appopen
from webbrowser import open as webopen
import webbrowser
from pywhatkit import search, playonyt
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from rich import print
from groq import Groq
import subprocess
import requests
import keyboard
import asyncio
import os
import sys

# load environment variables from the .env file.
env_vars = dotenv_values(".env")
GroqAPIKey = env_vars.get("GroqAPIKey", None)
USERNAME = env_vars.get("Username", os.environ.get("USERNAME", "Assistant"))

# initialize groq client only if API key present (avoid KeyError)
client = Groq(api_key=GroqAPIKey) if GroqAPIKey else None

# CSS classes for parsing (kept as in original)
classes = [
    "zCubwf", "hgKElc", "LTKOO sY7ric", "Z0LcW",
    "gsrt vk_bk FzvWSb YwPhnf", "pclqee", "tw-Data-text tw-text-small tw-ta",
    "IZ6rdc", "O5uR6d LTKOO", "vlzY6d", "webanswers-webanswers_table_webanswers-table",
    "dDoNo ikb4Bb gsrt", "sXLaoe", "LWkfKe", "VQF4g", "qv3Wpe", "kno-rdesc", "SPZz6b"
]

useragent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/91.0.4472.124 Safari/537.36")

professional_responses = [
    "Your satisfaction is my top priority; feel free to reach out if there's anything else I can help you with.",
    "I'm at your service for any additional questions or support you may need—don't hesitate to ask.",
]

messages = []

SystemChatBot = [
    {
        "role": "system",
        "content": (
            f"Hello, I am {USERNAME}. You are a helpful AI assistant. "
            "Your capabilities include providing general information, performing web searches, "
            "and generating content based on user prompts. Answer all questions directly unless "
            "you are asked to generate content. Do not engage in persona-based conversations."
        )
    }
]


def GoogleSearch(Topic: str) -> bool:
    """Perform a Google search via pywhatkit (opens browser)."""
    try:
        search(Topic)
        return True
    except Exception as e:
        print("[red]GoogleSearch error:[/red]", e)
        return False


def Content(Topic: str) -> bool:
    """Generate content via Groq chat and save to Data/<topic>.txt then open in notepad."""
    if not client:
        print("[red]Content error: Groq API client is not initialized (missing API key).[/red]")
        return False

    def OpenNotepad(File: str):
        default_text_editor = "notepad.exe" if sys.platform.startswith("win") else "gedit"
        try:
            subprocess.Popen([default_text_editor, File])
        except Exception as e:
            print("[yellow]Could not open file in editor, error:[/yellow]", e)

    def ContentWriterAI(prompt: str) -> str:
        messages.append({"role": "user", "content": prompt})
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=SystemChatBot + messages,
                max_tokens=2048,
                temperature=0.7,
                top_p=1,
                stream=True,
                stop=None
            )
        except Exception as e:
            print("[red]AI request failed:[/red]", e)
            return ""

        Answer = ""
        try:
            for chunk in completion:
                # guard against missing fields on stream chunks
                delta = getattr(chunk.choices[0], "delta", None)
                if delta:
                    content_piece = getattr(delta, "content", None)
                    if content_piece:
                        Answer += content_piece
        except Exception as e:
            print("[yellow]Warning while processing streamed chunks:[/yellow]", e)

        Answer = Answer.replace("</s>", "")
        messages.append({"role": "assistant", "content": Answer})
        return Answer

    Topic_clean = Topic.replace("Content ", "").strip()
    data_dir = os.path.join("Data")
    os.makedirs(data_dir, exist_ok=True)

    ContentByAI = ContentWriterAI(Topic_clean)
    if ContentByAI is None:
        ContentByAI = ""

    filename = os.path.join(data_dir, f"{Topic_clean.lower().replace(' ', '')}.txt")
    try:
        with open(filename, "w", encoding="utf-8") as file:
            file.write(ContentByAI)
    except Exception as e:
        print("[red]Failed to write file:[/red]", e)
        return False

    OpenNotepad(filename)
    return True


def YouTubeSearch(Topic: str) -> bool:
    """Open YouTube search results for Topic."""
    try:
        Url4Search = f"https://www.youtube.com/results?search_query={requests.utils.requote_uri(Topic)}"
        webbrowser.open(Url4Search)
        return True
    except Exception as e:
        print("[red]YouTubeSearch error:[/red]", e)
        return False


def PlayYoutube(query: str) -> bool:
    """Play the first YouTube result using pywhatkit.playonyt."""
    try:
        playonyt(query)
        return True
    except Exception as e:
        print("[red]PlayYoutube error:[/red]", e)
        return False


def OpenApp(app: str, sess: requests.Session = None) -> bool:
    """Try to open an app locally, otherwise fallback to searching the web and opening the first result."""
    sess = sess or requests.Session()

    try:
        # try AppOpener first
        appopen(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception as e:
        print(f"[yellow]AppOpener failed for '{app}':[/yellow]", e)

    def extract_links(html: str) -> list:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", {"jsname": "UWckNb"})
        hrefs = []
        for link in links:
            href = link.get("href")
            if href:
                hrefs.append(href)
        return hrefs

    def search_google(query: str) -> str | None:
        url = f"https://www.google.com/search?q={requests.utils.requote_uri(query)}"
        headers = {"User-Agent": useragent}
        try:
            response = sess.get(url, headers=headers, timeout=8)
            if response.status_code == 200:
                return response.text
            else:
                print("[red]Failed to retrieve search results, status code:[/red]", response.status_code)
        except Exception as e:
            print("[red]HTTP request failed:[/red]", e)
        return None

    html = search_google(app)
    if not html:
        return False

    links = extract_links(html)
    if not links:
        print("[yellow]No suitable links found while searching for the app.[/yellow]")
        return False

    # open the first absolute link or prefix google redirect URL properly
    first = links[0]
    if first.startswith("/url?q="):
        # google redirect style, extract real URL
        import urllib.parse as _up
        parsed = _up.parse_qs(_up.urlsplit(first).query)
        # fallback: open as-is
        link = first
    else:
        link = first

    try:
        # ensure it is a proper URL
        if link.startswith("http"):
            webopen(link)
        else:
            webopen(f"https://www.google.com{link}")
    except Exception as e:
        print("[red]Failed to open link in browser:[/red]", e)
        return False

    return True


def CloseApp(app: str) -> bool:
    """Try to close an app. Special-case Chrome on Windows if AppOpener.close doesn't work."""
    try:
        close(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception as e:
        print(f"[yellow]AppOpener.close failed for '{app}':[/yellow]", e)

    # Platform-specific fallback for Chrome on Windows
    try:
        if "chrome" in app.lower() and sys.platform.startswith("win"):
            subprocess.run("taskkill /F /IM chrome.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception as e:
        print("[red]Fallback close attempt failed:[/red]", e)

    return False


def System(command: str) -> bool:
    """Execute simple system commands: mute/unmute/volume up/volume down."""
    def mute():
        keyboard.press_and_release("volume mute")

    def unmute():
        keyboard.press_and_release("volume mute")

    def volume_up():
        keyboard.press_and_release("volume up")

    def volume_down():
        keyboard.press_and_release("volume down")

    try:
        if command == "mute":
            mute()
        elif command == "unmute":
            unmute()
        elif command == "volume up":
            volume_up()
        elif command == "volume down":
            volume_down()
        else:
            print(f"[yellow]Unknown system command: {command}[/yellow]")
            return False
    except Exception as e:
        print("[red]System command failed:[/red]", e)
        return False

    return True


async def TranslateAndExecute(commands: list[str]):
    """Translate a list of natural-language commands and execute them concurrently."""
    funcs = []

    for command in commands:
        cmd = command.strip()
        if not cmd:
            continue

        if cmd.startswith("open"):
            # skip trivial phrases
            if "open it" in cmd or cmd == "open file":
                continue
            target = cmd.removeprefix("open ").strip()
            funcs.append(asyncio.to_thread(OpenApp, target))

        elif cmd.startswith("close "):
            target = cmd.removeprefix("close ").strip()
            funcs.append(asyncio.to_thread(CloseApp, target))

        elif cmd.startswith("play "):
            target = cmd.removeprefix("play ").strip()
            funcs.append(asyncio.to_thread(PlayYoutube, target))

        elif cmd.startswith("content "):
            target = cmd.removeprefix("content ").strip()
            funcs.append(asyncio.to_thread(Content, target))

        elif cmd.startswith("google search "):
            target = cmd.removeprefix("google search ").strip()
            funcs.append(asyncio.to_thread(GoogleSearch, target))

        elif cmd.startswith("youtube search "):
            target = cmd.removeprefix("youtube search ").strip()
            funcs.append(asyncio.to_thread(YouTubeSearch, target))

        elif cmd.startswith("system "):
            target = cmd.removeprefix("system ").strip()
            funcs.append(asyncio.to_thread(System, target))

        elif cmd.startswith(("what ", "where ", "when ", "why ", "how ")):
            # treat as a google query
            # remove the leading question word
            if cmd.startswith("what "):
                query = cmd.removeprefix("what ").strip()
            elif cmd.startswith("where "):
                query = cmd.removeprefix("where ").strip()
            elif cmd.startswith("when "):
                query = cmd.removeprefix("when ").strip()
            elif cmd.startswith("why "):
                query = cmd.removeprefix("why ").strip()
            elif cmd.startswith("how "):
                query = cmd.removeprefix("how ").strip()
            else:
                query = cmd
            funcs.append(asyncio.to_thread(GoogleSearch, query))

        else:
            print(f"No Function Found for: {cmd}")

    if not funcs:
        return

    results = await asyncio.gather(*funcs, return_exceptions=True)
    for result in results:
        yield result


async def Automation(commands: list[str]) -> bool:
    """Top-level automation runner — iterates TranslateAndExecute and returns True if invoked."""
    try:
        async for _ in TranslateAndExecute(commands):
            # If you want to process results, do it here.
            pass
        return True
    except Exception as e:
        print("[red]Automation runner failed:[/red]", e)
        return False
