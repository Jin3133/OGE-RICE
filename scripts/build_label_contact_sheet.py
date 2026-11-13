"""Build per-grid and all-image contact sheets for final visual QC."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data/raw/labeling/tolabel/images_rgb"
QC_DIR = ROOT / "data/raw/labeling/tolabel/qc_contact_sheets"
GRIDS = ("JX5K_R03C06", "JX5K_R07C05", "JX5K_R10C10")
DATES = ("20250418", "20250614", "20250707", "20250816", "20251005")


def tile(path: Path, caption: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    canvas = Image.new("RGB", (520, 555), "white")
    canvas.paste(image, (10, 10))
    ImageDraw.Draw(canvas).text((12, 520), caption, fill="black")
    return canvas


def main() -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for grid in GRIDS:
        items = [
            tile(IMAGE_DIR / f"{grid}_{date}_RGB.png", f"{grid}  {date}")
            for date in DATES
        ]
        sheet = Image.new("RGB", (520 * 5, 555), "#d9d9d9")
        for index, item in enumerate(items):
            sheet.paste(item, (index * 520, 0))
        sheet.save(QC_DIR / f"{grid}_five_dates.png")
        all_rows.append(sheet)

    overview = Image.new("RGB", (520 * 5, 555 * 3), "#d9d9d9")
    for index, row in enumerate(all_rows):
        overview.paste(row, (0, index * 555))
    overview.save(QC_DIR / "jiangxia_three_grids_five_dates.png")
    print(QC_DIR / "jiangxia_three_grids_five_dates.png")


if __name__ == "__main__":
    main()
