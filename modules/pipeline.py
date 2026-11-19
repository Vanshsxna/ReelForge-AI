"""The full generation pipeline: topic -> script -> scenes -> voice -> subtitles -> MP4.

The Streamlit UI (app.py) only calls `run_pipeline`; all the real work lives in modules/.
"""
import json
import time
from datetime import datetime

from config import GEMINI_MODEL, VIDEO_FORMATS, get_api_key
from modules.scene_generator import generate_scene_images
from modules.script_generator import ScriptError, generate_script
from modules.subtitle_generator import build_timelines, write_srt
from modules.video_assembler import VideoError, assemble_video
from modules.voice_generator import generate_narration
from utils.helpers import create_project_dir, find_ffmpeg, validate_inputs

PIPELINE_STEPS = [
    "Generating AI script",
    "Preparing scenes",
    "Creating narration",
    "Generating subtitles",
    "Assembling video",
    "Finalizing MP4",
]


def run_pipeline(topic, duration, style, language, video_format, progress=None):
    """Run every step and return a dict describing the generated project.

    `progress(step_number, total_steps, message)` is called as each step starts.
    Raises ValueError (bad input), ScriptError, VoiceError or VideoError.
    """
    started = time.time()
    total = len(PIPELINE_STEPS)

    def report(step, extra=""):
        if progress:
            label = PIPELINE_STEPS[step - 1] + (f" - {extra}" if extra else "")
            progress(step, total, label)

    # --- pre-flight checks: fail fast, before any slow work ---------------------
    topic = validate_inputs(topic, duration)
    if video_format not in VIDEO_FORMATS:
        raise ValueError("Invalid video format selected.")
    if not get_api_key():
        raise ScriptError("No Gemini API key found. Add GEMINI_API_KEY to the .env file and restart the app.")
    if not find_ffmpeg():
        raise VideoError("FFmpeg was not found. Run `pip install imageio-ffmpeg` or install FFmpeg and add it to PATH.")

    size = VIDEO_FORMATS[video_format]
    project_dir = create_project_dir(topic)

    # 1) script -----------------------------------------------------------------
    report(1)
    script = generate_script(topic, duration, style, language)
    script_path = project_dir / "script.json"
    script_path.write_text(
        json.dumps(
            {
                **script,
                "settings": {
                    "topic": topic, "duration_target": duration, "style": style,
                    "language": language, "format": video_format,
                    "model": GEMINI_MODEL, "created": datetime.now().isoformat(timespec="seconds"),
                },
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    scenes = script["scenes"]

    # 2) scene images -----------------------------------------------------------
    report(2)
    scene_paths = generate_scene_images(scenes, size, style, language, project_dir)

    # 3) narration (also gives the real duration of every scene) ----------------
    report(3)
    narration_path, durations = generate_narration(
        scenes, language, project_dir, progress_cb=lambda msg: report(3, msg)
    )

    # 4) subtitles --------------------------------------------------------------
    report(4)
    timelines = build_timelines(scenes, durations, size)
    srt_path = write_srt(timelines, durations, project_dir / "subtitles.srt")

    # 5) video assembly ---------------------------------------------------------
    report(5, "rendering frames, this can take a minute")
    video_path = project_dir / "final_video.mp4"
    assemble_video(scene_paths, timelines, durations, narration_path, video_path, language)

    # 6) finalize ---------------------------------------------------------------
    report(6)
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise VideoError("The final MP4 is missing or empty.")

    return {
        "project_dir": project_dir,
        "video_path": video_path,
        "narration_path": narration_path,
        "script_path": script_path,
        "srt_path": srt_path,
        "scene_paths": scene_paths,
        "script": script,
        "target_duration": duration,
        "actual_duration": sum(durations),
        "size": size,
        "style": style,
        "language": language,
        "elapsed": time.time() - started,
    }
