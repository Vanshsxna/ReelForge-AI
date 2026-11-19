"""MoviePy 1.x / 2.x compatibility layer.

MoviePy 2.0 changed its import paths (moviepy.editor was removed) and renamed
methods such as set_audio -> with_audio. Everything else in the project imports
MoviePy only from this file, so the rest of the code works with either version.
"""
try:  # MoviePy 2.x
    from moviepy import (
        AudioFileClip,
        VideoClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )
    MOVIEPY_MAJOR = 2
except ImportError:
    try:  # MoviePy 1.x
        from moviepy.editor import (
            AudioFileClip,
            VideoClip,
            concatenate_audioclips,
            concatenate_videoclips,
        )
        MOVIEPY_MAJOR = 1
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "MoviePy is not installed. Run: pip install -r requirements.txt"
        ) from exc


def with_audio(clip, audio):
    """Attach an audio clip to a video clip (works on MoviePy 1.x and 2.x)."""
    method = getattr(clip, "with_audio", None) or getattr(clip, "set_audio")
    return method(audio)


def safe_close(*clips):
    """Close clips quietly (needed on Windows so files can be deleted afterwards)."""
    for clip in clips:
        try:
            if clip is not None:
                clip.close()
        except Exception:
            pass
