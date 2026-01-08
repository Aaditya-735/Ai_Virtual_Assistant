# main.py (corrected)

from Frontend.GUI import (
    GraphicalUserInterface,
    SetAssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    setMicrophoneStatus,
    AnswerModifier,
    QueryModifier,
    GetMicrophoneStatus,
    GetAssistantStatus,
)
# Backend imports (assumed to exist). We make some calls tolerant to sync/async.
from Backend.Model import classify_prompt as FirstLayerDMM
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Automation
from Backend.SpeechToText import SpeechRecognition
from Backend.Chatbot import ChatBot
from Backend.TextToSpeech import TextToSpeech

from dotenv import dotenv_values
from asyncio import run as asyncio_run
import inspect
from time import sleep
import subprocess
import threading
import json
import os
import sys

env_vars = dotenv_values(".env")
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Assistant")

DefaultMessage = (
    f"{Username} : Hello {Assistantname}, How are you?\n"
    f"{Assistantname} : Welcome {Username}. I am doing well. How may i help you?"
)

subprocesses = []
Functions = ["open", "close", "play", "system", "content", "google search", "youtube search"]
CHATLOG_PATH = os.path.join("Data", "ChatLog.json")


def safe_path(p: str) -> str:
    """Return path unchanged or converted if using TempDirectoryPath() style elsewhere."""
    return p


def ShowDefaultChatIfNoChats():
    """
    Ensure Database.data and Responses.data exist and have defaults if ChatLog.json is empty or missing.
    Fixes: used correct write mode 'w', handled missing files.
    """
    # If chat log missing or empty, write defaults to temp files.
    chat_text = ""
    try:
        with open(CHATLOG_PATH, "r", encoding="utf-8") as f:
            chat_text = f.read()
    except FileNotFoundError:
        chat_text = ""

    if len(chat_text) < 5:
        # Use TempDirectoryPath for the ui temp files
        try:
            with open(TempDirectoryPath("Database.data"), "w", encoding="utf-8") as file:
                file.write("")
        except Exception:
            # fallback to local files if TempDirectoryPath fails
            with open(os.path.join("Frontend", "Files", "Database.data"), "w", encoding="utf-8") as file:
                file.write("")

        try:
            with open(TempDirectoryPath("Responses.data"), "w", encoding="utf-8") as file:
                file.write(DefaultMessage)
        except Exception:
            with open(os.path.join("Frontend", "Files", "Responses.data"), "w", encoding="utf-8") as file:
                file.write(DefaultMessage)


def ReadChatLogJson():
    """Return parsed JSON list from Data/ChatLog.json or [] on failure."""
    try:
        with open(CHATLOG_PATH, "r", encoding="utf-8") as file:
            chatlog_data = json.load(file)
            if isinstance(chatlog_data, list):
                return chatlog_data
            # if file contains an object, try to convert to list of messages
            return []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # corrupted json -> return empty
        return []


def ChatLogIntegration():
    """
    Convert chatlog json to a formatted string and write to Database.data after passing through AnswerModifier.
    """
    json_data = ReadChatLogJson()
    formatted_chatlog = ""
    for entry in json_data:
        role = entry.get("role", "").lower()
        content = entry.get("content", "")
        if role == "user":
            formatted_chatlog += f"User: {content}\n"
        elif role == "assistant":
            formatted_chatlog += f"Assistant: {content}\n"

    # Replace generic tokens with actual names
    formatted_chatlog = formatted_chatlog.replace("User", Username)
    formatted_chatlog = formatted_chatlog.replace("Assistant", Assistantname)

    # Apply AnswerModifier if available and write out
    try:
        out_text = AnswerModifier(formatted_chatlog)
    except Exception:
        out_text = formatted_chatlog

    try:
        with open(TempDirectoryPath("Database.data"), "w", encoding="utf-8") as file:
            file.write(out_text)
    except Exception:
        # fallback
        fallback_path = os.path.join("Frontend", "Files", "Database.data")
        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
        with open(fallback_path, "w", encoding="utf-8") as file:
            file.write(out_text)


def ShowChatOnGUI():
    """
    Read Database.data and copy to Responses.data for GUI consumption.
    """
    try:
        with open(TempDirectoryPath("Database.data"), "r", encoding="utf-8") as File:
            Data = File.read()
    except Exception:
        # fallback try project file
        try:
            with open(os.path.join("Frontend", "Files", "Database.data"), "r", encoding="utf-8") as File:
                Data = File.read()
        except Exception:
            Data = ""

    if len(str(Data)) > 0:
        lines = Data.split("\n")
        result = "\n".join(lines)
        try:
            with open(TempDirectoryPath("Responses.data"), "w", encoding="utf-8") as File:
                File.write(result)
        except Exception:
            os.makedirs(os.path.join("Frontend", "Files"), exist_ok=True)
            with open(os.path.join("Frontend", "Files", "Responses.data"), "w", encoding="utf-8") as File:
                File.write(result)


def InitialExecution():
    # initialize UI / data
    try:
        setMicrophoneStatus("False")
    except Exception:
        # If setMicrophoneStatus isn't available / fails, ignore
        pass

    try:
        ShowTextToScreen("")
    except Exception:
        pass

    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatOnGUI()


InitialExecution()


def _call_automation_maybe_async(decision_list):
    """
    Call Automation either synchronously or asynchronously depending on whether Automation is a coroutine function.
    """
    try:
        if inspect.iscoroutinefunction(Automation):
            # Automation is an async def
            return asyncio_run(Automation(decision_list))
        else:
            # might still return coroutine when called (if class __call__ is async), handle that
            result = Automation(decision_list)
            if inspect.iscoroutine(result):
                return asyncio_run(result)
            return result
    except Exception as e:
        # report and continue; don't let automation crash the whole assistant
        print(f"[Automation] Error while executing Automation: {e}")
        return None


def MainExecution():

    TaskExecution = False
    ImageExecution = False
    ImageGenerationQuery = ""

    # Set UI to listening and get speech input
    try:
        SetAssistantStatus("Listening...")
    except Exception:
        pass

    try:
        Query = SpeechRecognition()
    except Exception as e:
        print(f"[SpeechRecognition] Error: {e}")
        Query = ""

    try:
        ShowTextToScreen(f"{Username} : {Query}")
    except Exception:
        pass

    try:
        SetAssistantStatus("Thinking...")
    except Exception:
        pass

    try:
        Decision = FirstLayerDMM(Query)
    except Exception as e:
        print(f"[FirstLayerDMM] Error: {e}")
        Decision = []

    # Ensure Decision is iterable list
    if not isinstance(Decision, (list, tuple)):
        Decision = list(Decision) if Decision else []

    print("")
    print(f"Decision : {Decision}")
    print("")

    # Determine whether decisions contain general / realtime
    G = any(i.startswith("general") for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Mearged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision if i.startswith("general") or i.startswith("realtime")]
    )

    # detect image generation requests
    for q in Decision:
        if isinstance(q, str) and "generate" in q:
            ImageGenerationQuery = str(q)
            ImageExecution = True
            break

    # detect task automations (calls Automation once)
    for q in Decision:
        if not TaskExecution:
            if any(isinstance(q, str) and q.startswith(func) for func in Functions):
                _call_automation_maybe_async(list(Decision))
                TaskExecution = True

    # Image generation branch
    if ImageExecution:
        # Write query marker for image generation script
        try:
            with open(os.path.join("Frontend", "Files", "ImageGeneration.data"), "w", encoding="utf-8") as file:
                file.write(f"{ImageGenerationQuery},True")
        except Exception:
            try:
                with open(os.path.join("Backend", "ImageGeneration.data"), "w", encoding="utf-8") as file:
                    file.write(f"{ImageGenerationQuery},True")
            except Exception:
                print("[ImageGeneration] Could not write ImageGeneration.data")

        # Launch image generation script as subprocess (use current python executable)
        try:
            p1 = subprocess.Popen(
                [sys.executable, os.path.join("Backend", "ImageGeneration.py")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
            )
            subprocesses.append(p1)
        except Exception as e:
            print(f"Error starting ImageGeneration.py: {e}")

    # Branching logic: both general+realtime, realtime-only, or general-only
    if G and R:
        # Both general and realtime - prioritize realtime search + combined query
        try:
            SetAssistantStatus("Searching...")
        except Exception:
            pass
        try:
            Answer = RealtimeSearchEngine(QueryModifier(Mearged_query))
        except Exception as e:
            print(f"[RealtimeSearchEngine] Error: {e}")
            Answer = "Sorry, I couldn't fetch realtime results."

        try:
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering...")
            TextToSpeech(Answer)
        except Exception:
            pass

        return True

    elif R:
        # Only realtime results needed
        try:
            SetAssistantStatus("Searching...")
        except Exception:
            pass

        try:
            Answer = RealtimeSearchEngine(QueryModifier(Mearged_query))
        except Exception as e:
            print(f"[RealtimeSearchEngine] Error: {e}")
            Answer = "Sorry, I couldn't fetch realtime results."

        try:
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering...")
            TextToSpeech(Answer)
        except Exception:
            pass

        return True

    else:
        # No realtime tasks — handle per-decision general queries or exit
        for item in Decision:
            if not isinstance(item, str):
                continue

            if item.startswith("general"):
                try:
                    SetAssistantStatus("Thinking...")
                except Exception:
                    pass
                QueryFinal = item.replace("general ", "", 1)
                try:
                    Answer = ChatBot(QueryModifier(QueryFinal))
                except Exception as e:
                    print(f"[ChatBot] Error: {e}")
                    Answer = "Sorry, I couldn't process that."

                try:
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                except Exception:
                    pass

                return True

            elif item.startswith("realtime"):
                try:
                    SetAssistantStatus("Searching...")
                except Exception:
                    pass
                QueryFinal = item.replace("realtime ", "", 1)
                try:
                    Answer = RealtimeSearchEngine(QueryModifier(QueryFinal))
                except Exception as e:
                    print(f"[RealtimeSearchEngine] Error: {e}")
                    Answer = "Sorry, I couldn't fetch realtime results."

                try:
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                except Exception:
                    pass

                return True

            elif item.startswith("exit"):
                QueryFinal = "Okay, Bye!"
                try:
                    Answer = ChatBot(QueryModifier(QueryFinal))
                except Exception:
                    Answer = QueryFinal

                try:
                    ShowTextToScreen(f"{Assistantname} : {Answer}")
                    SetAssistantStatus("Answering...")
                    TextToSpeech(Answer)
                except Exception:
                    pass

                # Graceful exit
                try:
                    # try normal exit first
                    sys.exit(0)
                except SystemExit:
                    os._exit(0)

        # If we reach here nothing matched
        return False


def FirstThread():
    """
    Poll the microphone status and run MainExecution when mic is active.
    """
    while True:
        try:
            CurrentStatus = GetMicrophoneStatus()
        except Exception:
            CurrentStatus = "False"

        if CurrentStatus == "True":
            MainExecution()
        else:
            try:
                AIStatus = GetAssistantStatus()
            except Exception:
                AIStatus = ""

            if "Available..." in AIStatus:
                sleep(0.1)
            else:
                try:
                    SetAssistantStatus("Available...")
                except Exception:
                    pass


def SecondThread():
    """
    Start / show the GUI (this is intended to run in the main thread in many GUI frameworks).
    """
    try:
        GraphicalUserInterface()
    except Exception as e:
        print(f"[GUI] Error launching GraphicalUserInterface: {e}")


if __name__ == "__main__":
    # FirstThread as a daemon so the process can be killed from the GUI exit
    thread1 = threading.Thread(target=FirstThread, daemon=True)
    thread1.start()

    # Run GUI in main thread
    SecondThread()
