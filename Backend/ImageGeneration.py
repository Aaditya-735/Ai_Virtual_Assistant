#!/usr/bin/env python3
"""
ImageGeneration.py (fixed for InferenceClient signature)
- Uses huggingface_hub.InferenceClient.text_to_image(prompt, model=...)
- Does NOT pass 'parameters' to text_to_image (compat with older hf client versions)
"""

import asyncio
from random import randint
from pathlib import Path
from time import sleep
import os
import sys
from io import BytesIO

from dotenv import load_dotenv
from PIL import Image
from huggingface_hub import InferenceClient

# load .env
load_dotenv()

# Get API key
HUGGING_FACE_API_KEY = os.getenv("HuggingFaceAPIKey") or os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_API_KEY")
if not HUGGING_FACE_API_KEY:
    raise RuntimeError("Hugging Face API key not found. Set HuggingFaceAPIKey or HF_TOKEN in environment or .env file.")

# Initialize client
client = InferenceClient(api_key=HUGGING_FACE_API_KEY)

# Directories
DATA_DIR = Path("Data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONTROL_FILE = Path("Frontend") / "Files" / "ImageGeneration.data"
CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)


def sanitize_filename(s: str) -> str:
    safe = s.strip().replace(" ", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch in ("_", "-", ".")).rstrip("._-")


def open_image(prompt: str):
    prompt_safe = sanitize_filename(prompt)
    files = [DATA_DIR / f"{prompt_safe}{i}.jpg" for i in range(1, 5)]
    for jpg_path in files:
        if jpg_path.exists():
            try:
                print(f"Opening image: {jpg_path}")
                img = Image.open(jpg_path)
                img.show()
                sleep(1)
            except Exception as e:
                print(f"Failed to open {jpg_path}: {e}")
        else:
            print(f"File not found: {jpg_path}")


def hf_generate_image_blocking(prompt: str, model: str, seed: int = None):
    """
    Use InferenceClient.text_to_image without 'parameters' kwarg (compat).
    NOTE: Some hf client versions accept parameters but older ones do not.
    """
    try:
        # call text_to_image with prompt and model only (no parameters=...)
        result = client.text_to_image(prompt, model=model)
    except TypeError as te:
        # defensive fallback: client may expect different argument ordering; try alternative:
        try:
            result = client.text_to_image(prompt)  # model might be set as default for client
        except Exception as e:
            raise RuntimeError(f"Hugging Face image generation failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Hugging Face image generation failed: {e}") from e

    # result may be PIL.Image, bytes, or dict
    if hasattr(result, "save"):
        bio = BytesIO()
        result.convert("RGB").save(bio, format="JPEG", quality=95)
        return bio.getvalue()

    if isinstance(result, (bytes, bytearray)):
        return bytes(result)

    if isinstance(result, dict):
        # attempt simple extraction if dict contains base64 or bytes
        import base64
        for k in ("image", "images", "b64_json", "b64", "data"):
            if k in result:
                val = result[k]
                if isinstance(val, (bytes, bytearray)):
                    return bytes(val)
                if isinstance(val, str):
                    try:
                        return base64.b64decode(val)
                    except Exception:
                        pass
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, (bytes, bytearray)):
                        return bytes(first)
                    if isinstance(first, str):
                        try:
                            return base64.b64decode(first)
                        except Exception:
                            pass

    raise RuntimeError("Unable to interpret Hugging Face response returned by InferenceClient.text_to_image()")


async def generate_one(prompt: str, model: str, seed: int):
    return await asyncio.to_thread(hf_generate_image_blocking, prompt, model, seed)


async def generate_images(prompt: str, model: str = "stabilityai/stable-diffusion-xl-base-1.0"):
    tasks = []
    for _ in range(4):
        seed = randint(0, 1_000_000)  # we generate seed but currently not passed to HF (compat)
        tasks.append(asyncio.create_task(generate_one(prompt, model, seed)))

    image_bytes_list = await asyncio.gather(*tasks)
    prompt_safe = sanitize_filename(prompt)
    saved_files = []
    for i, image_bytes in enumerate(image_bytes_list, start=1):
        out_path = DATA_DIR / f"{prompt_safe}{i}.jpg"
        try:
            img = Image.open(BytesIO(image_bytes))
            img.convert("RGB").save(out_path, format="JPEG", quality=95)
            saved_files.append(out_path)
            print(f"Saved image: {out_path}")
        except Exception:
            try:
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                saved_files.append(out_path)
                print(f"Saved raw bytes to: {out_path}")
            except Exception as e:
                print(f"Failed to save image {out_path}: {e}")
    return saved_files


def GenerateImages(prompt: str):
    try:
        saved = asyncio.run(generate_images(prompt))
        print(f"Generated {len(saved)} images for prompt: {prompt}")
    except Exception as e:
        print(f"Image generation failed: {e}")
        return
    open_image(prompt)


def main_loop():
    print("Starting ImageGeneration monitor...")
    while True:
        try:
            if not CONTROL_FILE.exists():
                CONTROL_FILE.write_text(",False")
                sleep(1)
                continue

            data = CONTROL_FILE.read_text(encoding="utf-8").strip()
            if not data:
                sleep(1)
                continue

            if "," in data:
                Prompt, Status = data.rsplit(",", 1)
            else:
                Prompt, Status = "", "False"

            Prompt = Prompt.strip()
            Status = Status.strip()

            if Status.lower() in ("true", "1", "yes"):
                print(f"Generating images for prompt: '{Prompt}'")
                GenerateImages(prompt=Prompt)
                CONTROL_FILE.write_text(f"{Prompt},False", encoding="utf-8")
            else:
                sleep(1)

        except Exception as e:
            print(f"Error in main loop: {e}", file=sys.stderr)
            sleep(1)


if __name__ == "__main__":
    main_loop()
