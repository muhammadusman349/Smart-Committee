from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from .forms import (
    UserUpdateForm,
    ProfileUpdateForm,
    ContactForm,
    NewsletterForm,
    AdminReplyForm
)
from .models import Profile, Contact
from .tasks import send_contact_notification_email, send_admin_reply_email, send_newsletter_welcome_email
from committee.models import Committee, Membership, Contribution


def home(request):
    if request.user.is_authenticated:
        if request.user.is_organizer:
            return redirect('committee:organizer_dashboard')
        else:
            return redirect('committee:member_dashboard')  # Fallback for members
    else:
        context = {
            'total_committees_all': Committee.objects.count(),
            'total_members_all': Membership.objects.count(),
            'total_contributions_all': Contribution.objects.filter(payment_status='PAID').aggregate(total=Sum('amount_paid'))['total'] or 0,
        }
        return render(request, 'home.html', context)


@login_required
def profile_view(request):
    # Get or create profile for the user
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, 
            request.FILES, 
            instance=profile
        )
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


# Service Pages
def financial_tracking(request):
    """Financial Tracking service page"""
    return render(request, 'services/financial_tracking.html')


def member_management(request):
    """Member Management service page"""
    return render(request, 'services/member_management.html')


def reporting_analytics(request):
    """Reporting & Analytics service page"""
    return render(request, 'services/reporting_analytics.html')


def security_compliance(request):
    """Security & Compliance service page"""
    return render(request, 'services/security_compliance.html')


def features(request):
    """Features page"""
    return render(request, 'pages/features.html')


# Legal Pages
def privacy_policy(request):
    """Privacy Policy page"""
    return render(request, 'legal/privacy_policy.html')


def terms_of_service(request):
    """Terms of Service page"""
    return render(request, 'legal/terms_of_service.html')


def contact(request):
    """Contact page with form handling"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save()

            # Send notification email to admin using Celery
            try:
                send_contact_notification_email.delay(contact_message.id)
                messages.success(request, 'Thank you for your message! We\'ll get back to you soon.')
            except Exception as e:
                print(f"Failed to queue notification email: {e}")
                messages.success(request, 'Thank you for your message! We\'ll get back to you soon.')

            return redirect('contact')
    else:
        form = ContactForm()

    return render(request, 'contact/contact.html', {'form': form})


def newsletter_signup(request):
    """Handle newsletter signup from footer"""
    if request.method == 'POST':
        form = NewsletterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Check if email already subscribed
            existing_subscription = Contact.objects.filter(
                email=email, 
                contact_type='newsletter'
            ).exists()

            if existing_subscription:
                messages.info(request, 'You are already subscribed to our newsletter!')
            else:
                # Create a contact entry for newsletter subscription
                Contact.objects.create(
                    name='Newsletter Subscriber',
                    email=email,
                    contact_type='newsletter',
                    subject='Newsletter Subscription',
                    message=f'User {email} subscribed to newsletter.'
                )

                # Send welcome email using Celery
                try:
                    send_newsletter_welcome_email.delay(email)
                except Exception as e:
                    print(f"Failed to queue welcome email: {e}")

                messages.success(request, 'Successfully subscribed to our newsletter!')

            return redirect('home')
        else:
            messages.error(request, 'Please enter a valid email address.')

    return redirect('home')


# Admin Views for Contact Management
@staff_member_required
def admin_contacts_list(request):
    """Admin view to list all contacts with filtering and pagination"""
    contacts = Contact.objects.all()

    # Filtering
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    if status_filter == 'new':
        contacts = contacts.filter(is_read=False, is_replied=False)
    elif status_filter == 'read':
        contacts = contacts.filter(is_read=True, is_replied=False)
    elif status_filter == 'replied':
        contacts = contacts.filter(is_replied=True)

    if type_filter:
        contacts = contacts.filter(contact_type=type_filter)

    # Pagination
    paginator = Paginator(contacts, 20)  # Show 20 contacts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'contact_types': Contact.CONTACT_TYPES,
        'total_new': Contact.objects.filter(is_read=False, is_replied=False).count(),
        'total_read': Contact.objects.filter(is_read=True, is_replied=False).count(),
        'total_replied': Contact.objects.filter(is_replied=True).count(),
    }

    return render(request, 'admin/contacts_list.html', context)


@staff_member_required
def admin_contact_detail(request, contact_id):
    """Admin view to view and reply to a specific contact"""
    contact = get_object_or_404(Contact, id=contact_id)

    # Mark as read when admin views it
    if not contact.is_read:
        contact.is_read = True
        contact.save()

    if request.method == 'POST':
        form = AdminReplyForm(request.POST)
        if form.is_valid():
            reply_message = form.cleaned_data['reply_message']
            mark_as_read = form.cleaned_data['mark_as_read']

            # Update contact with reply
            contact.admin_reply = reply_message
            contact.replied_by = request.user
            contact.replied_at = timezone.now()
            contact.is_replied = True

            if mark_as_read:
                contact.is_read = True

            contact.save()

            # Send reply email using Celery
            try:
                admin_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email
                send_admin_reply_email.delay(contact.id, reply_message, admin_name)
                messages.success(request, f'Reply sent successfully to {contact.email}')
            except Exception as e:
                print(f"Failed to queue reply email: {e}")
                messages.warning(request, 'Reply saved but email sending failed. Please try again.')

            return redirect('contact_detail', contact_id=contact.id)
    else:
        form = AdminReplyForm()

    context = {
        'contact': contact,
        'form': form,
    }

    return render(request, 'admin/contact_detail.html', context)


@staff_member_required
def admin_contact_mark_read(request, contact_id):
    """Admin view to mark a contact as read"""
    contact = get_object_or_404(Contact, id=contact_id)
    contact.is_read = True
    contact.save()
    messages.success(request, f'Contact from {contact.name} marked as read.')
    return redirect('contacts_list')


@staff_member_required
def admin_contact_delete(request, contact_id):
    """Admin view to delete a contact"""
    contact = get_object_or_404(Contact, id=contact_id)

    if request.method == 'POST':
        contact_name = contact.name
        contact.delete()
        messages.success(request, f'Contact from {contact_name} has been deleted.')
        return redirect('contacts_list')

    return render(request, 'admin/contact_delete_confirm.html', {'contact': contact})
