from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
class PdfExporter:
    @staticmethod
    def export_simple_table(title, columns, rows, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c=canvas.Canvas(str(output_path), pagesize=A4)
        _,h=A4
        y=h-40
        c.setFont("Helvetica-Bold",14); c.drawString(40,y,title); y-=30
        c.setFont("Helvetica-Bold",10); c.drawString(40,y," | ".join(columns)); y-=20
        c.setFont("Helvetica",10)
        for r in rows:
            c.drawString(40,y," | ".join(r)); y-=16
            if y<40: c.showPage(); y=h-40
        c.save()
