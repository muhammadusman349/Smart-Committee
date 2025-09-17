from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from accounts.models import User
from django.db.models import Sum
from datetime import date, timedelta
import calendar
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from .models import Committee, Membership, Contribution, Payout, Invitation
from .forms import (
    CommitteeForm,
    MembershipForm,
    ContributionForm,
    PayoutForm,
    InvitationForm
)
from secrets import token_urlsafe
from .tasks import send_invitation_email
from django.views.decorators.http import require_http_methods

# Committee Views


@login_required
def committee_list(request):
    """List committees for the logged-in organizer with pagination"""
    # Ensure only organizers can access
    if not request.user.is_organizer:
        messages.error(request, "Only organizers can view this page.")
        return redirect('home')

    committees_list = Committee.objects.filter(
        organizer=request.user
    ).order_by('start_date')

    # Pagination - 5 items per page
    paginator = Paginator(committees_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'committee/list.html', {
        'committees': page_obj,
        'page_obj': page_obj
    })


@login_required
def committee_detail(request, pk):
    """Committee details with permission checks"""
    committee = get_object_or_404(Committee, pk=pk)
    is_organizer = committee.organizer == request.user

    # Get all memberships for this committee
    memberships = committee.memberships.select_related('member').all()

    # Get total contributions for this committee
    total_contributions = Contribution.objects.filter(
        membership__committee=committee
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0

    # Get total payouts for this committee
    total_payouts = Payout.objects.filter(
        membership__committee=committee
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    # Get available users who are not yet members
    existing_member_ids = memberships.values_list('member_id', flat=True)
    available_users = User.objects.exclude(id=committee.organizer_id).exclude(id__in=existing_member_ids)

    # Get the user's active membership in this committee, if it exists
    user_membership = committee.memberships.filter(member=request.user, status='ACTIVE').first()
    is_member = user_membership is not None

    if not (is_organizer or is_member):
        messages.error(request, "You don't have permission to view this committee")
        return redirect('committee:committee_list')

    return render(request, 'committee/detail.html', {
        'committee': committee,
        'is_organizer': is_organizer,
        'memberships': memberships,
        'total_contributions': total_contributions,
        'total_payouts': total_payouts,
        'available_users': available_users,
        'user_membership': user_membership,
        'is_member': is_member,
    })


@login_required
def invitation_send(request, committee_pk):
    """Organizer sends an invitation to join a committee via email"""
    committee = get_object_or_404(Committee, pk=committee_pk)
    if committee.organizer != request.user:
        messages.error(request, "Only the organizer can send invitations for this committee.")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = InvitationForm(request.POST, request=request, committee=committee)
        if form.is_valid():
            email = form.cleaned_data['email']
            token = token_urlsafe(32)
            invitation = Invitation.objects.create(
                committee=committee,
                invited_by=request.user,
                email=email,
                token=token,
            )

            # Send invitation email asynchronously using Celery
            send_invitation_email.delay(
                committee_id=committee.id,
                inviter_name=request.user.full_name,
                inviter_email=request.user.email,
                recipient_email=email,
                token=token,
                site_domain=request.get_host()
            )

            messages.success(request, f"Invitation is being sent to {email}.")
            return redirect('committee:committee_detail', pk=committee.pk)
    else:
        form = InvitationForm(request=request, committee=committee)

    return render(request, 'committee/invitation_form.html', {
        'form': form,
        'committee': committee,
        'title': 'Invite Member'
    })


def _can_accept(invitation: Invitation, user: User) -> bool:
    """Helper to check if user can accept the invitation."""
    # Must be logged in to compare emails
    if not getattr(user, 'is_authenticated', False):
        return False

    if invitation.status != 'PENDING':
        return False
    if invitation.expires_at and timezone.now() > invitation.expires_at:
        return False
    # Email must match
    return user.email.lower() == invitation.email.lower()


def invitation_accept(request, token):
    """Accept an invitation by token. Requires login with the same email."""
    invitation = get_object_or_404(Invitation, token=token)

    if invitation.status != 'PENDING':
        messages.error(request, "This invitation is no longer valid.")
        return render(request, 'committee/invitation_status.html', {
            'invitation': invitation,
            'status': 'invalid'
        })

    # Auto-expire if past expiry
    if invitation.expires_at and timezone.now() > invitation.expires_at:
        invitation.status = 'EXPIRED'
        invitation.save()
        messages.error(request, "This invitation has expired.")
        return render(request, 'committee/invitation_status.html', {
            'invitation': invitation,
            'status': 'expired'
        })

    if not _can_accept(invitation, request.user):
        # Suggest logging in with the invited email or signing up
        login_url = reverse('account_login') + f"?next={request.path}"
        signup_url = reverse('account_signup') + f"?next={request.path}"
        return render(request, 'committee/invitation_accept_login_required.html', {
            'invitation': invitation,
            'login_url': login_url,
            'signup_url': signup_url,
        })

    # Create membership if not exists
    committee = invitation.committee
    member = request.user
    Membership.objects.get_or_create(committee=committee, member=member, defaults={'status': 'ACTIVE'})

    # Mark invitation as accepted and expire the token
    invitation.status = 'ACCEPTED'
    invitation.expires_at = timezone.now()  # Immediately expire the token
    invitation.save()

    messages.success(request, f"You have successfully joined the committee '{committee.name}'.")
    return redirect('committee:member_committee_detail', pk=committee.pk)


@login_required
def invitation_list(request, pk):
    """View and manage invitations for a committee"""
    committee = get_object_or_404(Committee, pk=pk, organizer=request.user)
    invitations = committee.invitations.all().order_by('-created_at')

    # Accurate counts for statuses
    pending_count = invitations.filter(status='PENDING').count()
    accepted_count = invitations.filter(status='ACCEPTED').count()
    expired_count = invitations.filter(status='EXPIRED').count()
    total_count = invitations.count()

    return render(request, 'committee/invitation_list.html', {
        'committee': committee,
        'invitations': invitations,
        'pending_count': pending_count,
        'accepted_count': accepted_count,
        'expired_count': expired_count,
        'total_count': total_count,
        'scheme': request.scheme,
        'site_domain': request.get_host(),
    })


@login_required
@require_http_methods(["POST"])
def invitation_resend(request, pk):
    """Resend an expired or failed invitation"""
    invitation = get_object_or_404(Invitation, pk=pk)

    # Security check: only organizer can resend
    if invitation.committee.organizer != request.user:
        messages.error(request, "You don't have permission to resend this invitation.")
        return redirect('committee:committee_detail', pk=invitation.committee.pk)

    # Only allow resending if invitation is expired or pending
    if invitation.status not in ['EXPIRED', 'PENDING']:
        messages.error(request, "This invitation cannot be resent.")
        return redirect('committee:invitation_list', pk=invitation.committee.pk)

    # Generate new token and reset expiry
    invitation.token = token_urlsafe(32)
    invitation.expires_at = timezone.now() + timedelta(days=7)
    invitation.status = 'PENDING'
    invitation.save()

    # Send new invitation email
    send_invitation_email.delay(
        invitation_id=invitation.id,
        committee_name=invitation.committee.name,
        organizer_name=invitation.invited_by.get_full_name(),
        recipient_email=invitation.email,
        token=invitation.token,
        site_domain=request.get_host()
    )

    messages.success(request, f"Invitation has been resent to {invitation.email}.")
    return redirect('committee:invitation_list', pk=invitation.committee.pk)


@login_required
@require_http_methods(["POST"])
def invitation_revoke(request, pk):
    """Revoke a pending invitation"""
    invitation = get_object_or_404(Invitation, pk=pk)

    # Security check: only organizer can revoke
    if invitation.committee.organizer != request.user:
        messages.error(request, "You don't have permission to revoke this invitation.")
        return redirect('committee:committee_detail', pk=invitation.committee.pk)

    # Only allow revoking pending invitations
    if invitation.status != 'PENDING':
        messages.error(request, "This invitation cannot be revoked.")
        return redirect('committee:invitation_list', pk=invitation.committee.pk)

    # Mark as expired
    invitation.status = 'EXPIRED'
    invitation.expires_at = timezone.now()
    invitation.save()

    messages.success(request, f"Invitation to {invitation.email} has been revoked.")
    return redirect('committee:invitation_list', pk=invitation.committee.pk)


@login_required
def switch_to_organizer(request):
    """Allow members to become organizers"""
    if not request.user.is_organizer:
        request.user.is_organizer = True
        request.user.save()
        messages.success(request, "You've been upgraded to organizer status! You can now create and manage committees.")
        return redirect('committee:organizer_dashboard')
    else:
        messages.info(request, "You're already an organizer.")
        return redirect('committee:organizer_dashboard')


@login_required
def step_down_organizer(request):
    """Allow organizers to remove their organizer status"""
    if not request.user.is_organizer:
        messages.error(request, "You're not currently an organizer.")
        return redirect('committee:member_dashboard')

    # Check if user has any committees they organize
    organized_committees = Committee.objects.filter(organizer=request.user).count()

    if organized_committees > 0:
        messages.error(request, f"You cannot step down as organizer while you have {organized_committees} active committee(s). Please transfer or delete your committees first.")
        return redirect('committee:organizer_dashboard')

    # Remove organizer status
    request.user.is_organizer = False
    request.user.save()

    messages.success(request, "You have stepped down from organizer status. You can become an organizer again anytime by creating a committee.")
    return redirect('committee:member_dashboard')


@login_required
def committee_create(request):
    """Committee creation - auto-upgrades members to organizers"""
    # Auto-upgrade to organizer if user is creating their first committee
    if not request.user.is_organizer:
        request.user.is_organizer = True
        request.user.save()
        messages.info(request, "You've been upgraded to organizer status!")

    if request.method == 'POST':
        form = CommitteeForm(request.POST, request=request)
        if form.is_valid():
            committee = form.save()
            messages.success(request, 'Committee created successfully!')
            return redirect('committee:committee_detail', pk=committee.pk)
    else:
        form = CommitteeForm(request=request)

    return render(request, 'committee/form.html', {
        'form': form,
        'title': 'Create Committee'
    })


@login_required
def committee_update(request, pk):
    """Update committee (organizer only)"""
    committee = get_object_or_404(Committee, pk=pk)
    if committee.organizer != request.user:
        messages.error(request, "You don't have permission to edit this committee")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = CommitteeForm(request.POST, instance=committee, request=request)
        if form.is_valid():
            # Save the form to get the updated instance
            updated_committee = form.save(commit=False)

            # Check if start date or duration has changed
            if ('start_date' in form.changed_data or
                'duration_months' in form.changed_data):
                # Recalculate end date based on new start date and duration
                from dateutil.relativedelta import relativedelta
                updated_committee.end_date = (
                    updated_committee.start_date +
                    relativedelta(months=updated_committee.duration_months)
                )

                # If the new end date is in the past and committee is active, mark as completed
                from datetime import date
                if (updated_committee.status == 'ACTIVE' and
                    updated_committee.end_date and
                    updated_committee.end_date < date.today()):
                    updated_committee.status = 'COMPLETED'

            # Save the committee with updated end date and status
            updated_committee.save()
            form.save_m2m()  # Save many-to-many data if any

            messages.success(request, 'Committee updated successfully!')
            return redirect('committee:committee_detail', pk=committee.pk)
    else:
        form = CommitteeForm(instance=committee, request=request)

    return render(request, 'committee/form.html', {
        'form': form,
        'committee': committee,  # Pass committee to template for back link
        'title': 'Update Committee'
    })


@login_required
def committee_delete(request, pk):
    """Delete committee (organizer only)"""
    committee = get_object_or_404(Committee, pk=pk)
    if committee.organizer != request.user:
        messages.error(request, "You don't have permission to delete this committee")
        return redirect('committee:committee_detail', pk=committee.pk)

    committee.delete()
    messages.success(request, 'Committee deleted successfully!')
    return redirect('committee:committee_list')


# Membership Views
@login_required
def membership_list(request, pk):
    """List all members of a committee (organizer and members)"""
    committee = get_object_or_404(Committee, pk=pk)
    is_organizer = committee.organizer == request.user
    is_member = committee.memberships.filter(member=request.user, status='ACTIVE').exists()

    if not (is_organizer or is_member):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('committee:committee_detail', pk=pk)

    memberships = committee.memberships.all().order_by('-joined_at')
    return render(request, 'committee/membership_list.html', {
        'committee': committee,
        'memberships': memberships,
    })


@login_required
def membership_create(request, committee_pk):
    """Add member to committee (organizer only)"""
    committee = get_object_or_404(Committee, pk=committee_pk)
    if committee.organizer != request.user:
        messages.error(request, "Only the organizer can add members to this committee.")
        return redirect('committee:committee_detail', pk=committee_pk)

    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')

        if not user_ids:
            messages.error(request, "Please select at least one member to add.")
            return redirect('committee:committee_detail', pk=committee_pk)

        added_count = 0
        already_members = 0

        for user_id in user_ids:
            try:
                user = User.objects.get(pk=user_id)
                if not Membership.objects.filter(committee=committee, member=user).exists():
                    Membership.objects.create(committee=committee, member=user)
                    added_count += 1
                else:
                    already_members += 1
            except User.DoesNotExist:
                continue

        if added_count > 0:
            messages.success(request, f"Successfully added {added_count} member(s) to the committee.")
        if already_members > 0:
            messages.warning(request, f"{already_members} selected user(s) were already members of this committee.")

        return redirect('committee:committee_detail', pk=committee_pk)

    # For GET request, we'll handle it in the committee_detail view
    return redirect('committee:committee_detail', pk=committee_pk)


@login_required
def membership_update(request, pk):
    """Update membership status"""
    membership = get_object_or_404(Membership, pk=pk)
    committee = membership.committee
    source = request.GET.get('source', 'committee')

    if committee.organizer != request.user:
        messages.error(request, "Only the organizer can update memberships for this committee.")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = MembershipForm(request.POST, instance=membership, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Membership updated successfully!')
            if source == 'all_members':
                return redirect('committee:see_all_members')
            return redirect('committee:membership_list', pk=committee.pk)
    else:
        form = MembershipForm(instance=membership, request=request)

    return render(request, 'committee/membership_form_update.html', {
        'form': form,
        'title': 'Update Membership',
        'membership': membership,
        'source': source
    })


@login_required
def membership_delete(request, pk):
    """Delete membership (organizer only)"""
    membership = get_object_or_404(Membership, pk=pk)
    committee = membership.committee

    if committee.organizer != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': "You don't have permission to delete this membership"
            }, status=403)
        messages.error(request, "You don't have permission to delete this membership")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        member_name = membership.member.full_name
        membership.delete()
        success_message = f'Member "{member_name}" has been removed from the committee successfully!'

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.get_messages(request).used = True  # Clear any existing messages
            messages.success(request, success_message)

            # Determine redirect URL
            source = request.GET.get('source', '')
            if source == 'all_members':
                redirect_url = reverse('committee:see_all_members')
            else:
                redirect_url = reverse('committee:committee_detail', kwargs={'pk': committee.pk})

            return JsonResponse({
                'success': True,
                'message': success_message,
                'redirect': redirect_url
            })

        # For non-AJAX requests
        messages.success(request, success_message)
        if request.GET.get('source') == 'all_members':
            return redirect('committee:see_all_members')
        return redirect('committee:committee_detail', pk=committee.pk)

    # GET request - redirect to the appropriate page
    if request.GET.get('source') == 'all_members':
        return redirect('committee:see_all_members')
    return redirect('committee:committee_detail', pk=committee.pk)


# Contribution Views
@login_required
def contribution_create(request, membership_pk):
    """Record contribution (organizer only)"""
    membership = get_object_or_404(Membership, pk=membership_pk)
    is_organizer = membership.committee.organizer == request.user

    if not is_organizer:
        messages.error(request, "Only organizers can add contributions.")
        return redirect('committee:committee_detail', pk=membership.committee.pk)

    if request.method == 'POST':
        form = ContributionForm(request.POST, request=request, membership=membership)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contribution recorded successfully!')
            return redirect('committee:membership_list', pk=membership.committee.pk)
    else:
        form = ContributionForm(request=request, membership=membership)

    return render(request, 'committee/contribution_form.html', {
        'form': form,
        'title': 'Record Contribution',
        'membership': membership
    })


@login_required
def contribution_update(request, pk):
    """Update contribution (organizer only)"""
    contribution = get_object_or_404(Contribution, pk=pk)
    membership = contribution.membership
    is_organizer = membership.committee.organizer == request.user

    if not is_organizer:
        messages.error(request, "Only organizers can update contributions.")
        return redirect('committee:committee_detail', pk=membership.committee.pk)

    if contribution.payment_status == 'PAID':
        messages.error(request, 'Cannot edit a paid contribution.')
        return redirect('committee:manage_contributions')

    if request.method == 'POST':
        form = ContributionForm(request.POST, instance=contribution, request=request, membership=membership)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contribution updated successfully!')
            return redirect('committee:manage_contributions')
    else:
        form = ContributionForm(instance=contribution, request=request, membership=membership)

    return render(request, 'committee/contribution_form.html', {
        'form': form,
        'title': 'Update Contribution',
        'membership': membership,
        'contribution': contribution,
        'is_readonly': contribution.payment_status == 'PAID'
    })


@login_required
def contribution_delete(request, pk):
    """Delete contribution (organizer only)"""
    contribution = get_object_or_404(Contribution, pk=pk)
    is_organizer = contribution.membership.committee.organizer == request.user

    if not is_organizer:
        messages.error(request, "Only organizers can delete contributions.")
        return redirect('committee:committee_detail', pk=contribution.membership.committee.pk)

    if request.method == 'POST':
        contribution.delete()
        messages.success(request, 'Contribution deleted successfully!')
        return redirect('committee:manage_contributions')

    return redirect('committee:manage_contributions')


# contribution verify
@login_required
def contribution_verify(request, pk):
    contribution = get_object_or_404(Contribution, pk=pk)

    # Only organizer of the committee can verify
    if request.user != contribution.membership.committee.organizer:
        messages.error(request, "You are not authorized to verify this contribution.")
        return redirect('committee:manage_contributions')

    if contribution.verified_by_organizer:
        messages.error(request, "This contribution has already been verified.")
        return redirect('committee:manage_contributions')

    if request.method == 'POST':
        contribution.verified_by_organizer = True
        contribution.save()
        messages.success(request, 'Contribution verified successfully!')
        return redirect('committee:manage_contributions')

    return redirect('committee:manage_contributions')


# Payout Views
@login_required
def payout_create(request, membership_pk):
    """Create payout (organizer only)"""
    membership = get_object_or_404(Membership, pk=membership_pk)
    committee = membership.committee

    if committee.organizer != request.user:
        messages.error(request, "Only the organizer can create payouts for this committee.")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = PayoutForm(
            request.POST,
            request=request,
            membership=membership,
            initial={'is_confirmed': True}  # Auto-confirm for organizers
        )

        if form.is_valid():
            try:
                payout = form.save(commit=False)
                payout.membership = membership
                payout.is_confirmed = True  # Always confirm for organizers
                payout.confirmed_at = timezone.now()

                payout.save()
                form.save_m2m()

                messages.success(request, 'Payout created and confirmed successfully!')
                return redirect('committee:manage_payouts')

            except Exception as e:
                messages.error(request, f'Error creating payout: {str(e)}')
    else:
        form = PayoutForm(
            request=request,
            membership=membership,
            initial={
                'received_by': membership.member,
                'is_confirmed': True,
                'date': timezone.now().date()
            }
        )

    return render(request, 'committee/payout_form.html', {
        'form': form,
        'title': 'Create Payout',
        'membership': membership
    })


@login_required
def payout_update(request, pk):
    """Update payout (organizer only)"""
    payout = get_object_or_404(Payout, pk=pk)
    membership = payout.membership
    committee = membership.committee

    if committee.organizer != request.user:
        messages.error(request, "Only the organizer can update payouts for this committee.")
        return redirect('committee:committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = PayoutForm(
            request.POST,
            instance=payout,
            request=request,
            membership=membership
        )

        if form.is_valid():
            try:
                updated_payout = form.save(commit=False)

                # Only update confirmed_at if it wasn't confirmed before but is now
                if not payout.is_confirmed and form.cleaned_data.get('is_confirmed'):
                    updated_payout.confirmed_at = timezone.now()

                updated_payout.save()
                form.save_m2m()

                messages.success(request, 'Payout updated successfully!')
                return redirect('committee:manage_payouts')

            except Exception as e:
                messages.error(request, f'Error updating payout: {str(e)}')
    else:
        form = PayoutForm(
            instance=payout,
            request=request,
            membership=membership
        )

    return render(request, 'committee/payout_form.html', {
        'form': form,
        'title': 'Update Payout',
        'membership': membership
    })


@login_required
def payout_delete(request, pk):
    """Delete payout (organizer only)"""
    payout = get_object_or_404(Payout, pk=pk)

    # Check if user is the organizer
    if payout.membership.committee.organizer != request.user:
        messages.error(request, "Only the organizer can delete payouts")
        return redirect('committee:manage_payouts')

    # Handle POST request (form submission)
    if request.method == 'POST':
        payout.delete()
        messages.success(request, 'Payout deleted successfully!')
        return redirect('committee:manage_payouts')

    # Handle GET request (show confirmation page)
    return render(request, 'committee/payout_confirm_delete.html', {
        'payout': payout
    })


# Organizer Dashboard Views
@login_required
def organizer_dashboard(request):
    """Dashboard for organizers to manage committees and view statistics"""
    if not request.user.is_organizer:
        messages.error(request, "Only organizers can access the dashboard")
        return redirect('committee:member_dashboard')

    # Check if organizer is also a member of any committee
    is_also_member = Membership.objects.filter(member=request.user, status='ACTIVE').exists()

    # Calculate statistics
    total_committees = Committee.objects.filter(organizer=request.user).count()
    total_members = Membership.objects.filter(committee__organizer=request.user).count()
    total_contributions = Contribution.objects.filter(
        membership__committee__organizer=request.user,
        payment_status='PAID'
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    total_payouts = Payout.objects.filter(
        membership__committee__organizer=request.user,
        is_confirmed=True
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Recent activities
    now = timezone.now()
    latest_committee = Committee.objects.filter(organizer=request.user).last()
    new_committee_created = None
    if latest_committee:
        time_diff = now - latest_committee.created_at
        new_committee_created = int(time_diff.total_seconds() // 3600)

    latest_membership = Membership.objects.filter(committee__organizer=request.user).last()
    new_member_joined = None
    if latest_membership:
        time_diff = now - latest_membership.created_at
        new_member_joined = int(time_diff.total_seconds() // 3600)

    latest_payment = Contribution.objects.filter(
        membership__committee__organizer=request.user,
        payment_status='PAID'
    ).last()
    payment_received = None
    if latest_payment:
        time_diff = now - latest_payment.created_at
        payment_received = int(time_diff.total_seconds() // 3600)

    # Recent members, contributions, and payouts (limit to 5 each)
    recent_members = Membership.objects.filter(
        committee__organizer=request.user
    ).order_by('-created_at')[:5]
    recent_contributions = Contribution.objects.filter(
        membership__committee__organizer=request.user
    ).order_by('-created_at')[:5]
    recent_payouts = Payout.objects.filter(
        membership__committee__organizer=request.user
    ).order_by('-paid_at')[:5]

    # Active memberships for bulk contributions
    active_memberships = Membership.objects.filter(
        committee__organizer=request.user,
        status='ACTIVE'
    )

    # Next contribution date (first day of next month)
    current_month = now.replace(day=1)
    next_contribution_date = (current_month + timedelta(days=32)).replace(day=1)

    return render(request, 'committee/organizer_dashboard.html', {
        'total_committees': total_committees,
        'total_members': total_members,
        'total_contributions': total_contributions,
        'total_payouts': total_payouts,
        'new_committee_created': new_committee_created,
        'new_member_joined': new_member_joined,
        'payment_received': payment_received,
        'recent_members': recent_members,
        'recent_contributions': recent_contributions,
        'recent_payouts': recent_payouts,
        'active_memberships': active_memberships,
        'next_contribution_date': next_contribution_date,
        'current_month': current_month,
        'is_also_member': is_also_member,
        'form_errors': []
    })


@login_required
def see_all_members(request):
    user = request.user
    members = Membership.objects.filter(
        committee__organizer=user, 
        status='ACTIVE'
    ).select_related('member').prefetch_related('member__user_profile').order_by('-joined_at')

    paginator = Paginator(members, 5)
    page_number = request.GET.get('page')
    try:
        members = paginator.page(page_number)
    except PageNotAnInteger:
        members = paginator.page(1)
    except EmptyPage:
        members = paginator.page(paginator.num_pages)

    return render(request, 'committee/see_all_members.html', {
        'members': members,
        'page_obj': members,
    })


@login_required
def manage_contributions(request):
    """View all contributions for organizer's committees"""
    if not request.user.is_organizer:
        messages.error(request, "Only organizers can access this page")
        return redirect('committee:committee_list')

    # Fetch contributions for the organizer's committees with related data
    contributions = Contribution.objects.select_related(
        'membership__member__user_profile',
        'membership__committee'
    ).filter(
        membership__committee__organizer=request.user
    ).order_by('-for_month')

    # Paginate with 5 contributions per page
    paginator = Paginator(contributions, 5)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Pass only the paginated page_obj and memberships for the dropdown (if needed)
    context = {
        'page_obj': page_obj,
        'object_name': 'contributions',
    }
    return render(request, 'committee/manage_contributions.html', context)


@login_required
def manage_payouts(request):
    """View all payouts for organizer's committees"""
    if not request.user.is_organizer:
        messages.error(request, "Only organizers can access this page")
        return redirect('committee:committee_list')

    # Fetch payouts with related data to prevent N+1 queries
    payouts = Payout.objects.select_related(
        'membership__member__user_profile',
        'membership__committee',
        'received_by'
    ).filter(
        membership__committee__organizer=request.user
    ).order_by('-paid_at')

    # Get active memberships for the create payout dropdown
    memberships = Membership.objects.select_related(
        'member__user_profile',
        'committee'
    ).filter(
        committee__organizer=request.user,
        status='ACTIVE'
    )

    return render(request, 'committee/manage_payouts.html', {
        'payouts': payouts,
        'memberships': memberships
    })


@login_required
def bulk_contribution(request):
    """Record contributions for all active members for the current month"""
    if not request.user.is_organizer:
        messages.error(request, "Only organizers can access this page")
        return redirect('committee:organizer_dashboard')

    active_memberships = Membership.objects.filter(
        committee__organizer=request.user,
        status='ACTIVE'
    ).select_related('member', 'committee')

    current_month = timezone.now().date().replace(day=1)
    current_month_display = timezone.now().strftime('%B %Y')

    # Get existing contributions for this month with payment status
    contributions_dict = {}
    contributions = Contribution.objects.filter(
        membership__in=active_memberships,
        for_month__year=current_month.year,
        for_month__month=current_month.month
    ).select_related('membership')

    for contribution in contributions:
        contributions_dict[contribution.membership_id] = contribution

    if request.method == 'POST':
        success_count = 0
        form_errors = []

        for membership in active_memberships:
            if f'membership_{membership.pk}' in request.POST:
                if membership.pk not in contributions_dict:
                    form = ContributionForm(
                        data={
                            'amount_paid': membership.committee.monthly_amount,
                            'for_month': current_month,
                            'payment_status': 'PAID'
                        },
                        request=request,
                        membership=membership
                    )
                    if form.is_valid():
                        form.save()
                        success_count += 1
                    else:
                        for error in form.non_field_errors():
                            form_errors.append(error)
                else:
                    form_errors.append(f"Contribution already exists for {membership.member.full_name} in {membership.committee.name} for this month")

        if success_count > 0:
            messages.success(request, f"Successfully recorded {success_count} contributions for {current_month_display}")
        if form_errors:
            for error in form_errors:
                messages.error(request, error)

        return redirect('committee:organizer_dashboard')

    # Calculate counts for each payment status
    paid_count = sum(1 for c in contributions_dict.values() if c.payment_status == 'PAID')
    pending_count = sum(1 for c in contributions_dict.values() if c.payment_status == 'PENDING')
    late_count = sum(1 for c in contributions_dict.values() if c.payment_status == 'LATE')
    not_recorded_count = active_memberships.count() - len(contributions_dict)

    # GET request - show the form
    context = {
        'active_memberships': active_memberships,
        'current_month': current_month_display,
        'contributions_dict': contributions_dict,
        'current_month_date': current_month,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'late_count': late_count,
        'not_recorded_count': not_recorded_count,
    }
    return render(request, 'committee/bulk_contribution.html', context)


# Member Dashboard Views
@login_required
def member_dashboard(request):
    """Dashboard for members to see their committees, contributions, and payouts."""
    # Allow access to member dashboard regardless of organizer status
    # Users can be both organizers and members

    memberships = Membership.objects.filter(member=request.user, status='ACTIVE').select_related('committee')
    committees = []
    for m in memberships:
        committee = m.committee
        last_contribution = Contribution.objects.filter(membership=m).order_by('-for_month').first()

        if last_contribution:
            next_month_date = last_contribution.for_month + timedelta(days=31)
            next_month_date = next_month_date.replace(day=1)
        else:
            next_month_date = committee.start_date

        day = committee.start_date.day
        last_day_of_month = calendar.monthrange(next_month_date.year, next_month_date.month)[1]
        if day > last_day_of_month:
            day = last_day_of_month

        next_contribution_date = date(next_month_date.year, next_month_date.month, day)

        if next_contribution_date < date.today():
            next_month_date = next_month_date + timedelta(days=31)
            next_month_date = next_month_date.replace(day=1)
            last_day_of_month = calendar.monthrange(next_month_date.year, next_month_date.month)[1]
            if day > last_day_of_month:
                day = last_day_of_month
            next_contribution_date = date(next_month_date.year, next_month_date.month, day)

        committee.next_contribution_date = next_contribution_date
        committees.append(committee)

    my_contributions = Contribution.objects.filter(membership__member=request.user).select_related('membership__committee').order_by('-for_month')
    my_payouts = Payout.objects.filter(membership__member=request.user).select_related('membership__committee').order_by('-paid_at')

    active_committees_count = memberships.count()
    total_contributions_amount = my_contributions.filter(payment_status='PAID').aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_payouts_amount = my_payouts.filter(is_confirmed=True).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    context = {
        'committees': committees,
        'my_contributions': my_contributions,
        'my_payouts': my_payouts,
        'active_committees_count': active_committees_count,
        'total_contributions_amount': total_contributions_amount,
        'total_payouts_amount': total_payouts_amount,
        'page_title': 'Member Dashboard',
    }
    return render(request, 'committee/member_dashboard.html', context)


@login_required
def member_committee_detail(request, pk):
    """Show committee details for a member, including other members, contributions, and payouts."""
    committee = get_object_or_404(Committee, pk=pk)

    # Ensure the user is a member of this committee
    try:
        user_membership = Membership.objects.get(committee=committee, member=request.user, status='ACTIVE')
    except Membership.DoesNotExist:
        messages.error(request, "You are not an active member of this committee.")
        return redirect('committee:member_dashboard')

    # Get all active members of the committee with related data
    all_memberships = Membership.objects.filter(
        committee=committee, 
        status='ACTIVE'
    ).select_related('member').prefetch_related('member__user_profile')

    # Get contributions for the logged-in member
    my_contributions = Contribution.objects.filter(membership=user_membership).order_by('-for_month')

    # Get all payouts for this committee
    payouts = Payout.objects.filter(membership__committee=committee).select_related('membership__member').order_by('-paid_at')

    # Contribution form
    contribution_form = ContributionForm(request=request, membership=user_membership)

    context = {
        'committee': committee,
        'user_membership': user_membership,
        'all_memberships': all_memberships,
        'my_contributions': my_contributions,
        'payouts': payouts,
        'contribution_form': contribution_form,
        'page_title': f"{committee.name} Details",
    }
    return render(request, 'committee/member_committee_detail.html', context)


@login_required
def member_contribution_create(request, membership_pk):
    """Create a contribution for the logged-in member."""
    membership = get_object_or_404(Membership, pk=membership_pk)
    committee = membership.committee

    # Security check: only the member themselves can create a contribution.
    if request.user != membership.member:
        messages.error(request, "You can only submit contributions for yourself.")
        return redirect('committee:member_committee_detail', pk=committee.pk)

    if request.method == 'POST':
        form = ContributionForm(request.POST, membership=membership, request=request)
        if form.is_valid():
            contribution = form.save(commit=False)
            contribution.membership = membership
            # Set default status for member submissions
            contribution.payment_status = 'PENDING'
            contribution.save()
            messages.success(request, 'Your contribution has been submitted for verification.')
            return redirect('committee:member_committee_detail', pk=committee.pk)
    else:
        form = ContributionForm(membership=membership, request=request)

    return render(request, 'committee/member_contribution_form.html', {
        'form': form,
        'membership': membership,
        'committee': committee,
        'title': 'Submit Contribution'
    })


@login_required
@require_POST
def toggle_committee_status(request, pk):
    committee = get_object_or_404(Committee, pk=pk)

    # Verify ownership
    if committee.organizer != request.user:
        messages.error(request, "Permission denied")
        return redirect('committee:committee_detail', pk=committee.pk)

    # Update status by saving (triggers completion check)
    committee.save()

    # Handle after potential status update
    if committee.status == 'COMPLETED':
        messages.error(request, "Cannot modify completed committees")
        return redirect('committee:committee_detail', pk=committee.pk)

    # Toggle status
    if committee.status == 'ACTIVE':
        if committee.deactivate():
            messages.success(request, "Committee deactivated")
        else:
            messages.error(request, "Cannot deactivate at this time")
    elif committee.status == 'DEACTIVATED':
        if committee.reactivate():
            messages.success(request, "Committee reactivated")
        else:
            messages.error(request, "Cannot reactivate completed committees")

    return redirect('committee:committee_detail', pk=committee.pk)
