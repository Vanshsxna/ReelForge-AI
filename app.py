"""ReelForge AI - Streamlit dashboard.  Run with:  streamlit run app.py"""
import html
import traceback

import streamlit as st

from config import (
    APP_NAME, APP_TAGLINE, DURATIONS, GEMINI_MODEL, LANGUAGES,
    STYLE_THEMES, VIDEO_FORMATS, get_api_key,
)
from modules.pipeline import run_pipeline
from modules.script_generator import ScriptError
from modules.video_assembler import VideoError
from modules.voice_generator import VoiceError
from utils.helpers import file_bytes, find_ffmpeg, has_devanagari_font

st.set_page_config(page_title=f"{APP_NAME} - AI Text-to-Video", page_icon="🎬",
                   layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------------------ CSS
st.markdown("""
<style>
.stApp { background: radial-gradient(1200px 600px at 10% -10%, rgba(99,102,241,.22), transparent 60%),
                     radial-gradient(900px 500px at 100% 0%, rgba(168,85,247,.18), transparent 55%), #070B1C; }
.block-container { padding-top: 2rem; max-width: 1400px; }
[data-testid="stSidebar"] { background: #0B1130; border-right: 1px solid rgba(255,255,255,.06); }
.rf-hero { padding: 1.6rem 1.8rem; border-radius: 20px; margin-bottom: 1.2rem;
           background: linear-gradient(135deg, rgba(59,130,246,.18), rgba(124,92,255,.18));
           border: 1px solid rgba(255,255,255,.10); }
.rf-brand { display:flex; align-items:center; gap:14px; }
.rf-logo { width:52px; height:52px; border-radius:14px; display:flex; align-items:center; justify-content:center;
           font-size:24px; color:#fff; background: linear-gradient(135deg,#3B82F6,#8B5CF6);
           box-shadow: 0 6px 24px rgba(124,92,255,.45); }
.rf-name { font-size:2rem; font-weight:800; letter-spacing:-.5px; line-height:1.1; }
.rf-name span { background: linear-gradient(90deg,#60A5FA,#A78BFA); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.rf-tag { color:#AEB8E6; font-size:.95rem; }
.rf-intro { color:#C9D1F5; margin:.9rem 0 .6rem 0; font-size:1rem; max-width: 900px; }
.rf-chip { display:inline-block; padding:.22rem .7rem; margin:.15rem .3rem .15rem 0; border-radius:999px; font-size:.78rem;
           color:#DDE3FF; background: rgba(124,92,255,.18); border:1px solid rgba(124,92,255,.35); }
.rf-card-title { font-size:1.15rem; font-weight:700; margin-bottom:.4rem; }
.rf-placeholder { border:1px dashed rgba(255,255,255,.18); border-radius:18px; padding:3rem 1.5rem; text-align:center; color:#9AA6D6;
                  background: rgba(255,255,255,.02); }
.rf-placeholder b { color:#DDE3FF; }
div[data-testid="stFormSubmitButton"] button, .stDownloadButton button[kind="primary"] {
    background: linear-gradient(90deg,#3B82F6,#8B5CF6); border:0; color:#fff; font-weight:700; padding:.7rem 1rem;
    border-radius:12px; box-shadow:0 8px 24px rgba(99,102,241,.35); }
div[data-testid="stFormSubmitButton"] button:hover { filter:brightness(1.1); }
div[data-testid="stFormSubmitButton"] button, .stDownloadButton button { width:100%; }
div[data-testid="stFormSubmitButton"], .stDownloadButton { width:100%; }
[data-testid="stForm"] { background: rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:1.2rem; }
[data-testid="stMetric"] { background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); padding:.6rem .9rem; border-radius:14px; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------- sidebar
api_ok, ffmpeg_ok = bool(get_api_key()), bool(find_ffmpeg())
with st.sidebar:
    st.markdown('<div class="rf-brand"><div class="rf-logo">▶</div><div><div class="rf-name" style="font-size:1.4rem">'
                'ReelForge <span>AI</span></div></div></div>', unsafe_allow_html=True)
    st.caption(APP_TAGLINE)
    st.markdown("#### System check")
    st.write(("✅ " if api_ok else "❌ ") + ("Gemini API key found" if api_ok else "Gemini API key missing"))
    st.write(("✅ " if ffmpeg_ok else "❌ ") + ("FFmpeg available" if ffmpeg_ok else "FFmpeg not found"))
    st.caption(f"Model: `{GEMINI_MODEL}`")
    if not api_ok:
        st.info("Create a `.env` file next to `app.py` with `GEMINI_API_KEY=your_key`, then restart the app.")
    if not ffmpeg_ok:
        st.info("Run `pip install imageio-ffmpeg` (or install FFmpeg and add it to PATH).")
    st.markdown("#### Tips")
    st.caption("• Start with 30 seconds for the fastest result.\n\n• Specific topics give better scripts "
               "(\"3 habits that improve focus\" beats \"productivity\").\n\n• Narration needs an internet connection (gTTS).")

# ----------------------------------------------------------------------- hero
st.markdown(f"""
<div class="rf-hero">
  <div class="rf-brand"><div class="rf-logo">▶</div>
    <div><div class="rf-name">ReelForge <span>AI</span></div><div class="rf-tag">{html.escape(APP_TAGLINE)}</div></div></div>
  <p class="rf-intro">Type an idea, pick a style, and ReelForge AI writes the script with Google Gemini, designs the scenes,
  records the narration, adds subtitles and renders a ready-to-post MP4 for Reels, Shorts or YouTube.</p>
  <span class="rf-chip">Gemini scripts</span><span class="rf-chip">Pillow scene design</span><span class="rf-chip">gTTS voice-over</span>
  <span class="rf-chip">Auto subtitles</span><span class="rf-chip">MoviePy + FFmpeg</span><span class="rf-chip">English &amp; Hindi</span>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------- helpers
def show_results(r):
    """Render the finished project: video, downloads, audio, script and scenes."""
    script = r["script"]
    st.markdown(f'<div class="rf-card-title">🎉 {html.escape(script["title"])}</div>', unsafe_allow_html=True)
    st.caption(script["description"])

    w, h = r["size"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Video length", f"{r['actual_duration']:.0f}s", f"target {r['target_duration']}s", delta_color="off")
    m2.metric("Resolution", f"{w}x{h}")
    m3.metric("Scenes", len(script["scenes"]))
    m4.metric("Render time", f"{r['elapsed']:.0f}s")

    video_bytes = file_bytes(r["video_path"])
    if h > w:  # vertical video: keep the player a sensible size
        vcol, dcol = st.columns([3, 4], gap="medium")
    else:
        vcol, dcol = st.container(), st.container()
    with vcol:
        st.video(video_bytes, format="video/mp4")
    with dcol:
        st.download_button("⬇️ Download Video (MP4)", video_bytes, file_name=f"{r['project_dir'].name}.mp4",
                           mime="video/mp4", type="primary")
        st.markdown("**Narration preview**")
        st.audio(file_bytes(r["narration_path"]), format="audio/mp3")
        d1, d2 = st.columns(2)
        d1.download_button("Script (.json)", file_bytes(r["script_path"]), file_name="script.json",
                           mime="application/json")
        d2.download_button("Subtitles (.srt)", file_bytes(r["srt_path"]), file_name="subtitles.srt",
                           mime="text/plain")
        st.caption(f"Saved in: `{r['project_dir']}`")
        if h > w:
            with st.expander("Generated script", expanded=True):
                show_script(script)
    if h <= w:
        with st.expander("Generated script", expanded=True):
            show_script(script)

    with st.expander("Scene images"):
        cols = st.columns(min(4, len(r["scene_paths"])))
        for i, path in enumerate(r["scene_paths"]):
            cols[i % len(cols)].image(str(path), caption=f"Scene {i + 1}")


def show_script(script):
    st.markdown("**Full narration**")
    st.write(script["narration"])
    st.markdown("**Scenes**")
    for s in script["scenes"]:
        st.markdown(f"**{s['scene_number']}. {s['on_screen_text']}**")
        st.write(s["narration"])
        st.caption(f"Visual idea: {s['visual_description']}")


def show_error(exc):
    """Turn exceptions into friendly messages instead of crashing the app."""
    if isinstance(exc, ValueError):
        st.warning(str(exc))
    elif isinstance(exc, ScriptError):
        st.error(f"**Script generation failed.** {exc}")
    elif isinstance(exc, VoiceError):
        st.error(f"**Narration failed.** {exc}")
    elif isinstance(exc, VideoError):
        st.error(f"**Video assembly failed.** {exc}")
    else:
        st.error("**Something unexpected went wrong.** Please try again; if it keeps happening, check the details below.")
        with st.expander("Technical details"):
            st.code(traceback.format_exc())


def generate(topic, duration, style, language, fmt):
    """Run the pipeline with a live progress bar; store the result in session state."""
    st.session_state.pop("result", None)
    box = st.empty()
    with box.container():
        bar = st.progress(0.0, text="Starting...")

    def on_progress(step, total, message):
        bar.progress((step - 1) / total, text=f"Step {step}/{total} - {message}")

    try:
        result = run_pipeline(topic, duration, style, language, fmt, progress=on_progress)
        bar.progress(1.0, text="Done!")
        st.session_state["result"] = result
        box.empty()
    except Exception as exc:  # noqa: BLE001 - every failure is shown to the user
        box.empty()
        show_error(exc)


# ----------------------------------------------------------------- main tabs
tab_create, tab_about = st.tabs(["🎬 Create Video", "ℹ️ How it works"])

with tab_create:
    left, right = st.columns([5, 7], gap="large")

    with left:
        st.markdown('<div class="rf-card-title">Create your video</div>', unsafe_allow_html=True)
        with st.form("generate_form"):
            topic = st.text_area("Video topic or idea", height=110, max_chars=500,
                                 placeholder="e.g. How black holes work, 5 habits of productive students, The history of chess...")
            c1, c2 = st.columns(2)
            duration = c1.selectbox("Duration", DURATIONS, format_func=lambda d: f"{d} seconds")
            style = c2.selectbox("Video style", list(STYLE_THEMES.keys()))
            language = st.radio("Language", list(LANGUAGES.keys()), horizontal=True)
            fmt = st.radio("Video format", list(VIDEO_FORMATS.keys()))
            submitted = st.form_submit_button("✨ Generate Video")
        if language == "Hindi" and not has_devanagari_font():
            st.warning("No Hindi-capable font was found on this computer, so on-screen Hindi text may look broken. "
                       "On Windows, `Nirmala UI` is normally installed; or put a Devanagari .ttf (e.g. NotoSansDevanagari-Bold.ttf) in assets/fonts/.")

    with right:
        if submitted:
            generate(topic, duration, style, language, fmt)
        if st.session_state.get("result"):
            show_results(st.session_state["result"])
        elif not submitted:
            st.markdown("""<div class="rf-placeholder"><div style="font-size:2.4rem">🎞️</div>
              <p><b>Your video will appear here.</b></p>
              <p>Enter a topic on the left and press <b>Generate Video</b>.<br>
              A 30-second video usually takes 1-2 minutes.</p></div>""", unsafe_allow_html=True)

with tab_about:
    st.markdown("""
### The pipeline
1. **Generating AI script** - Gemini returns a structured JSON script (title, description, narration, scenes). The app validates it and retries if it is malformed.
2. **Preparing scenes** - Pillow draws a gradient scene card (headline, emblem, progress bar) for every scene.
3. **Creating narration** - gTTS speaks each scene; the real audio length of each scene sets the scene duration.
4. **Generating subtitles** - each scene's narration is split into short phrases timed across that scene. *This is phrase-level timing estimated from scene audio length, not word-level synchronisation.*
5. **Assembling video** - MoviePy joins the scenes with fade transitions, burns in the subtitles and adds the narration; FFmpeg encodes H.264/AAC.
6. **Finalizing MP4** - the file is checked, saved in `outputs/<project>/` and shown here.

### Good to know
- The final length follows the narration, so it is close to (not exactly) the selected duration.
- Visuals are generated with Pillow only - no image-generation API is needed. The scene renderer is replaceable in `modules/scene_generator.py`.
- Every run creates a new folder in `outputs/`; earlier videos are never overwritten.
""")
