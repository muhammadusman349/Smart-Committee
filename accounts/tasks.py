from django.apps import apps
from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.utils import timezone


@shared_task
def send_contact_notification_email(contact_id):
    """
    Celery task to send contact notification email to admin asynchronously
    """
    try:
        # Get contact details
        Contact = apps.get_model('accounts', 'Contact')
        contact = Contact.objects.get(id=contact_id)

        # Prepare template context
        try:
            admin_url = f"http://{settings.ALLOWED_HOSTS[0]}/admin/contacts/{contact.id}/" if settings.ALLOWED_HOSTS else "#"
        except (IndexError, AttributeError):
            admin_url = "#"
        
        context = {
            'contact': contact,
            'admin_url': admin_url,
        }

        # Render email templates
        subject = f"New Contact Message: {contact.subject}"
        html_content = render_to_string('emails/contact_notification.html', context)
        text_content = render_to_string('emails/contact_notification.txt', context)

        # Send email with HTML and text versions
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL]  # Send to admin
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            return f"Contact notification email sent successfully for contact ID: {contact_id}"
        except Exception as email_error:
            error_msg = f"SMTP Error sending contact notification: {str(email_error)}"
            print(f"EMAIL ERROR: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Failed to send contact notification email: {str(e)}"
        print(f"TASK ERROR: {error_msg}")
        raise Exception(error_msg)


@shared_task
def send_admin_reply_email(contact_id, reply_message, admin_name=None):
    """
    Celery task to send admin reply email to contact submitter
    """
    try:
        # Get contact details
        Contact = apps.get_model('accounts', 'Contact')
        contact = Contact.objects.get(id=contact_id)

        # Prepare template context
        context = {
            'contact': contact,
            'reply_message': reply_message,
            'admin_signature': admin_name or "Support Team",
            'current_year': timezone.now().year,
        }

        # Render email templates
        subject = f"Re: {contact.subject}"
        html_content = render_to_string('emails/admin_reply.html', context)
        text_content = render_to_string('emails/admin_reply.txt', context)

        # Send email with HTML and text versions
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[contact.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            
            # Mark contact as replied
            contact.is_replied = True
            contact.save()
            
            return f"Admin reply email sent successfully to {contact.email}"
        except Exception as email_error:
            error_msg = f"SMTP Error sending admin reply: {str(email_error)}"
            print(f"EMAIL ERROR: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Failed to send admin reply email: {str(e)}"
        print(f"TASK ERROR: {error_msg}")
        raise Exception(error_msg)


@shared_task
def send_newsletter_welcome_email(email):
    """
    Celery task to send welcome email to newsletter subscribers
    """
    try:
        # Prepare template context
        try:
            platform_url = f"http://{settings.ALLOWED_HOSTS[0]}/" if settings.ALLOWED_HOSTS else "#"
            contact_url = f"http://{settings.ALLOWED_HOSTS[0]}/contact/" if settings.ALLOWED_HOSTS else "#"
        except (IndexError, AttributeError):
            platform_url = "#"
            contact_url = "#"
        
        context = {
            'email': email,
            'platform_url': platform_url,
            'contact_url': contact_url,
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'current_year': timezone.now().year,
        }

        # Render email templates
        subject = "Welcome to FinanceCore Newsletter!"
        html_content = render_to_string('emails/newsletter_welcome.html', context)
        text_content = render_to_string('emails/newsletter_welcome.txt', context)

        # Send email with HTML and text versions
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            return f"Newsletter welcome email sent successfully to {email}"
        except Exception as email_error:
            error_msg = f"SMTP Error sending newsletter welcome: {str(email_error)}"
            print(f"EMAIL ERROR: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Failed to send newsletter welcome email: {str(e)}"
        print(f"TASK ERROR: {error_msg}")
        raise Exception(error_msg)
