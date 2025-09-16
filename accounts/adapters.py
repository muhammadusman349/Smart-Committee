from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.utils import timezone


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        # Call the parent class's save_user method
        user = super().save_user(request, user, form, commit=False)

        # Check if user is signing up through an invitation link
        from committee.models import Invitation, Membership
        pending_invitations = Invitation.objects.filter(
            email__iexact=user.email,
            status='PENDING'
        )

        if pending_invitations.exists():
            # Invited users start as members (not organizers)
            user.is_organizer = False
            if commit:
                user.save()
                # Auto-accept all pending invitations for this email
                for invitation in pending_invitations:
                    # Create membership
                    Membership.objects.get_or_create(
                        committee=invitation.committee,
                        member=user,
                        defaults={'status': 'ACTIVE'}
                    )
                    # Mark invitation as accepted and expire the token
                    invitation.status = 'ACCEPTED'
                    invitation.expires_at = timezone.now()  # Immediately expire the token
                    invitation.save()
                    # Add success message
                    messages.success(
                        request,
                        f"Welcome! You've successfully joined the committee '{invitation.committee.name}'."
                    )
        else:
            # Regular signups rely on model default (is_organizer=True)
            if commit:
                user.save()
        return user
