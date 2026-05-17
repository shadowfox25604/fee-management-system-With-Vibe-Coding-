from pathlib import Path
import pandas as pd
class ExcelExporter:
    @staticmethod
    def export_rows(rows, output_path: Path):
        df = pd.DataFrame(rows)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output_path, engine="xlsxwriter") as w: df.to_excel(w, index=False, sheet_name="Report")
