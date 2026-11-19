"""Script generation with Google Gemini (structured JSON, validated)."""
import json
import re
import time

from config import (
    GEMINI_MODEL,
    LANGUAGES,
    MAX_SCENES,
    SCENES_BY_DURATION,
    STYLE_THEMES,
    get_api_key,
)


class ScriptError(Exception):
    """Raised when the script cannot be generated. The message is shown to the user."""


# --------------------------------------------------------------------- prompt
def build_prompt(topic, duration, style, language, num_scenes, extra_note=""):
    words_per_second = LANGUAGES[language]["words_per_second"]
    total_words = round(duration * words_per_second)
    per_scene = round(total_words / num_scenes)
    hint = STYLE_THEMES[style]["prompt_hint"]

    example = {
        "title": "Catchy video title",
        "description": "One or two sentence description for the video caption.",
        "narration": "The complete narration: all scene narrations joined together.",
        "scenes": [
            {
                "scene_number": 1,
                "narration": "Narration spoken during this scene.",
                "visual_description": "One sentence describing the visuals for this scene (in English).",
                "on_screen_text": "Short headline (max 6 words)",
            }
        ],
    }
    lang_rule = (
        "Write title, description, narration and on_screen_text in Hindi using Devanagari script."
        if language == "Hindi"
        else "Write title, description, narration and on_screen_text in English."
    )
    prompt = f"""You are a professional short-form video scriptwriter.
Write a script for a {duration}-second vertical/landscape social media video.

Topic: {topic}
Style: {style} - {hint}
Language: {language}

Rules:
- {lang_rule}
- Use exactly {num_scenes} scenes. Scene 1 is a strong, attention-grabbing hook. The last scene is a conclusion with a short call to action (like, follow, share) where appropriate.
- The whole narration must be about {total_words} words (roughly {per_scene} words per scene) so that it can be spoken in {duration} seconds.
- Narration is plain spoken text only: no emojis, no markdown, no stage directions, no scene labels.
- on_screen_text is a punchy headline of at most 6 words.
- visual_description is always written in English.
- The top-level "narration" must equal the scene narrations joined in order.
- Be factual and avoid made-up statistics.

Return ONLY one valid JSON object (no markdown fences, no commentary) with exactly this structure:
{json.dumps(example, ensure_ascii=False, indent=2)}
"""
    if extra_note:
        prompt += f"\nIMPORTANT CORRECTION: {extra_note}\n"
    return prompt


# ----------------------------------------------------------------- Gemini call
def _call_gemini(prompt: str, api_key: str) -> str:
    """Send the prompt to Gemini and return the raw text of the reply.

    This is the ONLY function that talks to the Gemini SDK. If your existing
    Gemini code differs (e.g. different client setup), adapt just this function.
    """
    from google import genai  # imported here so a missing package gives a friendly error
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    return response.text or ""


def _friendly_gemini_error(exc: Exception) -> ScriptError:
    """Translate raw SDK/network exceptions into messages a user can act on."""
    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()
    if isinstance(exc, ImportError):
        return ScriptError("The `google-genai` package is not installed. Run: pip install -r requirements.txt")
    if "api key not valid" in low or "api_key_invalid" in low or "invalid api key" in low or "api key expired" in low:
        return ScriptError("Your Gemini API key was rejected as invalid. Check GEMINI_API_KEY in the .env file, then restart the app.")
    if "429" in low or "resource_exhausted" in low or "quota" in low:
        return ScriptError("Gemini rate limit or quota reached. Wait a minute and try again, or check your API quota.")
    if "permission_denied" in low or "403" in low:
        return ScriptError("Gemini denied access (permission error). Check that your API key is allowed to use this model.")
    if "not_found" in low or "404" in low or "is not found" in low:
        return ScriptError(
            f"Gemini could not find the model `{GEMINI_MODEL}`. "
            "Set GEMINI_MODEL in .env to a model ID that works with your key."
        )
    if any(w in low for w in ("getaddrinfo", "connecterror", "connection", "timed out", "timeout", "name resolution")):
        return ScriptError("Could not reach the Gemini API. Check your internet connection and try again.")
    if "400" in low or "invalid_argument" in low:
        return ScriptError(f"Gemini rejected the request: {exc}")
    return ScriptError(f"Gemini API error: {exc}")


def _is_transient(exc: Exception) -> bool:
    low = str(exc).lower()
    return any(w in low for w in ("503", "unavailable", "overloaded", "500", "internal", "timed out", "timeout"))


# ------------------------------------------------------------- JSON handling
def _extract_json(text: str):
    """Parse JSON even if the model wrapped it in ```json fences or added extra text."""
    if not text or not text.strip():
        raise ValueError("Gemini returned an empty response.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _clean(value) -> str:
    """Convert to a tidy single-line string (removes markdown symbols)."""
    if value is None:
        return ""
    text = re.sub(r"[*#_`]+", "", str(value))
    return re.sub(r"\s+", " ", text).strip()


def _shorten(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def validate_script(data, topic: str) -> dict:
    """Check the structure of Gemini's JSON and repair small gaps. Raises ValueError if unusable."""
    if not isinstance(data, dict):
        raise ValueError("The JSON is not an object.")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("The JSON has no 'scenes' list.")

    scenes = []
    for item in raw_scenes[:MAX_SCENES]:
        if not isinstance(item, dict):
            continue
        narration = _clean(item.get("narration") or item.get("scene_narration"))
        if not narration:
            continue
        on_screen = _clean(item.get("on_screen_text") or item.get("title"))
        if not on_screen:  # fall back to the first words of the narration
            on_screen = " ".join(narration.split()[:5])
        scenes.append({
            "scene_number": len(scenes) + 1,
            "narration": narration,
            "visual_description": _clean(item.get("visual_description")) or "Abstract gradient background",
            "on_screen_text": _shorten(on_screen, 60),
        })
    if len(scenes) < 2:
        raise ValueError("The JSON contains fewer than 2 usable scenes.")

    full_narration = " ".join(s["narration"] for s in scenes)  # audio is built from the scenes
    return {
        "title": _shorten(_clean(data.get("title")) or topic.strip().capitalize(), 100),
        "description": _clean(data.get("description")) or scenes[0]["narration"],
        "narration": full_narration,
        "scenes": scenes,
    }


# ----------------------------------------------------------------- public API
def generate_script(topic: str, duration: int, style: str, language: str) -> dict:
    """Ask Gemini for a structured script and return the validated dict."""
    api_key = get_api_key()
    if not api_key:
        raise ScriptError(
            "No Gemini API key found. Create a `.env` file next to app.py containing "
            "GEMINI_API_KEY=your_key and restart the app."
        )

    num_scenes = SCENES_BY_DURATION[duration]
    target_words = duration * LANGUAGES[language]["words_per_second"]
    note, best, last_problem = "", None, "unknown problem"
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        prompt = build_prompt(topic, duration, style, language, num_scenes, note)
        try:
            raw = _call_gemini(prompt, api_key)
        except Exception as exc:  # noqa: BLE001 - mapped to friendly errors below
            if _is_transient(exc) and attempt < max_attempts:
                time.sleep(2 * attempt)
                continue
            raise _friendly_gemini_error(exc) from exc

        try:
            script = validate_script(_extract_json(raw), topic)
        except (ValueError, json.JSONDecodeError) as exc:
            last_problem = str(exc)
            note = ("Your previous reply was not valid JSON in the required structure "
                    f"({last_problem}). Reply with ONLY the JSON object.")
            continue

        best = script
        words = len(script["narration"].split())
        if 0.6 * target_words <= words <= 1.4 * target_words:
            return script
        note = (f"Your previous narration had {words} words but about {round(target_words)} "
                f"words are needed for {duration} seconds. Adjust the length.")

    if best:  # length was off but the script is valid - still usable
        return best
    raise ScriptError(
        "Gemini returned a response that could not be read as a valid script "
        f"after {max_attempts} attempts ({last_problem}). Please try again or rephrase your topic."
    )
