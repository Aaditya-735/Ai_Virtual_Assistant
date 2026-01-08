#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
import os
import time
import mtranslate as mt
from pathlib import Path

# load environment variables from the .env file.
env_vars = dotenv_values(".env")
# get the input language setting from the environment variables, default to 'en' if missing
InputLanguage = env_vars.get("InputLanguage") or "en"

# ensure simple language format (e.g., 'en' -> 'en-US' fallback if short)
def normalize_lang(lang: str) -> str:
    lang = (lang or "en").strip()
    if "-" in lang:
        return lang
    # convert short codes like 'en' or 'EN' to 'en-US' as a reasonable default
    return f"{lang.lower()}-{ 'US' if lang.lower() == 'en' else lang.upper() }"

NormalizedInputLanguage = normalize_lang(InputLanguage)

# define the HTML code for the speech recognition interface.
HtmlCode = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Speech Recognition</title>
</head>
<body>
    <button id="start" onclick="startRecognition()">Start Recognition</button>
    <button id="end" onclick="stopRecognition()">Stop Recognition</button>
    <p id="output"></p>
    <script>
        const output = document.getElementById('output');
        let recognition;

        function startRecognition() {{
            const WebSpeech = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!WebSpeech) {{
                output.textContent = "SpeechRecognition API not available in this browser.";
                return;
            }}
            recognition = new WebSpeech();
            recognition.lang = '{NormalizedInputLanguage}';
            recognition.continuous = true;

            recognition.onresult = function(event) {{
                const transcript = event.results[event.results.length - 1][0].transcript;
                // append a space for readability between chunks
                output.textContent += (transcript + " ");
            }};

            recognition.onerror = function(evt) {{
                console.error("Recognition error:", evt);
            }};

            recognition.onend = function() {{
                // restart so it keeps listening until user clicks Stop
                try {{
                    recognition.start();
                }} catch (e) {{
                    console.error("Failed to restart recognition:", e);
                }}
            }};
            recognition.start();
        }}

        function stopRecognition() {{
            if (recognition) {{
                recognition.stop();
            }}
            // do not clear output here — let the calling automation decide.
        }}
    </script>
</body>
</html>'''

# write the modified HTML code to a file (create folders if missing).
data_dir = Path.cwd() / "Data"
data_dir.mkdir(parents=True, exist_ok=True)
html_path = data_dir / "Voice.html"
html_path.write_text(HtmlCode, encoding="utf-8")

# create frontend temp dir
current_dir = Path.cwd()
TempDirPath = current_dir / "Frontend" / "Files"
TempDirPath.mkdir(parents=True, exist_ok=True)

# prepare the webdriver
chrome_options = Options()
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.142.86 Safari/537.36"
chrome_options.add_argument(f'user-agent={user_agent}')
# allow fake media stream (useful for testing) and allow access without user prompt
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")
# headless may interfere with microphone in some setups; keep as optional by env var in future.
chrome_options.add_argument("--headless=new")
# reduce logging noise
chrome_options.add_argument("--log-level=3")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Function to set the assistant's status by writing it to a file.
def SetAssistantStatus(Status: str):
    try:
        status_file = TempDirPath / "Status.data"
        status_file.write_text(Status, encoding="utf-8")
    except Exception as e:
        # fail silently but log to console
        print("Warning: could not write status file:", e)

# function to modify a query to ensure proper punctuation and formatting.
def QueryModifier(Query: str) -> str:
    if not Query:
        return ""
    new_query = Query.strip()
    # normalize whitespace and lowercase for question detection, but preserve final capitalization after punctuation
    trimmed = " ".join(new_query.split()).lower()
    question_indicators = ["how", "what", "who", "where", "when", "why", "which", "whose", "whom", "can you", "what's", "where's", "how's"]
    is_question = any(trimmed.startswith(q) or (" " + q + " ") in (" " + trimmed + " ") for q in question_indicators)

    last_char = new_query[-1]
    if is_question:
        if last_char not in ".?!":
            new_query = new_query + "?"
        else:
            # replace trailing punctuation with '?'
            new_query = new_query[:-1] + "?"
    else:
        if last_char not in ".?!":
            new_query = new_query + "."
        else:
            # ensure ends with a single period
            if last_char != ".":
                new_query = new_query[:-1] + "."

    # ensure first letter capitalized and rest preserved
    return new_query.strip().capitalize()

# function to translate text into english using the mtranslate library.
def UniversalTranslator(Text: str) -> str:
    try:
        if not Text:
            return ""
        english_translation = mt.translate(Text, "en", "auto")
        return english_translation.capitalize()
    except Exception as e:
        # fallback to original text if translation fails
        print("Translation failed:", e)
        return Text

# function to perform speech recognition using the webdriver.
def SpeechRecognition(poll_interval: float = 0.5, max_wait_seconds: float = None) -> str:
    # Open the HTML file in the browser.
    driver.get(html_path.as_uri())

    # start speech recognition by clicking the start button.
    try:
        start_btn = driver.find_element(By.ID, "start")
        start_btn.click()
    except Exception as e:
        raise RuntimeError(f"Could not click Start button: {e}")

    start_time = time.time()
    try:
        while True:
            try:
                # get the recognized text from the HTML output element.
                output_elem = driver.find_element(By.ID, "output")
                Text = output_elem.text.strip()

                if Text:
                    # Stop recognition by clicking the stop button.
                    try:
                        driver.find_element(By.ID, "end").click()
                    except Exception:
                        # if clicking end fails, continue — we already captured the text
                        pass

                    # if the input language is english (or contains 'en') return the modified query.
                    if "en" in InputLanguage.lower():
                        return QueryModifier(Text)
                    else:
                        # if the input language is not english , translate the text and return it.
                        SetAssistantStatus("Translating...")
                        return QueryModifier(UniversalTranslator(Text))

                # optional timeout to avoid infinite loop if desired
                if max_wait_seconds is not None and (time.time() - start_time) > max_wait_seconds:
                    raise TimeoutError("Speech recognition timed out waiting for input.")
            except Exception:
                # ignore DOM read errors and continue polling
                pass

            time.sleep(poll_interval)
    finally:
        # best effort: try to stop recognition if still active
        try:
            driver.execute_script("if (window.recognition) { try { window.recognition.stop(); } catch(e) {} }")
        except Exception:
            pass

# main execution block.
if __name__ == "__main__":
    try:
        while True:
            Text = SpeechRecognition()
            if Text:
                print(Text)
            # small pause to prevent a tight loop
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nExiting on user interrupt.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
