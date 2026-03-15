### JARVIS – AI Virtual Assistant

JARVIS is a Python-based AI virtual assistant that interacts with users through voice commands and performs 
automation tasks such as opening applications, answering queries using AI models, and executing web searches. 
The project demonstrates practical implementation of voice recognition, AI APIs, and desktop automation.

# Features
-Voice command recognition
-AI-powered responses using LLM APIs
-Desktop application automation
-Web search integration
-Text-to-speech interaction
-Clap detection to start the assistant

# Technologies Used
-Python
-SpeechRecognition
-PyAudio
-Groq / LLM APIs
-Hugging Face API
-PyQt (GUI)
-dotenv

# Installation
1. git clone https://github.com/Aaditya-735/Ai_Virtual_Assistant.git
2. cd Ai_Virtual_Assistant
3. pip install -r Requirements.txt

# Environment Setup

Create a .env file and add your API keys:
            GROQ_API_KEY=your_api_key
            HF_TOKEN=your_token

# Run the Project

python Main.py

-> To start the assistant with clap detection:
            python clap_start.py
