"""High contrast registration QR and A4 reception poster (never a payment QR)."""
from io import BytesIO
from xml.sax.saxutils import escape
import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle


def registration_qr(url):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    output = BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(output, format='PNG')
    return output.getvalue()


def reception_poster(name, url):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(595.28, 841.89))
    canvas.setTitle('Gym registration - ' + name)
    canvas.setFillColor(HexColor('#11171b'))
    canvas.rect(0, 0, 595.28, 841.89, fill=1, stroke=0)
    canvas.setFillColor(HexColor('#c9ff35'))
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawString(48, 784, 'WELCOME TO YOUR NEXT STEP')
    title = Paragraph(escape(name), ParagraphStyle('gym', fontName='Helvetica-Bold', fontSize=28,
                      leading=34, textColor=HexColor('#ffffff')))
    _, height = title.wrap(499, 130)
    title.drawOn(canvas, 48, 745 - height)
    canvas.setFillColor(HexColor('#ffffff'))
    canvas.setFont('Helvetica-Bold', 24)
    canvas.drawString(48, 540, 'Scan to join our gym')
    canvas.setFont('Helvetica', 12)
    canvas.drawString(48, 516, 'Explore plans. Create an account. Register in your browser.')
    canvas.drawImage(ImageReader(BytesIO(registration_qr(url))), 157, 210, width=280, height=280)
    canvas.setFillColor(HexColor('#c9ff35'))
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawCentredString(297.64, 184, 'REGISTRATION QR - NOT FOR PAYMENT')
    link = Paragraph(escape(url), ParagraphStyle('link', fontName='Helvetica', fontSize=10,
                     leading=14, textColor=HexColor('#ffffff'), alignment=1, splitLongWords=True))
    _, link_height = link.wrap(499, 70)
    link.drawOn(canvas, 48, 153 - link_height)
    canvas.linkURL(url, (48, 153 - link_height, 547, 153), relative=0)
    canvas.setFont('Helvetica', 10)
    canvas.drawCentredString(297.64, 60, 'No app download required. Ask reception if you need help.')
    canvas.save()
    return output.getvalue()
