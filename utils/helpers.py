"""Small reusable helpers: file names, fonts, text wrapping, FFmpeg check."""
import re
import shutil
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from config import DURATIONS, FONTS_DIR, OUTPUT_DIR


# ------------------------------------------------------------------ validation
def validate_inputs(topic: str, duration: int) -> str:
    """Validate user input. Returns the cleaned topic or raises ValueError."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("Please enter a video topic or idea before generating.")
    if len(topic) < 3:
        raise ValueError("The topic is too short - describe your idea in a few words.")
    if len(topic) > 500:
        raise ValueError("The topic is too long - please keep it under 500 characters.")
    if duration not in DURATIONS:
        raise ValueError(f"Invalid duration. Choose one of: {', '.join(map(str, DURATIONS))} seconds.")
    return topic


# ------------------------------------------------------------------ file names
def slugify(text: str, max_len: int = 40) -> str:
    """Turn a topic into a safe folder name (ASCII only, works on Windows)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()[:max_len].strip("_")
    return slug or "video"


def create_project_dir(topic: str) -> Path:
    """Create outputs/<topic>_<timestamp>/ - a new folder each run, so nothing is overwritten."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(topic)}_{datetime.now():%Y%m%d_%H%M%S}"
    path, counter = OUTPUT_DIR / base, 1
    while path.exists():
        counter += 1
        path = OUTPUT_DIR / f"{base}_{counter}"
    path.mkdir(parents=True)
    return path


def file_bytes(path) -> bytes:
    return Path(path).read_bytes()


# ---------------------------------------------------------------------- FFmpeg
def find_ffmpeg():
    """Return the path to an FFmpeg executable, or None if none is available.

    MoviePy normally uses the FFmpeg binary bundled with `imageio-ffmpeg`
    (installed through requirements.txt), so a system FFmpeg is optional.
    """
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# ----------------------------------------------------------------------- fonts
_WIN = Path("C:/Windows/Fonts")
_LATIN_BOLD = [
    "segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "verdanab.ttf",
    "Arial Bold.ttf", "Helvetica.ttc",
    "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf",
]
_LATIN_REG = [
    "segoeui.ttf", "arial.ttf", "calibri.ttf", "Arial.ttf",
    "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf",
]
_HINDI_BOLD = [
    "NirmalaB.ttf", "Nirmala.ttc", "mangalb.ttf", "Kohinoor.ttc",
    "NotoSansDevanagari-Bold.ttf", "Lohit-Devanagari.ttf",
]
_HINDI_REG = [
    "Nirmala.ttf", "Nirmala.ttc", "mangal.ttf", "Kohinoor.ttc",
    "NotoSansDevanagari-Regular.ttf", "Lohit-Devanagari.ttf",
]
_SEARCH_DIRS = [
    FONTS_DIR, _WIN, Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"), Path("/usr/share/fonts"), Path("/usr/share/fonts/truetype"),
]


def _locate(names):
    """Find the first existing font file among `names` in the usual font folders."""
    for name in names:
        for folder in _SEARCH_DIRS:
            if not folder.exists():
                continue
            direct = folder / name
            if direct.exists():
                return str(direct)
            # Linux keeps fonts in sub-folders, so search one level deeper.
            try:
                found = next(folder.rglob(name), None)
            except OSError:
                found = None
            if found:
                return str(found)
    return None


@lru_cache(maxsize=None)
def _font_path(language: str, bold: bool):
    if language == "Hindi":
        return _locate(_HINDI_BOLD if bold else _HINDI_REG)
    return _locate(_LATIN_BOLD if bold else _LATIN_REG)


def has_devanagari_font() -> bool:
    """True if a font that can draw Hindi (Devanagari) was found on this computer."""
    return _font_path("Hindi", True) is not None or _font_path("Hindi", False) is not None


@lru_cache(maxsize=64)
def load_font(size: int, language: str = "English", bold: bool = True):
    """Load a TrueType font (Windows fonts first). Falls back to Pillow's default font."""
    path = _font_path(language, bold)
    if language == "Hindi" and path is None:
        path = _font_path("Hindi", not bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# ------------------------------------------------------------- text measuring
def text_width(font, text: str) -> float:
    try:
        return font.getlength(text)
    except AttributeError:  # very old Pillow
        return font.getsize(text)[0]


def line_height(font, factor: float = 1.15) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * factor)


def wrap_text(text: str, font, max_width: int):
    """Greedy word wrap so that no line is wider than `max_width` pixels."""
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and text_width(font, trial) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def fit_text(text, language, max_width, max_height, start_size, min_size, max_lines, bold=True):
    """Shrink the font until the wrapped text fits in the box.

    Returns (font, lines, line_height_px).
    """
    size = start_size
    while True:
        font = load_font(size, language, bold)
        lines = wrap_text(text, font, max_width)
        lh = line_height(font)
        widest = max((text_width(font, ln) for ln in lines), default=0)
        fits = len(lines) <= max_lines and lh * len(lines) <= max_height and widest <= max_width
        if fits or size <= min_size:
            return font, lines, lh
        size -= 2


def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
