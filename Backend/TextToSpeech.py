# TextToSpeech.py — corrected version
import os
import random
import asyncio
import pygame
import edge_tts
from dotenv import dotenv_values

# Load environment variables from a .env file
env_vars = dotenv_values(".env")
AssistantVoice = env_vars.get("AssistantVoice") or "en-US-JennyNeural"  # fallback voice

# Ensure Data directory exists and use OS-independent path
DATA_DIR = os.path.join(os.path.dirname(__file__), "Data")
os.makedirs(DATA_DIR, exist_ok=True)
SPEECH_FILE = os.path.join(DATA_DIR, "speech.mp3")


# Asynchronous function to convert text to an audio file
async def TextToAudioFile(text: str) -> None:
    """
    Generate an MP3 speech file for `text` using edge-tts.
    Saves to SPEECH_FILE path.
    """
    # Remove old file if present
    if os.path.exists(SPEECH_FILE):
        try:
            os.remove(SPEECH_FILE)
        except OSError:
            # If removal fails, ignore and try to overwrite later
            pass

    # Use edge-tts Communicate with text and assistant voice
    # Note: advanced SSML (pitch/rate) was removed for compatibility.
    communicate = edge_tts.Communicate(text, AssistantVoice)
    await communicate.save(SPEECH_FILE)


def _run_coro_safe(coro):
    """
    Run coroutine in typical script environments using asyncio.run().
    If an event loop is already running, raise clear error so user can handle it.
    """
    try:
        # If there is a running loop, asyncio.get_running_loop() will not raise.
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop -> safe to use asyncio.run
        return asyncio.run(coro)
    else:
        # An event loop is already running (e.g. interactive notebook). Provide a clear error.
        raise RuntimeError(
            "An asyncio event loop is already running. "
            "This script expects to be run as a standard Python process (not inside an already-running asyncio loop)."
        )


# Function to manage Text-To-Speech (TTS) functionality
def TTS(Text, func=lambda r=None: True):
    """
    Convert `Text` to speech and play it using pygame.
    `func` is an optional callable used as a stop-check and final notifier.
      - When called with no args it should return True/False (continue/stop).
      - The TTS code calls func(False) in the cleanup to signal completion.
    Returns True on success, False on error.
    """
    while True:
        try:
            # Convert text to an audio file asynchronously
            _run_coro_safe(TextToAudioFile(Text))

            # Initialize pygame mixer for audio playback
            pygame.mixer.init()

            # Load generated speech file
            pygame.mixer.music.load(SPEECH_FILE)
            pygame.mixer.music.play()

            # Loop until playback finishes or external func signals to stop
            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                try:
                    # If func returns exactly False, we break playback early.
                    if func() is False:
                        break
                except TypeError:
                    # If func expects an argument (e.g., func(False)), call safely
                    try:
                        if func(None) is False:
                            break
                    except Exception:
                        # If func fails, ignore and continue
                        pass
                clock.tick(10)

            return True

        except Exception as e:
            print(f"Error in TTS: {e}")
            # On error, return False so caller knows TTS failed.
            return False

        finally:
            try:
                # Signal completion to func
                try:
                    func(False)
                except TypeError:
                    # If func doesn't accept args, call without
                    try:
                        func()
                    except Exception:
                        pass

                # Stop and quit mixer if initialized
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
            except Exception as e:
                print(f"Error in finally block: {e}")


# Function to manage Text-To-Speech with additional responses for long text
def TextToSpeech(Text, func=lambda r=None: True):
    """
    Splits sentences and if Text is long, speaks only the first part and a "check chat" message.
    Otherwise, speaks the whole text.
    """
    Text = str(Text).strip()
    Data = Text.split(".")
    # Predefined responses for long text
    responses = [
        "The rest of the result has been printed to the chat screen, kindly check it out sir.",
        "The rest of the text is now on the chat screen, sir, please check it.",
        "You can see the rest of the text on the chat screen, sir.",
        "The remaining part of the text is now on the chat screen, sir.",
        "Sir, you'll find more text on the chat screen for you to see.",
        "The rest of the answer is now on the chat screen, sir.",
        "Sir, please look at the chat screen, the rest of the answer is there.",
        "You'll find the complete answer on the chat screen, sir.",
        "The next part of the text is on the chat screen, sir.",
        "Sir, please check the chat screen for more information.",
        "There's more text on the chat screen for you, sir.",
        "Sir, take a look at the chat screen for additional text.",
        "You'll find more to read on the chat screen, sir.",
        "Sir, check the chat screen for the rest of the text.",
        "The chat screen has the rest of the text, sir.",
        "There's more to see on the chat screen, sir, please look.",
        "Sir, the chat screen holds the continuation of the text.",
        "You'll find the complete answer on the chat screen, kindly check it out sir.",
        "Please review the chat screen for the rest of the text, sir.",
        "Sir, look at the chat screen for the complete answer."
    ]

    # If the text is long (more than 4 sentences and >= 250 chars), say a short piece + response
    if len(Data) > 4 and len(Text) >= 250:
        first_two = ". ".join([s.strip() for s in Data[:2] if s.strip()])
        if first_two:
            to_speak = first_two + ". " + random.choice(responses)
        else:
            to_speak = random.choice(responses)
        TTS(to_speak, func)
    else:
        TTS(Text, func)


if __name__ == "__main__":
    try:
        while True:
            user_text = input("Enter the text: ").strip()
            if user_text.lower() in ("exit", "quit"):
                print("Exiting.")
                break
            TextToSpeech(user_text)
    except KeyboardInterrupt:
        print("\nTerminated by user.")
