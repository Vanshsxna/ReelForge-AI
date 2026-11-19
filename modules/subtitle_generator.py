"""Subtitle generation: timing + drawing.

Timing is ESTIMATED at phrase level: each scene's real audio duration is known,
and the scene narration is split into short phrases whose on-screen time is
proportional to their length. This is NOT word-level synchronisation.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from utils.helpers import fit_text, format_srt_time, line_height, text_width

PUNCTUATION_END = (".", "!", "?", "।", ",", ";", ":", "…")


def split_into_chunks(text: str, max_words: int = 6):
    """Split narration into short subtitle phrases (prefers breaking at punctuation)."""
    chunks, current = [], []
    for word in text.split():
        current.append(word)
        if len(current) >= max_words or (word.endswith(PUNCTUATION_END) and len(current) >= 3):
            chunks.append(current)
            current = []
    if current:
        if chunks and len(current) <= 2:  # avoid a lonely 1-2 word subtitle
            chunks[-1].extend(current)
        else:
            chunks.append(current)
    return [" ".join(c) for c in chunks]


def build_scene_timeline(narration: str, scene_duration: float, max_words: int):
    """Return [{'start','end','text'}] relative to the start of the scene."""
    chunks = split_into_chunks(narration, max_words) or [narration]
    weights = [max(len(c), 1) for c in chunks]
    total = float(sum(weights))
    timeline, cursor = [], 0.0
    for chunk, weight in zip(chunks, weights):
        length = scene_duration * weight / total
        timeline.append({"start": cursor, "end": cursor + length, "text": chunk})
        cursor += length
    return timeline


def build_timelines(scenes, durations, size):
    """Subtitle timelines for every scene. Landscape videos fit more words per line."""
    width, height = size
    max_words = 6 if height > width else 9
    return [build_scene_timeline(s["narration"], d, max_words) for s, d in zip(scenes, durations)]


def write_srt(timelines, durations, path) -> Path:
    """Save a standard .srt subtitle file (global times, phrase-level accuracy)."""
    lines, offset, index = [], 0.0, 1
    for timeline, duration in zip(timelines, durations):
        for item in timeline:
            lines += [
                str(index),
                f"{format_srt_time(offset + item['start'])} --> {format_srt_time(offset + item['end'])}",
                item["text"],
                "",
            ]
            index += 1
        offset += duration
    path = Path(path)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def draw_subtitle(base: Image.Image, text: str, language: str = "English") -> Image.Image:
    """Draw a subtitle box (white text on dark rounded box) at the bottom of a frame.

    Returns a NEW RGB image; `base` is not modified. The text is wrapped and the
    font shrunk if needed, so it never leaves the video boundaries.
    """
    width, height = base.size
    unit = min(width, height) / 720.0
    vertical = height > width

    max_text_w = int(width * (0.80 if vertical else 0.70))
    pad_x, pad_y = int(22 * unit), int(14 * unit)
    font, lines, lh = fit_text(
        text, language, max_text_w, int(height * 0.20),
        start_size=int(42 * unit), min_size=int(24 * unit), max_lines=3,
    )

    block_w = int(max(text_width(font, ln) for ln in lines)) + 2 * pad_x
    block_h = lh * len(lines) + 2 * pad_y
    block_w = min(block_w, int(width * 0.94))
    # Keep subtitles above the area covered by Reels/Shorts buttons.
    bottom = int(height * (0.84 if vertical else 0.91))
    x0 = (width - block_w) // 2
    y0 = bottom - block_h

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle([x0, y0, x0 + block_w, y0 + block_h], radius=int(18 * unit), fill=(5, 8, 20, 205))
    draw.rounded_rectangle([x0, y0, x0 + block_w, y0 + block_h], radius=int(18 * unit),
                           outline=(255, 255, 255, 40), width=max(1, int(2 * unit)))
    y = y0 + pad_y
    for line in lines:
        draw.text(((width - text_width(font, line)) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
