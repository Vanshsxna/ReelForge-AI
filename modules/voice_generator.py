"""Narration with gTTS (Google Text-to-Speech). Needs an internet connection."""
import re
import shutil
import time
from pathlib import Path

from config import LANGUAGES
from utils.moviepy_compat import AudioFileClip, concatenate_audioclips, safe_close


class VoiceError(Exception):
    """Raised when narration audio cannot be generated."""


def clean_for_speech(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*#_`~]+", " ", text)).strip()


def _synthesize(text: str, lang: str, path: Path, attempts: int = 3):
    """Convert one piece of text to an MP3 file, retrying on temporary network errors."""
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise VoiceError("The `gTTS` package is not installed. Run: pip install -r requirements.txt") from exc

    last = None
    for attempt in range(1, attempts + 1):
        try:
            gTTS(text=text, lang=lang, slow=False).save(str(path))
            if path.exists() and path.stat().st_size > 0:
                return
            last = RuntimeError("empty audio file")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * attempt)
    raise VoiceError(
        "Could not create the narration with Google Text-to-Speech. "
        "Check your internet connection and try again. "
        f"(Details: {type(last).__name__}: {last})"
    )


def generate_narration(scenes, language, project_dir, progress_cb=None):
    """Create narration.mp3 and return (path, [real audio duration of each scene]).

    Each scene is spoken separately so we know exactly how long it lasts; the
    video scenes later use these durations, which keeps picture and voice in sync.
    """
    lang = LANGUAGES[language]["gtts"]
    project_dir = Path(project_dir)
    tmp_dir = project_dir / "_tmp_audio"
    tmp_dir.mkdir(exist_ok=True)
    output = project_dir / "narration.mp3"

    clips, durations, merged = [], [], None
    try:
        for i, scene in enumerate(scenes, start=1):
            if progress_cb:
                progress_cb(f"Narrating scene {i} of {len(scenes)}")
            part = tmp_dir / f"scene_{i}.mp3"
            _synthesize(clean_for_speech(scene["narration"]), lang, part)
            clip = AudioFileClip(str(part))
            clips.append(clip)
            durations.append(float(clip.duration))

        merged = concatenate_audioclips(clips)
        merged.write_audiofile(str(output), logger=None)
    except VoiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"Could not process the narration audio (is FFmpeg available?): {exc}") from exc
    finally:
        safe_close(merged, *clips)
        shutil.rmtree(tmp_dir, ignore_errors=True)  # remove temporary per-scene audio

    if not output.exists() or output.stat().st_size == 0:
        raise VoiceError("The narration file was not created.")
    return output, durations
