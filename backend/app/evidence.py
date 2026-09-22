from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def apply_watermark(
    image_path: str | Path,
    watermark_text: str,
    output_path: str | Path | None = None,
    opacity: int = 150,
) -> Path:
    """
    Applies a clean, translucent academic watermark to an evidence screenshot.
    Uses a subtle rounded backdrop pill so it is clearly readable on both dark
    terminals and light IDE/browser screens without obstructing technical details.
    """
    in_path = Path(image_path)
    out_path = Path(output_path) if output_path else in_path

    with Image.open(in_path) as base_img:
        base_rgba = base_img.convert("RGBA")
        width, height = base_rgba.size

        overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(14, min(36, int(width * 0.022)))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        padding = max(12, int(font_size * 0.8))
        x = width - text_w - padding
        y = height - text_h - padding

        if x < padding:
            x = padding
        if y < padding:
            y = padding

        bg_pad_x = 8
        bg_pad_y = 4
        pill_box = [
            x - bg_pad_x,
            y - bg_pad_y,
            x + text_w + bg_pad_x,
            y + text_h + bg_pad_y,
        ]
        draw.rounded_rectangle(pill_box, radius=4, fill=(15, 23, 42, int(opacity * 0.65)))
        draw.text((x, y), watermark_text, font=font, fill=(248, 250, 252, opacity))

        watermarked = Image.alpha_composite(base_rgba, overlay)
        orig_format = base_img.format or "PNG"
        if orig_format.upper() in ["JPEG", "JPG"]:
            watermarked.convert("RGB").save(out_path, format="JPEG", quality=92)
        else:
            watermarked.save(out_path, format="PNG")

    return out_path
