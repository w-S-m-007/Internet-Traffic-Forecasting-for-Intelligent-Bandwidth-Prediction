"""Build a static viewing PDF from reviewed PPTX slide renders.

Uses the optional bundled artifact Python runtime (ReportLab and Pillow).
The editable source remains project_presentation.pptx.
"""
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "docs/presentation/.build"
slides = sorted((BUILD / "final").glob("slide-*.png"))
if len(slides) != 15:
    raise ValueError(f"Expected 15 final slides, found {len(slides)}")
target = ROOT / "deliverables/presentation/project_presentation.pdf"
c = canvas.Canvas(str(target), pagesize=(960, 540))
c.setTitle("Internet traffic forecasting and intelligent bandwidth prediction")
c.setSubject("Static companion to the editable project presentation")
for slide in slides:
    c.drawImage(str(slide), 0, 0, width=960, height=540)
    c.showPage()
c.save()
assert len(PdfReader(target).pages) == 15

# This contact sheet is review-only. It combines unchanged slide renders.
sheet = Image.new("RGB", (1280, 8 * 360), "white")
for index, slide in enumerate(slides):
    image = Image.open(slide).convert("RGB")
    thumb = ImageOps.contain(image, (640, 360))
    sheet.paste(thumb, ((index % 2) * 640, (index // 2) * 360))
sheet.save(BUILD / "contact_sheet.jpg", quality=92)
print(target)
