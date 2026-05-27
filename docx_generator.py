import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """
    Sets inner padding (margins) of a table cell in dxa (1 pt = 20 dxa).
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for margin_name, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{margin_name}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_background(cell, fill_hex):
    """
    Sets the background color of a table cell.
    """
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def add_hyperlink(paragraph, text, url, color="4F46E5", underline=True):
    """
    Adds a functional hyperlink to a paragraph.
    """
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    if color:
        c = OxmlElement('w:color')
        c.set(qn('w:val'), color)
        rPr.append(c)
    if underline:
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        rPr.append(u)

    new_run.append(rPr)
    text_node = OxmlElement('w:t')
    text_node.text = text
    new_run.append(text_node)
    hyperlink.append(new_run)

    paragraph._p.append(hyperlink)
    return hyperlink

def create_docx(output_path, metadata, segments, target_lang=None):
    """
    Creates a styled Word Document (.docx) for the transcribed clip.
    """
    doc = docx.Document()
    
    # Configure document layout margins (1 inch / 2.54 cm all sides)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Style definitions
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(0x33, 0x41, 0x55) # Slate 700

    # Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(12)
    title_run = title_p.add_run(metadata['clip_name'])
    title_run.font.name = 'Calibri'
    title_run.font.size = Pt(20)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B) # Slate 800

    # Add subtitle
    subtitle_p = doc.add_paragraph()
    subtitle_p.paragraph_format.space_after = Pt(24)
    sub_run = subtitle_p.add_run("Transkriptionsbericht & Metadaten-Analyse")
    sub_run.font.size = Pt(12)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B) # Slate 500

    # Metadata Grid (built as a borderless styled table)
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    meta_table.autofit = False
    
    labels = [
        "Dateiname:",
        "Dauer:",
        "Erstellungsdatum:",
        "Ort (Metadaten):"
    ]
    
    # Values parsing
    loc_str = "Keine GPS-Metadaten vorhanden"
    maps_link = None
    if metadata.get('gps'):
        loc_str = metadata['gps'].get('address', metadata['gps']['formatted'])
        maps_link = metadata.get('maps_link')

    values = [
        metadata['clip_name'],
        metadata['duration_str'],
        metadata['creation_date'],
        loc_str
    ]

    for idx, (label, val) in enumerate(zip(labels, values)):
        row = meta_table.rows[idx]
        
        # Label cell
        cell_lbl = row.cells[0]
        cell_lbl.width = Inches(1.8)
        p_lbl = cell_lbl.paragraphs[0]
        p_lbl.paragraph_format.space_after = Pt(4)
        run_lbl = p_lbl.add_run(label)
        run_lbl.bold = True
        run_lbl.font.color.rgb = RGBColor(0x47, 0x55, 0x69) # Slate 600
        
        # Value cell
        cell_val = row.cells[1]
        cell_val.width = Inches(4.7)
        p_val = cell_val.paragraphs[0]
        p_val.paragraph_format.space_after = Pt(4)
        
        if idx == 3 and maps_link:
            # Add address text first
            p_val.add_run(val + " ")
            # Add Hyperlink
            add_hyperlink(p_val, "(Auf Google Maps anzeigen)", maps_link)
        else:
            p_val.add_run(val)

    # Empty paragraph spacer
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(12)
    spacer.paragraph_format.space_after = Pt(12)
    
    # Heading Transcription
    heading_p = doc.add_paragraph()
    heading_p.paragraph_format.space_after = Pt(8)
    heading_run = heading_p.add_run("Transkript")
    heading_run.font.size = Pt(14)
    heading_run.font.bold = True
    heading_run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B) # Slate 800

    # Segments Table
    has_translation = any(seg.get('translated') for seg in segments)
    
    if has_translation:
        cols = 3
        headers = ["Zeitstempel", "Originaltext", f"Übersetzung ({target_lang.upper()})"]
        col_widths = [Inches(1.2), Inches(2.65), Inches(2.65)]
    else:
        cols = 2
        headers = ["Zeitstempel", "Inhalt / Transkription"]
        col_widths = [Inches(1.2), Inches(5.3)]

    table = doc.add_table(rows=1, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Header Row styling
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        set_cell_background(hdr_cells[i], "4F46E5") # Premium Indigo
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
        
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(title)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) # White

    # Data Rows
    for r_idx, seg in enumerate(segments):
        row = table.add_row()
        row_cells = row.cells
        
        # Alternating row background for readability
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        
        # Content mapping
        time_text = f"[{seg['start_str']} - {seg['end_str']}]"
        
        if has_translation:
            row_data = [time_text, seg['original'], seg['translated']]
        else:
            row_data = [time_text, seg['original']]
            
        for i, text in enumerate(row_data):
            row_cells[i].width = col_widths[i]
            set_cell_background(row_cells[i], bg_color)
            set_cell_margins(row_cells[i], top=100, bottom=100, left=150, right=150)
            
            p = row_cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            
            if i == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(text)
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B) # Slate 500
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                run = p.add_run(text)
                run.font.size = Pt(10.5)

    # Save document
    doc.save(output_path)
    print(f"Report erfolgreich gespeichert unter: {output_path}")

if __name__ == '__main__':
    # Quick test generator script
    test_meta = {
        'clip_name': 'test_video.mp4',
        'duration_str': '00:01:45',
        'creation_date': '27.05.2026 12:45:00',
        'gps': {
            'lat': 52.52,
            'lon': 13.405,
            'formatted': '+52.5200, +13.4050',
            'address': 'Berlin, Deutschland'
        },
        'maps_link': 'https://www.google.com/maps/search/?api=1&query=52.52,13.405'
    }
    test_segments = [
        {'start_str': '00:00:00', 'end_str': '00:00:05', 'original': 'Hallo Welt, das ist eine Testaufnahme.', 'translated': 'Hello world, this is a test recording.'},
        {'start_str': '00:00:05', 'end_str': '00:00:12', 'original': 'Wir analysieren GPS Metadaten und transkribieren Audio offline.', 'translated': 'We analyze GPS metadata and transcribe audio offline.'}
    ]
    create_docx('test_output.docx', test_meta, test_segments, 'en')
