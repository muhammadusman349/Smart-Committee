from django.apps import apps
from celery import shared_task
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from conf.celery import app
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
)


@shared_task
def send_invitation_email(committee_id, inviter_name, inviter_email, recipient_email, token, site_domain):
    """
    Celery task to send invitation email asynchronously
    """
    try:
        # Get committee details
        Committee = apps.get_model('committee', 'Committee')
        committee = Committee.objects.get(id=committee_id)

        # Build accept URL
        accept_path = reverse('committee:invitation_accept', kwargs={'token': token})
        accept_url = f"http://{site_domain}{accept_path}"

        # Email content
        subject = f"Invitation to join committee: {committee.name}"
        message = (
            f"Hello,\n\n"
            f"You have been invited by {inviter_name or inviter_email} to join the committee \"{committee.name}\".\n"
            f"Description: {committee.description}\n\n"
            f"Monthly Amount: ${committee.monthly_amount}\n"
            f"Duration: {committee.duration_months} months\n"
            f"Start Date: {committee.start_date}\n\n"
            f"To accept this invitation, click the link below:\n{accept_url}\n\n"
            f"This invitation will expire in 7 days.\n\n"
            f"If you did not expect this invitation, you can safely ignore this email."
        )

        # Send email with detailed error handling
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )
            return f"Invitation email sent successfully to {recipient_email}"
        except Exception as email_error:
            error_msg = f"SMTP Error sending to {recipient_email}: {str(email_error)}"
            print(f"EMAIL ERROR: {error_msg}")  # This will show in Celery worker logs
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Failed to send invitation email: {str(e)}"
        print(f"TASK ERROR: {error_msg}")  # This will show in Celery worker logs
        raise Exception(error_msg)


@app.task
def generate_contribution_excel_file(contribution_id):
    from .models import Contribution
    from datetime import datetime

    try:
        contribution = Contribution.objects.get(id=contribution_id)
    except Contribution.DoesNotExist:
        print(f"Contribution with ID {contribution_id} does not exist.")
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Contribution Report"

    # Enhanced color scheme and styles
    title_font = Font(size=20, bold=True, color="FFFFFF")
    subtitle_font = Font(size=12, italic=True, color="666666")
    header_font = Font(size=12, bold=True, color="FFFFFF")
    data_font = Font(size=11, color="333333")
    amount_font = Font(size=11, bold=True, color="2E7D32")  # Green for amounts
    status_font = Font(size=11, bold=True, color="1976D2")  # Blue for status
    
    # Color fills
    title_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")  # Green
    header_fill = PatternFill(start_color="424242", end_color="424242", fill_type="solid")  # Dark gray
    data_fill_1 = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")  # Light gray
    data_fill_2 = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")  # White
    
    # Borders
    thick_border = Border(
        left=Side(style='thick', color="2E7D32"),
        right=Side(style='thick', color="2E7D32"),
        top=Side(style='thick', color="2E7D32"),
        bottom=Side(style='thick', color="2E7D32"),
    )
    thin_border = Border(
        left=Side(style='thin', color="CCCCCC"),
        right=Side(style='thin', color="CCCCCC"),
        top=Side(style='thin', color="CCCCCC"),
        bottom=Side(style='thin', color="CCCCCC"),
    )

    # Company header section
    sheet.merge_cells('A1:I2')
    title_cell = sheet.cell(row=1, column=1)
    title_cell.value = "CONTRIBUTION RECEIPT REPORT"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.border = thick_border

    # Report metadata
    sheet.merge_cells('A3:I3')
    subtitle_cell = sheet.cell(row=3, column=1)
    subtitle_cell.value = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | Committee: {contribution.membership.committee.name}"
    subtitle_cell.font = subtitle_font
    subtitle_cell.alignment = Alignment(horizontal="center")

    # Headers with enhanced styling
    contribution_headers = [
        "Contrib ID",
        "Member ID", 
        "Member Name",
        "For Month",
        "Due Date",
        "Paid Date",
        "Status",
        "Verified",
    ]

    # Create header row
    for col_num, header in enumerate(contribution_headers, start=1):
        cell = sheet.cell(row=5, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Data row with enhanced formatting
    row_index = 6
    data = [
        f"#{contribution.id}",
        f"M{contribution.membership.member.id}",
        contribution.membership.member.full_name if contribution.membership.member.full_name and contribution.membership.member.full_name.strip() else contribution.membership.member.email,
        contribution.for_month.strftime("%B %Y"),
        contribution.due_date.strftime("%b %d, %Y") if contribution.due_date else 'Not Set',
        contribution.payment_date.strftime("%b %d, %Y") if contribution.payment_date else 'Not Paid',
        contribution.payment_status,
        "Yes" if contribution.verified_by_organizer else "No",
    ]

    for col_num, value in enumerate(data, start=1):
        cell = sheet.cell(row=row_index, column=col_num)
        cell.value = value
        
        # Special formatting for different columns
        if col_num == 7:  # Status column
            cell.font = status_font
        else:
            cell.font = data_font
            
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.fill = data_fill_1
        cell.border = thin_border

    # Summary section
    summary_row = row_index + 2
    sheet.merge_cells(f'A{summary_row}:C{summary_row}')
    summary_cell = sheet.cell(row=summary_row, column=1)
    summary_cell.value = "CONTRIBUTION SUMMARY"
    summary_cell.font = Font(size=14, bold=True, color="2E7D32")
    summary_cell.alignment = Alignment(horizontal="left", vertical="center")

    # Summary details
    summary_details = [
        ("Committee:", contribution.membership.committee.name),
        ("Member:", contribution.membership.member.full_name if contribution.membership.member.full_name and contribution.membership.member.full_name.strip() else contribution.membership.member.email),
        ("Period:", contribution.for_month.strftime("%B %Y")),
        ("Amount Due:", f"${contribution.membership.committee.monthly_amount:,.2f}"),
        ("Amount Paid:", f"${contribution.amount_paid:,.2f}" if contribution.amount_paid else "Not Paid"),
        ("Status:", contribution.payment_status),
        ("Verified:", "Yes" if contribution.verified_by_organizer else "No"),
    ]

    for i, (label, value) in enumerate(summary_details, start=summary_row + 1):
        label_cell = sheet.cell(row=i, column=1)
        label_cell.value = label
        label_cell.font = Font(size=11, bold=True, color="666666")
        
        value_cell = sheet.cell(row=i, column=2)
        value_cell.value = value
        if "Amount" in label:
            value_cell.font = amount_font
        else:
            value_cell.font = Font(size=11, color="333333")

    # Enhanced column widths
    column_widths = [12, 12, 25, 15, 15, 15, 15, 12]
    for i, width in enumerate(column_widths, start=1):
        sheet.column_dimensions[chr(64 + i)].width = width

    # Row heights for better spacing
    sheet.row_dimensions[1].height = 40
    sheet.row_dimensions[3].height = 25
    sheet.row_dimensions[5].height = 30
    sheet.row_dimensions[6].height = 25

    # Save the Excel file
    buff = BytesIO()
    workbook.save(buff)
    buff.seek(0)
    file = InMemoryUploadedFile(buff, "xlsx", f"Contribution_Report{contribution.id}.xlsx", None, buff.tell(), None)
    contribution.excel_file.save(f"Contribution_Report_{contribution.id}.xlsx", file)
    contribution.save()


@app.task
def generate_contribution_pdf_file(contribution_id):
    from .models import Contribution
    from datetime import datetime

    try:
        contribution = Contribution.objects.get(id=contribution_id)
    except Contribution.DoesNotExist:
        print(f"Contribution with ID {contribution_id} does not exist.")
        return

    buff = BytesIO()
    doc = SimpleDocTemplate(
        buff, 
        pagesize=landscape(letter),
        topMargin=50,
        bottomMargin=50,
        leftMargin=40,
        rightMargin=40
    )
    elements = []

    # Professional stylesheet
    stylesheet = getSampleStyleSheet()
    
    # Corporate title style
    title_style = stylesheet["Title"].clone('CorporateTitle')
    title_style.fontSize = 22
    title_style.textColor = colors.HexColor('#1a365d')
    title_style.alignment = 1
    title_style.spaceAfter = 15
    title_style.fontName = 'Helvetica-Bold'
    
    # Subtitle style
    subtitle_style = stylesheet["Normal"].clone('CorporateSubtitle')
    subtitle_style.fontSize = 11
    subtitle_style.textColor = colors.HexColor('#4a5568')
    subtitle_style.alignment = 1
    subtitle_style.spaceAfter = 25
    
    # Section header style
    section_style = stylesheet["Heading2"].clone('CorporateSection')
    section_style.fontSize = 14
    section_style.textColor = colors.HexColor('#2d3748')
    section_style.spaceBefore = 20
    section_style.spaceAfter = 12
    section_style.fontName = 'Helvetica-Bold'

    # Document header
    header_text = "CONTRIBUTION RECEIPT"
    elements.append(Paragraph(header_text, title_style))
    
    # Document info
    doc_info = f"Report #{contribution.id:04d} | Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>Committee Management System"
    elements.append(Paragraph(doc_info, subtitle_style))

    # Transaction details section
    elements.append(Paragraph("TRANSACTION DETAILS", section_style))
    
    # Professional contribution data table with shorter headers
    contribution_data = [
        # Clean header row with shorter names
        [
            "Contrib ID",
            "Member ID", 
            "Member Name",
            "For Month",
            "Due Date",
            "Paid Date",
            "Status",
            "Verified"
        ],
        # Data row with clean formatting
        [
            f"#{contribution.id}",
            f"M{contribution.membership.member.id}",
            contribution.membership.member.full_name if contribution.membership.member.full_name and contribution.membership.member.full_name.strip() else contribution.membership.member.email,
            contribution.for_month.strftime("%B %Y"),
            contribution.due_date.strftime("%b %d, %Y") if contribution.due_date else 'Not Set',
            contribution.payment_date.strftime("%b %d, %Y") if contribution.payment_date else 'Not Paid',
            contribution.payment_status,
            "Yes" if contribution.verified_by_organizer else "No",
        ]
    ]

    # Create table with optimized column widths for shorter headers
    col_widths = [1.1*inch, 1*inch, 2.4*inch, 1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1*inch]
    contribution_table = Table(contribution_data, colWidths=col_widths)

    # Professional table styling for contribution PDF
    professional_table_style = TableStyle([
        # Header styling - clean corporate look
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # Data row styling - clean and readable
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#4a5568')),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Status column emphasis
        ('TEXTCOLOR', (6, 1), (6, -1), colors.HexColor('#38a169') if contribution.payment_status == 'PAID' else colors.HexColor('#e53e3e')),
        ('FONTNAME', (6, 1), (6, -1), 'Helvetica-Bold'),
        
        # Professional borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#cbd5e0')),
        
        # Consistent padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])
    
    contribution_table.setStyle(professional_table_style)
    elements.append(contribution_table)
    elements.append(Spacer(1, 25))

    # Summary section
    elements.append(Paragraph("CONTRIBUTION SUMMARY", section_style))
    
    # Clean summary table
    summary_data = [
        ["Committee:", contribution.membership.committee.name],
        ["Member:", contribution.membership.member.full_name if contribution.membership.member.full_name and contribution.membership.member.full_name.strip() else contribution.membership.member.email],
        ["Contribution Period:", contribution.for_month.strftime("%B %Y")],
        ["Amount Due:", f"${contribution.membership.committee.monthly_amount:,.2f}"],
        ["Amount Paid:", f"${contribution.amount_paid:,.2f}" if contribution.amount_paid else "Not Paid"],
        ["Payment Status:", contribution.payment_status],
        ["Due Date:", contribution.due_date.strftime("%B %d, %Y") if contribution.due_date else "Not Set"],
        ["Payment Date:", contribution.payment_date.strftime("%B %d, %Y") if contribution.payment_date else "Not Paid"],
        ["Verified by Organizer:", "Yes" if contribution.verified_by_organizer else "No"],
    ]
    
    summary_table = Table(summary_data, colWidths=[1.8*inch, 3.7*inch])
    summary_style = TableStyle([
        # Label column - professional gray
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2d3748')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, -1), 12),
        ('RIGHTPADDING', (0, 0), (0, -1), 15),
        ('LEFTPADDING', (1, 0), (1, -1), 15),
        ('RIGHTPADDING', (1, 0), (1, -1), 12),
        
        # Value column
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#4a5568')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        
        # Amount rows emphasis
        ('TEXTCOLOR', (1, 3), (1, 4), colors.HexColor('#38a169')),
        ('FONTNAME', (1, 3), (1, 4), 'Helvetica-Bold'),
        
        # Clean borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    summary_table.setStyle(summary_style)
    elements.append(summary_table)
    
    # Professional footer
    elements.append(Spacer(1, 40))
    footer_style = stylesheet["Normal"].clone('ProfessionalFooter')
    footer_style.fontSize = 9
    footer_style.textColor = colors.HexColor('#718096')
    footer_style.alignment = 1
    
    footer_text = f"""
    <br/>
    ──────────────────────────────────────────────────────────────────<br/>
    Official Contribution Receipt | Committee Management System<br/>
    Document generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
    For inquiries, please contact the committee administrator
    """
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)
    buff.seek(0)

    # Save the professional PDF file
    file = InMemoryUploadedFile(buff, "pdf", f"Contribution_Report_{contribution.id}.pdf", None, buff.tell(), None)
    contribution.pdf_file.save(f"Contribution_Report_{contribution.id}.pdf", file)
    contribution.save()


@app.task
def generate_payout_excel_file(payout_id):
    from .models import Payout
    from datetime import datetime

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        print(f"Payout with ID {payout_id} does not exist.")
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Payout Report"

    # Enhanced color scheme and styles
    title_font = Font(size=20, bold=True, color="FFFFFF")
    subtitle_font = Font(size=12, italic=True, color="666666")
    header_font = Font(size=12, bold=True, color="FFFFFF")
    data_font = Font(size=11, color="333333")
    amount_font = Font(size=11, bold=True, color="2E7D32")  # Green for amounts
    
    # Color fills
    title_fill = PatternFill(start_color="1976D2", end_color="1976D2", fill_type="solid")  # Blue
    header_fill = PatternFill(start_color="424242", end_color="424242", fill_type="solid")  # Dark gray
    data_fill_1 = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")  # Light gray
    data_fill_2 = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")  # White
    
    # Borders
    thick_border = Border(
        left=Side(style='thick', color="1976D2"),
        right=Side(style='thick', color="1976D2"),
        top=Side(style='thick', color="1976D2"),
        bottom=Side(style='thick', color="1976D2"),
    )
    thin_border = Border(
        left=Side(style='thin', color="CCCCCC"),
        right=Side(style='thin', color="CCCCCC"),
        top=Side(style='thin', color="CCCCCC"),
        bottom=Side(style='thin', color="CCCCCC"),
    )

    # Company header section
    sheet.merge_cells('A1:J2')
    title_cell = sheet.cell(row=1, column=1)
    title_cell.value = "PAYOUT RECEIPT REPORT"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.border = thick_border

    # Report metadata
    sheet.merge_cells('A3:J3')
    subtitle_cell = sheet.cell(row=3, column=1)
    subtitle_cell.value = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | Committee: {payout.membership.committee.name}"
    subtitle_cell.font = subtitle_font
    subtitle_cell.alignment = Alignment(horizontal="center")

    # Headers with enhanced styling
    payout_headers = [
        "Payout ID",
        "Member ID", 
        "Member Name",
        "Total Amount",
        "Paid Date",
        "Received By",
        "Status",
        "Payment Method",
        "Confirmed Date",
    ]

    # Create header row
    for col_num, header in enumerate(payout_headers, start=1):
        cell = sheet.cell(row=5, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    not_specified = "Not Specified"
    # Data row with enhanced formatting
    row_index = 6
    data = [
        f"#{payout.id}",
        f"M{payout.membership.member.id}",
        payout.membership.member.full_name if payout.membership.member.full_name and payout.membership.member.full_name.strip() else payout.membership.member.email,
        f"${payout.total_amount:,.2f}",
        payout.paid_at.strftime("%B %d, %Y"),
        payout.received_by.full_name if payout.received_by else not_specified,
        "Confirmed" if payout.is_confirmed else "Pending",
        "Cash" if payout.received_in_cash else "Transfer",
        payout.confirmed_at.strftime("%B %d, %Y") if payout.confirmed_at else 'Not Confirmed',
    ]

    for col_num, value in enumerate(data, start=1):
        cell = sheet.cell(row=row_index, column=col_num)
        cell.value = value
        
        # Special formatting for different columns
        if col_num == 4:  # Amount column
            cell.font = amount_font
        else:
            cell.font = data_font
            
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.fill = data_fill_1
        cell.border = thin_border

    # Summary section
    summary_row = row_index + 2
    sheet.merge_cells(f'A{summary_row}:C{summary_row}')
    summary_cell = sheet.cell(row=summary_row, column=1)
    summary_cell.value = "PAYOUT SUMMARY"
    summary_cell.font = Font(size=14, bold=True, color="1976D2")
    summary_cell.alignment = Alignment(horizontal="left", vertical="center")

    # Summary details
    summary_details = [
        ("Committee:", payout.membership.committee.name),
        ("Member:", payout.membership.member.full_name if payout.membership.member.full_name and payout.membership.member.full_name.strip() else payout.membership.member.email),
        ("Amount:", f"${payout.total_amount:,.2f}"),
        ("Status:", "Confirmed" if payout.is_confirmed else "Pending"),
        ("Payment Method:", "Cash" if payout.received_in_cash else "Bank Transfer"),
    ]

    for i, (label, value) in enumerate(summary_details, start=summary_row + 1):
        label_cell = sheet.cell(row=i, column=1)
        label_cell.value = label
        label_cell.font = Font(size=11, bold=True, color="666666")
        
        value_cell = sheet.cell(row=i, column=2)
        value_cell.value = value
        value_cell.font = Font(size=11, color="333333")

    # Enhanced column widths
    column_widths = [15, 12, 25, 15, 18, 20, 15, 15, 18]
    for i, width in enumerate(column_widths, start=1):
        sheet.column_dimensions[chr(64 + i)].width = width

    # Row heights for better spacing
    sheet.row_dimensions[1].height = 40
    sheet.row_dimensions[3].height = 25
    sheet.row_dimensions[5].height = 30
    sheet.row_dimensions[6].height = 25

    # Save the Excel file
    buff = BytesIO()
    workbook.save(buff)
    buff.seek(0)
    file = InMemoryUploadedFile(buff, "xlsx", f"Payout_Report_{payout.id}.xlsx", None, buff.tell(), None)
    payout.excel_file.save(f"Payout_Report_{payout.id}.xlsx", file)
    payout.save()


@app.task
def generate_payout_pdf_file(payout_id):
    from .models import Payout
    from datetime import datetime

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        print(f"Payout with ID {payout_id} does not exist.")
        return

    buff = BytesIO()
    doc = SimpleDocTemplate(
        buff, 
        pagesize=landscape(letter),
        topMargin=50,
        bottomMargin=50,
        leftMargin=40,
        rightMargin=40
    )
    elements = []

    # Professional stylesheet
    stylesheet = getSampleStyleSheet()
    
    # Corporate title style
    title_style = stylesheet["Title"].clone('CorporateTitle')
    title_style.fontSize = 22
    title_style.textColor = colors.HexColor('#1a365d')
    title_style.alignment = 1
    title_style.spaceAfter = 15
    title_style.fontName = 'Helvetica-Bold'
    
    # Subtitle style
    subtitle_style = stylesheet["Normal"].clone('CorporateSubtitle')
    subtitle_style.fontSize = 11
    subtitle_style.textColor = colors.HexColor('#4a5568')
    subtitle_style.alignment = 1
    subtitle_style.spaceAfter = 25
    
    # Section header style
    section_style = stylesheet["Heading2"].clone('CorporateSection')
    section_style.fontSize = 14
    section_style.textColor = colors.HexColor('#2d3748')
    section_style.spaceBefore = 20
    section_style.spaceAfter = 12
    section_style.fontName = 'Helvetica-Bold'

    # Document header
    header_text = "PAYOUT RECEIPT"
    elements.append(Paragraph(header_text, title_style))
    
    # Document info
    doc_info = f"Report #{payout.id:04d} | Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>Committee Management System"
    elements.append(Paragraph(doc_info, subtitle_style))

    # Company/Committee info section
    elements.append(Paragraph("TRANSACTION DETAILS", section_style))
    not_specified = "Not Specified"
    # Professional payout data table
    payout_data = [
        # Clean header row
        [
            "Payout ID",
            "Member ID", 
            "Member Name",
            "Amount",
            "Date Paid",
            "Received By",
            "Status",
            "Method",
            "Confirmed"
        ],
        # Data row with clean formatting
        [
            f"#{payout.id}",
            f"M{payout.membership.member.id}",
            payout.membership.member.full_name if payout.membership.member.full_name and payout.membership.member.full_name.strip() else payout.membership.member.email,
            f"${payout.total_amount:,.2f}",
            payout.paid_at.strftime("%b %d, %Y"),
            payout.received_by.full_name if payout.received_by else not_specified,
            "Confirmed" if payout.is_confirmed else "Pending",
            "Cash" if payout.received_in_cash else "Transfer",
            payout.confirmed_at.strftime("%b %d, %Y") if payout.confirmed_at else 'Pending',
        ]
    ]

    # Create table with appropriate column widths
    col_widths = [1.1*inch, 1*inch, 2.4*inch, 1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1*inch]
    payout_table = Table(payout_data, colWidths=col_widths)

    # Professional table styling
    professional_table_style = TableStyle([
        # Header styling - clean corporate look
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data row styling - clean and readable
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#4a5568')),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        
        # Amount column emphasis
        ('TEXTCOLOR', (3, 1), (3, -1), colors.HexColor('#38a169')),
        ('FONTNAME', (3, 1), (3, -1), 'Helvetica-Bold'),
        
        # Professional borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#cbd5e0')),
        
        # Consistent padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])
    
    payout_table.setStyle(professional_table_style)
    elements.append(payout_table)
    elements.append(Spacer(1, 25))

    # Summary section
    elements.append(Paragraph("PAYMENT SUMMARY", section_style))
    
    # Clean summary table
    summary_data = [
        ["Committee:", payout.membership.committee.name],
        ["Member:", payout.membership.member.full_name if payout.membership.member.full_name and payout.membership.member.full_name.strip() else payout.membership.member.email],
        ["Total Amount:", f"${payout.total_amount:,.2f}"],
        ["Payment Status:", "Confirmed" if payout.is_confirmed else "Pending"],
        ["Payment Method:", "Cash Payment" if payout.received_in_cash else "Bank Transfer"],
        ["Transaction Date:", payout.paid_at.strftime("%B %d, %Y")],
        ["Confirmation Date:", payout.confirmed_at.strftime("%B %d, %Y") if payout.confirmed_at else "Pending"],
    ]
    
    summary_table = Table(summary_data, colWidths=[1.5*inch, 4*inch])
    summary_style = TableStyle([
        # Label column - professional gray
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2d3748')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, -1), 12),
        ('RIGHTPADDING', (0, 0), (0, -1), 15),
        ('LEFTPADDING', (1, 0), (1, -1), 15),
        ('RIGHTPADDING', (1, 0), (1, -1), 12),
        
        # Value column
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#4a5568')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        
        # Amount row emphasis
        ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor('#38a169')),
        ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),
        
        # Clean borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    summary_table.setStyle(summary_style)
    elements.append(summary_table)
    
    # Professional footer
    elements.append(Spacer(1, 40))
    footer_style = stylesheet["Normal"].clone('ProfessionalFooter')
    footer_style.fontSize = 9
    footer_style.textColor = colors.HexColor('#718096')
    footer_style.alignment = 1
    
    footer_text = f"""
    <br/>
    ──────────────────────────────────────────────────────────────────<br/>
    Official Payout Receipt | Committee Management System<br/>
    Document generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
    For inquiries, please contact the committee administrator
    """
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)
    buff.seek(0)

    # Save the professional PDF file
    file = InMemoryUploadedFile(buff, "pdf", f"Professional_Payout_Report_{payout.id}.pdf", None, buff.tell(), None)
    payout.pdf_file.save(f"Professional_Payout_Report_{payout.id}.pdf", file)
    payout.save()
