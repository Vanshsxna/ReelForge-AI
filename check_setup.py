"""Run this BEFORE the first demo:   python check_setup.py   (add --gemini to test the API too)

It verifies imports, your MoviePy version, FFmpeg, fonts, the API key, and renders a
2-second test MP4 so you know the video pipeline works on this computer.
"""
import sys
import tempfile
from pathlib import Path

OK, BAD = "[ OK ]", "[FAIL]"
problems = 0


def check(label, fn):
    global problems
    try:
        detail = fn()
        print(f"{OK} {label}" + (f" - {detail}" if detail else ""))
    except Exception as exc:  # noqa: BLE001
        problems += 1
        print(f"{BAD} {label} - {type(exc).__name__}: {exc}")


def version_of(module_name):
    def _inner():
        module = __import__(module_name)
        return getattr(module, "__version__", "installed")
    return _inner


print(f"Python {sys.version.split()[0]}\n")
for pkg in ["streamlit", "google.genai", "gtts", "PIL", "numpy", "dotenv", "imageio_ffmpeg", "moviepy"]:
    check(f"import {pkg}", version_of(pkg))

from utils.helpers import find_ffmpeg, has_devanagari_font  # noqa: E402
from config import GEMINI_MODEL, get_api_key  # noqa: E402

check("MoviePy compatibility layer", lambda: __import__("utils.moviepy_compat", fromlist=["x"]).MOVIEPY_MAJOR.__str__() and
      f"MoviePy {__import__('utils.moviepy_compat', fromlist=['x']).MOVIEPY_MAJOR}.x API in use")
check("FFmpeg", lambda: find_ffmpeg() or (_ for _ in ()).throw(RuntimeError("not found - run: pip install imageio-ffmpeg")))
check("GEMINI_API_KEY in .env", lambda: "found" if get_api_key() else (_ for _ in ()).throw(RuntimeError("missing - copy .env.example to .env and add your key")))
print(f"{OK if has_devanagari_font() else '[WARN]'} Hindi font - " + ("found" if has_devanagari_font() else
      "not found; only matters for Hindi videos (put a Devanagari .ttf in assets/fonts/)"))


def render_test_video():
    from modules.scene_generator import generate_scene_images
    from modules.subtitle_generator import build_timelines
    from modules.video_assembler import _make_scene_clip
    from utils.moviepy_compat import concatenate_videoclips, safe_close

    scenes = [{"on_screen_text": "ReelForge test", "narration": "This is a short test of the video pipeline.", "scene_number": 1}]
    with tempfile.TemporaryDirectory() as tmp:
        image = generate_scene_images(scenes, (720, 1280), "Technology", "English", tmp)[0]
        timeline = build_timelines(scenes, [2.0], (720, 1280))[0]
        clip = concatenate_videoclips([_make_scene_clip(image, timeline, 2.0, "English")], method="chain")
        out = Path(tmp) / "test.mp4"
        try:
            clip.write_videofile(str(out), fps=24, codec="libx264", preset="ultrafast",
                                 ffmpeg_params=["-pix_fmt", "yuv420p"], logger=None)
        finally:
            safe_close(clip)
        return f"wrote {out.stat().st_size // 1024} KB test MP4"


check("Render a 2-second test video (Pillow + MoviePy + FFmpeg)", render_test_video)

if "--gemini" in sys.argv:
    def gemini_test():
        from modules.script_generator import _call_gemini
        reply = _call_gemini('Reply with exactly this JSON: {"ok": true}', get_api_key())
        return f"model {GEMINI_MODEL} replied: {reply.strip()[:40]}"
    check("Live Gemini API call", gemini_test)
else:
    print(f"      (run `python check_setup.py --gemini` to also test the live Gemini call, model: {GEMINI_MODEL})")

print("\nAll checks passed - you're ready: streamlit run app.py" if not problems else f"\n{problems} check(s) failed - fix them before running the app.")
