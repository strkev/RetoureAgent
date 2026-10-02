"""
pdf_generator.py
Erzeugt einen sauberen, standardkonformen PDF-1.4-Retourenbegleitschein ohne externe Abhängigkeiten.
Enthält Return-ID, Order-ID, Kundendaten, Tabelle der zurückgesendeten Artikel,
Erstattungsart und Gesamtsumme.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def _escape_pdf(text: str) -> str:
    """Escaped Sonderzeichen für PDF Literal Strings (ASCII/Latin-1 kompatibel)."""
    # Umlaute in saubere Entsprechungen wandeln für Standard Helvetica Font
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss", "€": "EUR"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_return_pdf(booking_data: Dict[str, Any], order_data: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Erzeugt einen druckfähigen Retourenbegleitschein (A4) als Binärdaten (PDF-1.4).
    """
    return_id = booking_data.get("return_id", "RET-SAMPLE")
    order_id = booking_data.get("order_id", "ORD-XXXX")
    return_type = booking_data.get("return_type", "refund")
    created_at = booking_data.get("created_at", datetime.now().strftime("%d.%m.%Y"))
    if "T" in created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            created_at = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    items = booking_data.get("items") or (order_data.get("items") if order_data else None) or []
    customer_email = (order_data.get("customer_email") if order_data else None) or "kunde@example.com"
    customer_addr = (order_data.get("adresse") if order_data else None) or "Musterstrasse 42, 10115 Berlin"
    customer_country = (order_data.get("land") if order_data else None) or "Deutschland"

    is_refund = (return_type == "refund")
    modality_text = "100% Kaufpreiserstattung (Zahlungsmittel)" if is_refund else "Store-Credit Warengutschein (Kulanz)"

    # Summe der retournierten Artikel berechnen
    total_val = 0.0
    for it in items:
        if isinstance(it, dict):
            total_val += float(it.get("price") or it.get("preis") or 0.0)
        else:
            total_val += 99.0

    if total_val == 0.0 and order_data:
        total_val = float(order_data.get("total_amount", 99.0))

    # Erzeuge PDF Content Stream (PostScript-like Commands)
    stream_lines = []

    # Hintergrund & Rahmen
    stream_lines.append("0.2 0.3 0.4 rg")  # Primärfarbe
    stream_lines.append("40 760 515 45 re f")  # Kopfzeilen-Kasten
    stream_lines.append("0.95 0.95 0.95 rg")
    stream_lines.append("40 680 515 65 re f")  # Meta-Info Kasten

    # Kopfzeile Text (Weiß)
    stream_lines.append("1 1 1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 18 Tf")
    stream_lines.append("55 780 Td")
    stream_lines.append("(MUSTER-SHOP RETOURENSCHEIN & BEGLEITBELEG) Tj")
    stream_lines.append("/F2 10 Tf")
    stream_lines.append("0 -15 Td")
    stream_lines.append("(Offizieller Retourennachweis fuer Ruecksendungen) Tj")
    stream_lines.append("ET")

    # Meta-Informationen (Dunkelgrau)
    stream_lines.append("0.1 0.1 0.1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 10 Tf")
    stream_lines.append("55 725 Td")
    stream_lines.append(f"(Retouren-ID: {_escape_pdf(return_id)}) Tj")
    stream_lines.append("180 0 Td")
    stream_lines.append(f"(Bestellnummer: {_escape_pdf(order_id)}) Tj")
    stream_lines.append("180 0 Td")
    stream_lines.append(f"(Datum: {_escape_pdf(str(created_at))}) Tj")

    stream_lines.append("-360 -22 Td")
    stream_lines.append(f"(Kunde: {_escape_pdf(customer_email)}) Tj")
    stream_lines.append("180 0 Td")
    stream_lines.append(f"(Erstattungsart: {_escape_pdf(modality_text)}) Tj")
    stream_lines.append("ET")

    # Barcode-Simulation (Striche)
    stream_lines.append("0 0 0 rg")
    barcode_x = 55
    barcode_y = 635
    stream_lines.append("BT /F2 8 Tf 55 655 Td (SCAN-CODE / RETOUREN-CODE:) Tj ET")
    # Einige simulierte Barcode-Linien
    pattern = [2, 1, 3, 1, 2, 4, 1, 3, 2, 1, 1, 3, 2, 4, 1, 2, 3, 1, 2, 1, 3, 1, 2, 4, 1, 3, 2, 1]
    curr_x = barcode_x
    for width in pattern:
        stream_lines.append(f"{curr_x} {barcode_y} {width} 15 re f")
        curr_x += width + 2
    stream_lines.append(f"BT /F2 9 Tf 220 {barcode_y + 3} Td ({_escape_pdf(return_id)} - DHL STANDARD RETOURE) Tj ET")

    # Adress-Boxen (Absender & Empfänger)
    stream_lines.append("0.8 0.8 0.8 RG 1 w")
    stream_lines.append("40 540 245 75 re s")  # Absender
    stream_lines.append("310 540 245 75 re s")  # Empfänger

    stream_lines.append("0.1 0.1 0.1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 10 Tf")
    stream_lines.append("50 598 Td (ABSENDER:) Tj")
    stream_lines.append("/F2 9 Tf")
    stream_lines.append("0 -15 Td")
    stream_lines.append(f"({_escape_pdf(customer_email)}) Tj")
    stream_lines.append("0 -14 Td")
    stream_lines.append(f"({_escape_pdf(customer_addr)}) Tj")
    stream_lines.append("0 -14 Td")
    stream_lines.append(f"({_escape_pdf(customer_country)}) Tj")

    stream_lines.append("270 43 Td")
    stream_lines.append("/F1 10 Tf")
    stream_lines.append("(EMPFAENGER / RETOURENZENTRUM:) Tj")
    stream_lines.append("/F2 9 Tf")
    stream_lines.append("0 -15 Td")
    stream_lines.append("(MusterShop GmbH & Co. KG) Tj")
    stream_lines.append("0 -14 Td")
    stream_lines.append("(Retouren-Logistik Halle 4) Tj")
    stream_lines.append("0 -14 Td")
    stream_lines.append("(Musterstrasse 42, 10115 Berlin, Deutschland) Tj")
    stream_lines.append("ET")

    # Tabelle der retournierten Produkte
    table_y = 500
    stream_lines.append("0.2 0.3 0.4 rg")
    stream_lines.append(f"40 {table_y} 515 22 re f")  # Header Kasten
    stream_lines.append("1 1 1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 9 Tf")
    stream_lines.append(f"50 {table_y + 6} Td")
    stream_lines.append("(POS) Tj")
    stream_lines.append("40 0 Td")
    stream_lines.append("(ARTIKEL-NR) Tj")
    stream_lines.append("90 0 Td")
    stream_lines.append("(BEZEICHNUNG DER WARE) Tj")
    stream_lines.append("230 0 Td")
    stream_lines.append("(PREIS) Tj")
    stream_lines.append("60 0 Td")
    stream_lines.append("(STATUS) Tj")
    stream_lines.append("ET")

    row_y = table_y - 20
    idx = 1
    for it in items:
        art_nr = it.get("item_id") or it.get("artikelnummer") or f"ART-{idx}" if isinstance(it, dict) else f"ART-{idx}"
        name = it.get("name") or it.get("bezeichnung") or str(it) if isinstance(it, dict) else str(it)
        price = f"{float(it.get('price') or it.get('preis') or 0.0):.2f} EUR" if isinstance(it, dict) and (it.get("price") or it.get("preis")) else "Inklusive"

        stream_lines.append("0.95 0.95 0.95 rg")
        if idx % 2 == 0:
            stream_lines.append(f"40 {row_y - 4} 515 18 re f")

        stream_lines.append("0.1 0.1 0.1 rg")
        stream_lines.append("BT")
        stream_lines.append("/F2 9 Tf")
        stream_lines.append(f"50 {row_y} Td")
        stream_lines.append(f"({idx}) Tj")
        stream_lines.append(f"40 0 Td ({_escape_pdf(art_nr)}) Tj")
        stream_lines.append(f"90 0 Td ({_escape_pdf(name[:35])}) Tj")
        stream_lines.append(f"230 0 Td ({_escape_pdf(price)}) Tj")
        stream_lines.append("60 0 Td (Retoure) Tj")
        stream_lines.append("ET")

        row_y -= 20
        idx += 1

    # Summenzeile & Kasten
    row_y -= 10
    stream_lines.append("0.7 0.7 0.7 RG 1 w")
    stream_lines.append(f"40 {row_y + 15} 515 0.5 re s")

    stream_lines.append("0.1 0.1 0.1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 11 Tf")
    stream_lines.append(f"320 {row_y} Td")
    stream_lines.append(f"(Gesamterstattung: {total_val:.2f} EUR) Tj")
    stream_lines.append("ET")

    # Hinweisbox unten
    stream_lines.append("0.9 0.94 0.98 rg")
    stream_lines.append("40 100 515 70 re f")
    stream_lines.append("0.2 0.3 0.4 RG 1 w")
    stream_lines.append("40 100 515 70 re s")

    stream_lines.append("0.1 0.1 0.1 rg")
    stream_lines.append("BT")
    stream_lines.append("/F1 10 Tf")
    stream_lines.append("55 150 Td")
    stream_lines.append("(HINWEISE ZUR RUECKSENDUNG:) Tj")
    stream_lines.append("/F2 8.5 Tf")
    stream_lines.append("0 -14 Td")
    stream_lines.append("(1. Bitte legen Sie diesen Retourenbeleg gut lesbar oben in das Paket.) Tj")
    stream_lines.append("0 -12 Td")
    stream_lines.append("(2. Kleben Sie das Adresslabel gut sichtbar auf die groesste Flaeche des Pakets.) Tj")
    stream_lines.append("0 -12 Td")
    stream_lines.append("(3. Nach Eingang pruefen wir die Ware innerhalb von 2-4 Werktagen und veranlassen die Erstattung.) Tj")
    stream_lines.append("ET")

    # Footer
    stream_lines.append("0.5 0.5 0.5 rg")
    stream_lines.append("BT")
    stream_lines.append("/F2 8 Tf")
    stream_lines.append("40 60 Td")
    stream_lines.append("(MusterShop GmbH & Co. KG - Geschaeftsfuehrung: Max Mustermann - Amtsgericht Berlin HRB 123456) Tj")
    stream_lines.append("0 -10 Td")
    stream_lines.append("(Dies ist ein automatisch generierter Musterbeleg fuer Entwicklungs- und Testzwecke.) Tj")
    stream_lines.append("ET")

    content_stream = "\n".join(stream_lines).encode("latin-1")
    stream_len = len(content_stream)

    # PDF-Objekte zusammensetzen
    objects = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page (A4 = 595 x 842 pt)
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>")
    # 4: Contents Stream
    objects.append(b"<< /Length " + str(stream_len).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream")
    # 5: Font F1 (Helvetica Bold)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    # 6: Font F2 (Helvetica Regular)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Schreibe XREF und Trailer
    pdf_out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for i, obj_content in enumerate(objects, 1):
        offsets.append(len(pdf_out))
        pdf_out.extend(f"{i} 0 obj\n".encode("ascii"))
        pdf_out.extend(obj_content)
        pdf_out.extend(b"\nendobj\n")

    xref_offset = len(pdf_out)
    pdf_out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf_out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    pdf_out.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))

    return bytes(pdf_out)
