from pathlib import Path
from fpdf import FPDF


def build_pdf(output_path: str, title: str, phase_data: dict, summary_text: str, decision_text: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, f'LRI Report - {title}', ln=True)

    pdf.set_font('Helvetica', '', 11)
    for phase, content in phase_data.items():
        pdf.ln(3)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.multi_cell(0, 7, phase)
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 6, content)

    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 7, 'AI Summary', ln=True)
    pdf.set_font('Helvetica', '', 11)
    pdf.multi_cell(0, 6, summary_text)

    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 7, 'Decision', ln=True)
    pdf.set_font('Helvetica', '', 11)
    pdf.multi_cell(0, 6, decision_text)

    pdf.output(str(path))
    return str(path)
