"""Scene image generation with Pillow.

The renderer is replaceable: subclass `SceneRenderer` (for example to call an
image-generation API in the future) and pass it to `generate_scene_images(...)`.
The default `PillowSceneRenderer` needs no external service.
"""
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from config import APP_NAME, STYLE_THEMES
from utils.helpers import fit_text, load_font, text_width


class SceneRenderer:
    """Interface for anything that can turn a scene into a background image."""

    def render(self, scene: dict, index: int, total: int, size, style: str, language: str) -> Image.Image:
        raise NotImplementedError


# --------------------------------------------------------------- drawing utils
def _gradient(size, top, bottom, mode):
    """Smooth two-colour gradient. mode 0 = vertical, 1 = diagonal, 2 = reversed diagonal."""
    w, h = size
    ys = np.linspace(0, 1, h)[:, None]
    xs = np.linspace(0, 1, w)[None, :]
    if mode == 0:
        t = ys + 0 * xs
    elif mode == 1:
        t = (xs + ys) / 2
    else:
        t = ((1 - xs) + ys) / 2
    top, bottom = np.array(top, dtype=float), np.array(bottom, dtype=float)
    arr = top[None, None, :] * (1 - t)[..., None] + bottom[None, None, :] * t[..., None]
    return Image.fromarray(arr.astype("uint8"), "RGB")


def _glow_layer(size, circles, blur):
    """Soft coloured light blobs. circles = [(cx, cy, radius, rgb, alpha)]."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for cx, cy, r, rgb, alpha in circles:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*rgb, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _emblem(draw, kind, cx, cy, r, accent_a, accent_b):
    """Simple flat 'illustration' above the headline card. Five variants."""
    a, b, white = accent_a, accent_b, (255, 255, 255)
    if kind == 0:  # concentric rings
        for i, rr in enumerate((r, r * 0.72, r * 0.44)):
            draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(*(a if i % 2 == 0 else b), 230), width=max(4, int(r * 0.09)))
        draw.ellipse([cx - r * 0.18, cy - r * 0.18, cx + r * 0.18, cy + r * 0.18], fill=(*white, 240))
    elif kind == 1:  # play button
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*a, 235))
        draw.ellipse([cx - r * 0.82, cy - r * 0.82, cx + r * 0.82, cy + r * 0.82], outline=(*white, 120), width=3)
        draw.polygon([(cx - r * 0.25, cy - r * 0.42), (cx - r * 0.25, cy + r * 0.42), (cx + r * 0.45, cy)], fill=(*white, 255))
    elif kind == 2:  # rising bars
        bar_w, gap = r * 0.36, r * 0.16
        total = 4 * bar_w + 3 * gap
        x = cx - total / 2
        for i, hgt in enumerate((0.9, 1.3, 1.7, 2.1)):
            top = cy + r - hgt * r * 0.9
            draw.rounded_rectangle([x, top, x + bar_w, cy + r], radius=int(bar_w * 0.3), fill=(*(a if i % 2 == 0 else b), 235))
            x += bar_w + gap
    elif kind == 3:  # hexagon
        import math
        def hexagon(rad):
            return [(cx + rad * math.cos(math.radians(60 * k + 30)), cy + rad * math.sin(math.radians(60 * k + 30))) for k in range(6)]
        draw.polygon(hexagon(r), fill=(*a, 90), outline=(*a, 255))
        draw.polygon(hexagon(r * 0.6), fill=(*b, 220))
        draw.line(hexagon(r) + [hexagon(r)[0]], fill=(*white, 200), width=3)
    else:  # four-point sparkle
        pts = [(cx, cy - r), (cx + r * 0.22, cy - r * 0.22), (cx + r, cy), (cx + r * 0.22, cy + r * 0.22),
               (cx, cy + r), (cx - r * 0.22, cy + r * 0.22), (cx - r, cy), (cx - r * 0.22, cy - r * 0.22)]
        draw.polygon(pts, fill=(*a, 240))
        s = r * 0.45
        small = [(cx + r * 0.85, cy - r * 0.85 - s), (cx + r * 0.85 + s * 0.2, cy - r * 0.85 - s * 0.2), (cx + r * 0.85 + s, cy - r * 0.85),
                 (cx + r * 0.85 + s * 0.2, cy - r * 0.85 + s * 0.2), (cx + r * 0.85, cy - r * 0.85 + s), (cx + r * 0.85 - s * 0.2, cy - r * 0.85 + s * 0.2),
                 (cx + r * 0.85 - s, cy - r * 0.85), (cx + r * 0.85 - s * 0.2, cy - r * 0.85 - s * 0.2)]
        draw.polygon(small, fill=(*b, 240))


# ------------------------------------------------------------ default renderer
class PillowSceneRenderer(SceneRenderer):
    """Gradient background + glow + dot grid + emblem + glass headline card."""

    def render(self, scene, index, total, size, style, language):
        width, height = size
        unit = min(width, height) / 720.0
        vertical = height > width
        theme = STYLE_THEMES[style]
        rng = random.Random(f"{scene['on_screen_text']}-{index}")  # deterministic per scene

        # 1) background gradient (direction changes per scene for variety)
        image = _gradient(size, theme["bg_top"], theme["bg_bottom"], (index - 1) % 3).convert("RGBA")

        # 2) soft glows in the accent colours
        glows = []
        for k in range(3):
            colour = theme["accent_a"] if k % 2 == 0 else theme["accent_b"]
            glows.append((rng.randint(0, width), rng.randint(0, height),
                          int(min(width, height) * rng.uniform(0.25, 0.45)), colour, 120))
        image = Image.alpha_composite(image, _glow_layer(size, glows, blur=int(90 * unit)))

        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 3) subtle dot grid in one corner
        step, dot = int(46 * unit), max(2, int(3 * unit))
        gx0 = width - int(width * 0.38) if index % 2 else int(width * 0.04)
        gy0 = int(height * 0.60) if vertical else int(height * 0.58)
        for gx in range(gx0, gx0 + int(width * 0.34), step):
            for gy in range(gy0, min(height, gy0 + int(height * 0.26)), step):
                draw.ellipse([gx, gy, gx + dot, gy + dot], fill=(255, 255, 255, 38))

        # 4) top progress segments (scene i of N) + scene badge + brand
        margin = int(34 * unit)
        gap = int(8 * unit)
        seg_w = (width - 2 * margin - gap * (total - 1)) / total
        for k in range(total):
            x0 = margin + k * (seg_w + gap)
            colour = (*theme["accent_b"], 255) if k < index else (255, 255, 255, 60)
            draw.rounded_rectangle([x0, int(30 * unit), x0 + seg_w, int(30 * unit) + max(4, int(7 * unit))], radius=4, fill=colour)

        small = load_font(int(26 * unit), language="English", bold=True)
        badge = f"{index:02d} / {total:02d}"
        bw = text_width(small, badge) + 2 * int(18 * unit)
        by = int(62 * unit)
        bh = int(46 * unit)
        draw.rounded_rectangle([margin, by, margin + bw, by + bh], radius=bh // 2, fill=(*theme["accent_a"], 210))
        draw.text((margin + int(18 * unit), by + int(6 * unit)), badge, font=small, fill=(255, 255, 255, 255))
        brand = APP_NAME.upper()
        draw.text((width - margin - text_width(small, brand), by + int(6 * unit)), brand, font=small, fill=(255, 255, 255, 150))

        # 5) emblem + glass headline card
        #    Vertical: emblem above the card. Landscape: emblem to the left of the card.
        pad = int(44 * unit)
        if vertical:
            card_w, card_cx, card_cy = int(width * 0.86), width // 2, height * 0.47
            max_text_h, start_size = int(height * 0.30), int(80 * unit)
        else:
            card_w, card_cx, card_cy = int(width * 0.58), int(width * 0.64), height * 0.42
            max_text_h, start_size = int(height * 0.26), int(64 * unit)
        font, lines, lh = fit_text(scene["on_screen_text"], language, card_w - 2 * pad, max_text_h,
                                   start_size=start_size, min_size=int(34 * unit), max_lines=4)
        card_h = lh * len(lines) + 2 * pad
        cx0, cy0 = int(card_cx - card_w / 2), int(card_cy - card_h / 2)

        if vertical:
            emblem_r = int(width * 0.12)
            emblem_x, emblem_y = width // 2, cy0 - emblem_r - int(40 * unit)
        else:
            emblem_r = int(height * 0.14)
            emblem_x, emblem_y = int(width * 0.16), int(card_cy)
        _emblem(draw, (index - 1) % 5, emblem_x, emblem_y, emblem_r, theme["accent_a"], theme["accent_b"])

        draw.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h], radius=int(36 * unit),
                               fill=(255, 255, 255, 30), outline=(255, 255, 255, 80), width=max(2, int(2 * unit)))
        bar_w = int(card_w * 0.22)
        draw.rounded_rectangle([card_cx - bar_w // 2, cy0 + int(14 * unit), card_cx + bar_w // 2, cy0 + int(14 * unit) + max(4, int(7 * unit))],
                               radius=4, fill=(*theme["accent_b"], 255))
        y = cy0 + pad
        for line in lines:
            x = card_cx - text_width(font, line) / 2
            draw.text((x + 2 * unit, y + 3 * unit), line, font=font, fill=(0, 0, 0, 110))  # soft shadow
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += lh

        return Image.alpha_composite(image, overlay).convert("RGB")


_DEFAULT_RENDERER = PillowSceneRenderer()


def generate_scene_images(scenes, size, style, language, project_dir, renderer=None):
    """Render and save scene_1.png, scene_2.png, ... Returns the list of file paths."""
    renderer = renderer or _DEFAULT_RENDERER
    paths = []
    for i, scene in enumerate(scenes, start=1):
        image = renderer.render(scene, i, len(scenes), size, style, language)
        path = Path(project_dir) / f"scene_{i}.png"
        image.save(path)
        paths.append(path)
    return paths
