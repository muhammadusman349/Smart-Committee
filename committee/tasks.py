from django.apps import apps
from celery import shared_task
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings


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
