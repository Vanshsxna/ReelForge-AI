"""Central configuration for ReelForge AI.

Everything that a beginner might want to tweak (model id, video sizes,
styles, languages, durations) lives in this one file.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# Load variables from the .env file (GEMINI_API_KEY=...). The key is never hardcoded.
load_dotenv(BASE_DIR / ".env")

APP_NAME = "ReelForge AI"
APP_TAGLINE = "Turn Your Ideas Into Engaging AI-Powered Videos."

# Existing, already-tested Gemini model ID. You can override it with
# GEMINI_MODEL=... in .env without touching the code.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"

_PLACEHOLDER_KEYS = {"", "your_actual_api_key", "your_api_key_here", "your_api_key"}


def get_api_key() -> str:
    """Return the Gemini API key from the environment ('' if missing/placeholder)."""
    key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    return "" if key.lower() in _PLACEHOLDER_KEYS else key


# ---------------------------------------------------------------- user options
DURATIONS = [30, 45, 60]  # seconds
# How many scenes Gemini is asked to write for each duration (~6-8 s per scene).
SCENES_BY_DURATION = {30: 5, 45: 6, 60: 8}
MAX_SCENES = 10

LANGUAGES = {
    "English": {"gtts": "en", "words_per_second": 2.4},
    "Hindi": {"gtts": "hi", "words_per_second": 2.3},
}

# Output sizes. 720p keeps rendering fast; change to (1080, 1920) / (1920, 1080)
# if you want Full-HD output (rendering takes ~2x longer).
VIDEO_FORMATS = {
    "Vertical (9:16) - Reels & Shorts": (720, 1280),
    "Landscape (16:9) - YouTube": (1280, 720),
}
FPS = 24

# Each style has a colour theme for the Pillow scenes and a hint for Gemini.
STYLE_THEMES = {
    "Educational": {
        "bg_top": (8, 14, 40), "bg_bottom": (22, 48, 130),
        "accent_a": (59, 130, 246), "accent_b": (34, 211, 238),
        "prompt_hint": "clear, structured and easy to learn from; explain ideas step by step with a simple example",
    },
    "Motivational": {
        "bg_top": (18, 8, 40), "bg_bottom": (82, 32, 160),
        "accent_a": (168, 85, 247), "accent_b": (244, 114, 182),
        "prompt_hint": "energetic, uplifting and direct; speak to the viewer as 'you' and end with a powerful line",
    },
    "Documentary": {
        "bg_top": (8, 10, 18), "bg_bottom": (30, 41, 70),
        "accent_a": (56, 189, 248), "accent_b": (251, 191, 36),
        "prompt_hint": "calm, cinematic narrator voice with vivid facts and a sense of scale",
    },
    "Storytelling": {
        "bg_top": (22, 8, 38), "bg_bottom": (92, 30, 140),
        "accent_a": (251, 146, 60), "accent_b": (232, 121, 249),
        "prompt_hint": "a short story with a character, a turning point and an emotional ending",
    },
    "Facts and Knowledge": {
        "bg_top": (4, 18, 38), "bg_bottom": (14, 84, 124),
        "accent_a": (45, 212, 191), "accent_b": (96, 165, 250),
        "prompt_hint": "surprising, fast-paced facts; each scene delivers one 'wow' fact",
    },
    "Technology": {
        "bg_top": (4, 8, 24), "bg_bottom": (34, 30, 88),
        "accent_a": (99, 102, 241), "accent_b": (34, 211, 238),
        "prompt_hint": "modern, sharp and forward-looking; explain how the technology works and why it matters",
    },
}
