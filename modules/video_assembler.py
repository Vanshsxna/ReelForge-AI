"""Video assembly with MoviePy (FFmpeg does the encoding).

Each scene is a MoviePy clip whose frames are produced by a small function:
  scene image + current subtitle phrase (+ fade-in / fade-out for transitions).
Subtitles are drawn with Pillow, so no ImageMagick installation is needed.
"""
from bisect import bisect_right
from pathlib import Path

import numpy as np
from PIL import Image

from config import FPS
from modules.subtitle_generator import draw_subtitle
from utils.helpers import find_ffmpeg
from utils.moviepy_compat import (
    AudioFileClip,
    VideoClip,
    concatenate_videoclips,
    safe_close,
    with_audio,
)

FADE_SECONDS = 0.3  # fade-in/out at each scene boundary (dip-to-black transition)


class VideoError(Exception):
    """Raised when the video cannot be assembled."""


def _make_scene_clip(image_path, timeline, duration, language):
    """Build one video clip: static scene image + timed subtitle phrases + fades."""
    base = Image.open(image_path).convert("RGB")
    starts = [item["start"] for item in timeline]
    fade = min(FADE_SECONDS, duration / 4)
    cache = {}

    def subtitle_frame(idx):
        if idx not in cache:
            cache.clear()  # keep only the current phrase in memory
            cache[idx] = np.array(draw_subtitle(base, timeline[idx]["text"], language))
        return cache[idx]

    def make_frame(t):
        idx = max(0, bisect_right(starts, t) - 1)
        frame = subtitle_frame(idx)
        alpha = 1.0
        if t < fade:
            alpha = t / fade
        if t > duration - fade:
            alpha = min(alpha, (duration - t) / fade)
        alpha = max(0.0, min(1.0, alpha))
        if alpha < 1.0:
            frame = (frame * alpha).astype(np.uint8)
        return frame

    return VideoClip(make_frame, duration=duration)


def assemble_video(scene_images, timelines, durations, narration_path, output_path, language, fps=FPS):
    """Combine scenes, subtitles and narration into an H.264/AAC MP4. Returns the output path."""
    if not find_ffmpeg():
        raise VideoError(
            "FFmpeg was not found. Run `pip install imageio-ffmpeg` (included in requirements.txt) "
            "or install FFmpeg from https://ffmpeg.org and add it to your PATH."
        )

    output_path = Path(output_path)
    clips, audio, final = [], None, None
    try:
        audio = AudioFileClip(str(narration_path))
        durations = list(durations)
        # The merged MP3 can differ from the sum of the parts by a few milliseconds:
        # give the difference to the last scene so video and audio end together.
        diff = float(audio.duration) - sum(durations)
        if abs(diff) < 1.5:
            durations[-1] = max(0.5, durations[-1] + diff)

        for image, timeline, duration in zip(scene_images, timelines, durations):
            clips.append(_make_scene_clip(image, timeline, duration, language))

        final = concatenate_videoclips(clips, method="chain")
        final = with_audio(final, audio)
        final.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="veryfast",
            threads=4,
            # yuv420p + faststart = plays in every browser/phone, including Streamlit's player
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            temp_audiofile=str(output_path.with_suffix(".tmp_audio.m4a")),
            remove_temp=True,
            logger=None,
        )
    except VideoError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VideoError(f"Video rendering failed: {type(exc).__name__}: {exc}") from exc
    finally:
        safe_close(final, *clips, audio)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise VideoError("FFmpeg finished but the MP4 file was not created.")
    return output_path
