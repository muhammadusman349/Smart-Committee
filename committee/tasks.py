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

    try:
        contribution = Contribution.objects.get(id=contribution_id)
    except Contribution.DoesNotExist:
        print(f"Contribution with ID {contribution_id} does not exist.")
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Contribution Report"

    # Define styles
    title_font = Font(size=16, bold=True)
    header_font = Font(size=14, bold=True)
    header_fill = PatternFill(start_color="00C0C0C0", end_color="00C0C0C0", fill_type="solid")
    header_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # Set the headers with styles (start from row 3)
    contribution_header = [ 
        "Contribution ID",
        "Member ID",
        "Member Name",
        "For Month",
        "Due Date",
        "Payment Date",
        "Payment Status",
        "Verified By Organizer",
    ]

    # Add title
    title_cell = sheet.cell(row=1, column=2)
    title_cell.value = "Contribution Report"
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="center")
    sheet.merge_cells(start_row=1, start_column=2, end_row=1, end_column=len(contribution_header) + 1)

    # Create headers
    for col_num, header in enumerate(contribution_header, start=2):
        cell = sheet.cell(row=3, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = header_border

    # Add data
    row_index = 4
    data = [
        contribution.id,
        contribution.membership.member.id,
        contribution.membership.member.full_name,
        contribution.for_month.strftime("%m/%d/%Y"),
        contribution.due_date.strftime("%m/%d/%Y") if contribution.due_date else 'Not Set',
        contribution.payment_date.strftime("%m/%d/%Y") if contribution.payment_date else 'Not Paid',
        contribution.payment_status,
        contribution.verified_by_organizer,
    ]

    for col_num, value in enumerate(data, start=2):
        cell = sheet.cell(row=row_index, column=col_num)
        cell.value = value
        cell.alignment = Alignment(horizontal="center")

    # Set column widths for better readability
    for col_num in range(2, len(contribution_header) + 2):
        sheet.column_dimensions[chr(64 + col_num)].width = 20

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

    try:
        contribution = Contribution.objects.get(id=contribution_id)
    except Contribution.DoesNotExist:
        print(f"Contribution with ID {contribution_id} does not exist.")
        return

    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=landscape(letter))
    elements = []

    # Set up stylesheet and title
    stylesheet = getSampleStyleSheet()
    title_style = stylesheet["Title"]
    title_style.alignment = 1

    # Add heading
    heading = Paragraph("Contribution Report", title_style)
    elements.append(heading)
    elements.append(Spacer(1, 12))

    # Create the contribution data table
    contribution_data = [
        ["Contribution ID", "Member ID", "Member Name", "For Month", "Due Date", "Payment Date", "Payment Status", "Verified By Organizer"],
        [
            contribution.id,
            contribution.membership.member.id,
            contribution.membership.member.full_name,
            contribution.for_month.strftime("%m/%d/%Y"),
            contribution.due_date.strftime("%m/%d/%Y") if contribution.due_date else 'Not Set',
            contribution.payment_date.strftime("%m/%d/%Y") if contribution.payment_date else 'Not Paid',
            contribution.payment_status,
            contribution.verified_by_organizer,
        ]
    ]

    # Create the table with better styling
    t1 = Table(contribution_data, colWidths=[100] * len(contribution_data[0]))

    # Define table style
    table_style = TableStyle(
        [
            # Header row style
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),

            # Data row style
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),

            # Alternating row background
            ("BACKGROUND", (0, 2), (-1, 2), colors.lightgrey),

            # Grid lines
            ("GRID", (0, 0), (-1, -1), 1, colors.black),

            # Padding and spacing
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )
    t1.setStyle(table_style)
    elements.append(t1)
    elements.append(Spacer(1, 24))
    doc.build(elements)
    buff.seek(0)

    # Save the PDF file
    file = InMemoryUploadedFile(buff, "pdf", f"{contribution.id}.pdf", None, buff.tell(), None)
    contribution.pdf_file.save(f"Contribution_Report_{contribution.id}.pdf", file)
    contribution.save()


@app.task
def generate_payout_excel_file(payout_id):
    from .models import Payout

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        print(f"Payout with ID {payout_id} does not exist.")
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Payout Report"

    # Define styles
    title_font = Font(size=16, bold=True)
    header_font = Font(size=14, bold=True)
    header_fill = PatternFill(start_color="00C0C0C0", end_color="00C0C0C0", fill_type="solid")
    header_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # Set the headers with styles (start from row 3)
    payout_header = [
        "Payout ID",
        "Member ID",
        "Member Name",
        "Total Amount",
        "Paid At",
        "Received By",
        "Is Confirmed",
        "Received In Cash",
        "Confirmed At",
    ]

    # Add title
    title_cell = sheet.cell(row=1, column=2)
    title_cell.value = "Payment Receipt Report"
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="center")
    sheet.merge_cells(start_row=1, start_column=2, end_row=1, end_column=len(payout_header) + 1)

    # Create headers
    for col_num, header in enumerate(payout_header, start=2):
        cell = sheet.cell(row=3, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = header_border

    # Add data
    row_index = 4
    data = [
        payout.id,
        payout.membership.member.id,
        payout.membership.member.full_name,
        payout.total_amount,
        payout.paid_at.strftime("%d/%m/%Y"),
        payout.received_by.full_name if payout.received_by else 'Not Specified',
        payout.is_confirmed,
        payout.received_in_cash,
        payout.confirmed_at.strftime("%d/%m/%Y") if payout.confirmed_at else 'Not Confirmed',
    ]

    for col_num, value in enumerate(data, start=2):
        cell = sheet.cell(row=row_index, column=col_num)
        cell.value = value
        cell.alignment = Alignment(horizontal="center")

    # Set column widths for better readability
    for col_num in range(2, len(payout_header) + 2):
        sheet.column_dimensions[chr(64 + col_num)].width = 20

    # Save the Excel file
    buff = BytesIO()
    workbook.save(buff)
    buff.seek(0)
    file = InMemoryUploadedFile(buff, "xlsx", f"Payout_Report{payout.id}.xlsx", None, buff.tell(), None)
    payout.excel_file.save(f"Payout_Report_{payout.id}.xlsx", file)
    payout.save()


@app.task
def generate_payout_pdf_file(payout_id):
    from .models import Payout

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        print(f"Payout with ID {payout_id} does not exist.")
        return

    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=landscape(letter))
    elements = []

    # Set up stylesheet and title
    stylesheet = getSampleStyleSheet()
    title_style = stylesheet["Title"]
    title_style.alignment = 1

    # Add heading
    heading = Paragraph("Payout Report", title_style)
    elements.append(heading)
    elements.append(Spacer(1, 12))

    # Create the payout data table
    payout_data = [
        ["Payout ID", "Member ID", "Member Name", "Total Amount", "Paid At", "Received By", "Is Confirmed", "Received In Cash", "Confirmed At"],
        [
          payout.id,
          payout.membership.member.id,
          payout.membership.member.full_name,
          payout.total_amount,
          payout.paid_at.strftime("%m/%d/%Y"),
          payout.received_by.full_name if payout.received_by else 'Not Specified',
          payout.is_confirmed,
          payout.received_in_cash,
          payout.confirmed_at.strftime("%m/%d/%Y") if payout.confirmed_at else 'Not Confirmed',
        ]
    ]

    # Create the table with better styling
    t1 = Table(payout_data, colWidths=[100] * len(payout_data[0]))

    # Define table style
    table_style = TableStyle(
        [
            # Header row style
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),

            # Data row style
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),

            # Alternating row background
            ("BACKGROUND", (0, 2), (-1, 2), colors.lightgrey),

            # Grid lines
            ("GRID", (0, 0), (-1, -1), 1, colors.black),

            # Padding and spacing
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )
    t1.setStyle(table_style)
    elements.append(t1)
    elements.append(Spacer(1, 24))
    doc.build(elements)
    buff.seek(0)

    # Save the PDF file
    file = InMemoryUploadedFile(buff, "pdf", f"{payout.id}.pdf", None, buff.tell(), None)
    payout.pdf_file.save(f"Payout_Report_{payout.id}.pdf", file)
    payout.save()
