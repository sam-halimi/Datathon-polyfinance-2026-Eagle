"""PNG de web/scripts/captures.js -> WebP allégés dans web/public/presentation/ (largeur 1100 px au plus)."""
from pathlib import Path

from PIL import Image

DOSSIER = Path(__file__).resolve().parents[1] / "public" / "presentation"
for png in sorted(DOSSIER.glob("*.png")):
    image = Image.open(png).convert("RGB")
    if image.width > 1100:
        image = image.resize((1100, round(image.height * 1100 / image.width)), Image.LANCZOS)
    cible = png.with_suffix(".webp")
    image.save(cible, "WEBP", quality=82, method=6)
    png.unlink()
    print(cible.name, f"{cible.stat().st_size // 1024} ko", image.size)
