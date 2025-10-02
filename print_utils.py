import os
import tempfile
import webbrowser
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


def print_srf_form(srf, logo_path="assets/images/bsu_logo.png"):
    """
    Generate a printable SRF form as PDF with the same layout as the ticket form.
    Opens the PDF in the system viewer for direct printing.
    """
    # Temp PDF
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = tmpfile.name
    tmpfile.close()

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=30)

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleB = styles["Heading2"]

    elements = []

    # --- Header with logo + title ---
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=60, height=60))
    elements.append(Paragraph("<b>ICT SERVICE REQUEST FORM (SRF)</b>", styleB))
    elements.append(Spacer(1, 12))

    # --- Section 1: Request Info ---
    data1 = [
        ["Campus:", srf.get("campus", ""), "ICT SRF No.:", srf.get("ict_srf_no", "")],
        ["Office/Building:", srf.get("office_building", ""), "Technician Assigned:", srf.get("technician_assigned", "")],
        ["Client’s Name:", srf.get("client_name", ""), "Signature:", "_____________________"],
        ["Date/Time of Call:", str(srf.get("date_time_call", "")), "Required Response Time:", srf.get("required_response_time", "")]
    ]
    table1 = Table(data1, colWidths=[120, 150, 120, 150])
    table1.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.black),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONT", (0,0), (-1,-1), "Helvetica", 10),
    ]))
    elements.append(table1)
    elements.append(Spacer(1, 12))

    # --- Section 2: Service Requirements ---
    elements.append(Paragraph("<b>Services Requirements:</b>", styleN))
    elements.append(Paragraph(srf.get("services_requirements", ""), styleN))
    elements.append(Spacer(1, 12))

    # --- Section 3: Technician Accomplishment ---
    elements.append(Paragraph("<b>ACCOMPLISHMENT (to be accomplished by the assigned technician)</b>", styleN))
    data2 = [
        ["Response Time:", srf.get("response_time", ""), "Service Time:", srf.get("service_time", "")]
    ]
    table2 = Table(data2, colWidths=[120, 150, 120, 150])
    table2.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.black),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONT", (0,0), (-1,-1), "Helvetica", 10),
    ]))
    elements.append(table2)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Remarks:</b>", styleN))
    elements.append(Paragraph(srf.get("remarks", ""), styleN))
    elements.append(Spacer(1, 20))

    # --- Footer: Created info ---
    elements.append(Paragraph(f"Created by: {srf.get('created_by_username','Unknown')}", styleN))
    elements.append(Paragraph(f"Created at: {srf.get('created_at','')}", styleN))
    elements.append(Paragraph(f"Status: {srf.get('status','open')}", styleN))

    # Build PDF
    doc.build(elements)

    # Open in viewer (user can print directly)
    webbrowser.open(pdf_path)
