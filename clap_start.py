import sounddevice as sd
import numpy as np
import subprocess
import time
import os
import sys

JARVIS_PATH = r"C:\Users\AG\Desktop\JARVIS\main.py"   # update to your path
VOLUME_THRESHOLD = 0.30

def sound_callback(indata, frames, time_info, status):
    volume = np.linalg.norm(indata) * 10
    if volume > VOLUME_THRESHOLD:
        print("Clap detected! Starting JARVIS...")
        subprocess.Popen([sys.executable, JARVIS_PATH])
        time.sleep(2)

def listen_for_clap():
    print("Listening for clap...")
    with sd.InputStream(callback=sound_callback):
        while True:
            time.sleep(0.1)

if __name__ == "__main__":
    listen_for_clap()
