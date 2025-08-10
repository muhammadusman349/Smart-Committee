from django import forms
from django.utils import timezone
from django.db.models import Sum
from .models import Committee, Membership, Contribution, Payout
from accounts.models import User


class MembershipForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        committee = cleaned_data.get('committee')
        member = cleaned_data.get('member')
        status = cleaned_data.get('status')

        # Security: Verify current user owns the committee
        if committee and committee.organizer != self.request.user:
            raise forms.ValidationError("You don't have permission to modify this committee's memberships.")

        # Check for duplicate active memberships
        if self.instance is None and committee and member and status == 'ACTIVE':
            if Membership.objects.filter(committee=committee, member=member, status='ACTIVE').exists():
                raise forms.ValidationError("This member is already active in the committee.")
        # Prevent organizer from adding themselves
        if member and committee and member == committee.organizer:
            raise forms.ValidationError("You cannot add yourself as a member to your own committee.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Auto-set left_at when status changes to LEFT/REMOVED
        if 'status' in self.changed_data and instance.status in ('LEFT', 'REMOVED'):
            instance.left_at = timezone.now()

        if commit:
            instance.save()
        return instance


class CommitteeForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

    class Meta:
        model = Committee
        fields = ['name', 'description', 'monthly_amount', 'duration_months', 'start_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'monthly_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration_months': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        # Security: Ensure the user is an organizer
        if not self.request.user.is_organizer:
            raise forms.ValidationError("You must be an organizer to create or edit a committee.")

        # If updating, ensure the user owns the committee
        if self.instance and self.instance.pk and self.instance.organizer != self.request.user:
            raise forms.ValidationError("You don't have permission to edit this committee.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.organizer = self.request.user
        if commit:
            instance.save()
        return instance


class ContributionForm(forms.ModelForm):
    for_month = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

    class Meta:
        model = Contribution
        fields = ['amount_paid', 'for_month']
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.membership = kwargs.pop('membership', None)
        super().__init__(*args, **kwargs)
        self.fields['amount_paid'].initial = self.membership.committee.monthly_amount

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get('amount_paid')
        required_amount = self.membership.committee.monthly_amount
        if amount_paid != required_amount:
            raise forms.ValidationError(
                f"Amount must be exactly {required_amount} (no partial or over payments)."
            )
        return amount_paid

    def clean(self):
        cleaned_data = super().clean()

        # Security: Verify user has permission
        is_organizer = self.request.user.is_organizer
        is_member = self.membership.member == self.request.user
        if not (is_organizer or is_member):
            raise forms.ValidationError("You don't have permission to create contributions for this membership.")

        # Prevent duplicate contributions for the same month
        for_month = cleaned_data.get('for_month')
        if for_month and Contribution.objects.filter(
            membership=self.membership,
            for_month__month=for_month.month,
            for_month__year=for_month.year
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError("A contribution for this month already exists.")

        for_month = cleaned_data.get('for_month')
        if for_month and for_month > timezone.now().date():
            raise forms.ValidationError("You cannot add a contribution for a future month.")

        # payment_date = cleaned_data.get('payment_date')
        # if for_month < payment_date:
        #     raise forms.ValidationError("for_month must be before payment_date.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.membership = self.membership

        # Set default payment date
        if not instance.payment_date:
            instance.payment_date = timezone.now().date()

        if instance.payment_date:
            if instance.due_date and instance.payment_date > instance.due_date:
                instance.payment_status = 'LATE'
            else:
                instance.payment_status = 'PAID'
        else:
            instance.payment_status = 'PENDING'

        # Auto-verify if paid and organizer is submitting
        if instance.payment_status in ('PAID', 'LATE') and self.request.user.is_organizer:
            instance.verified_by_organizer = True

        if commit:
            instance.save()
        return instance


class PayoutForm(forms.ModelForm):
    class Meta:
        model = Payout
        fields = ['total_amount', 'received_by', 'received_in_cash', 'is_confirmed']
        widgets = {
            'total_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'required': True
            }),
            'received_by': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'received_in_cash': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_confirmed': forms.HiddenInput()
        }
        labels = {
            'total_amount': 'Amount',
            'received_by': 'Received By',
            'received_in_cash': 'Received in Cash?',
            'is_confirmed': 'Confirmed'
        }
        help_texts = {
            'total_amount': 'Enter the total amount to be paid out',
            'received_in_cash': 'Check if payment was received in cash',
            'is_confirmed': 'Mark as confirmed (only for organizers)'
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.membership = kwargs.pop('membership', None)
        super().__init__(*args, **kwargs)

        # Set initial values
        if self.membership:
            committee = self.membership.committee
            # Calculate total amount based on contributions
            total_contributions = self.membership.contributions.aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            self.fields['total_amount'].initial = total_contributions

            # Set default received_by to the member if they are still active
            if self.membership.status == 'ACTIVE':
                self.fields['received_by'].initial = self.membership.member

            # Limit 'received_by' to members of the same committee
            self.fields['received_by'].queryset = User.objects.filter(
                committees_joined__committee=committee,
                committees_joined__status='ACTIVE'
            ).distinct()

    def clean_total_amount(self):
        total_amount = self.cleaned_data.get('total_amount')
        total_verified = self.membership.contributions.filter(
            payment_status__in=['PAID', 'LATE'],
            verified_by_organizer=True
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        if total_amount > total_verified:
            raise forms.ValidationError(
                f"Amount cannot exceed total verified contributions ({total_verified})."
            )
        return total_amount

    def clean(self):
        cleaned_data = super().clean()

        # Security: Only committee organizer can create payouts
        if self.membership.committee.organizer != self.request.user:
            raise forms.ValidationError("You don't have permission to create payouts for this committee.")

        # Prevent duplicate payouts
        if not self.instance.pk and Payout.objects.filter(membership=self.membership).exists():
            raise forms.ValidationError("A payout for this membership already exists.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.membership = self.membership
        instance.paid_by = self.request.user

        # Auto-set paid_at and confirmed_at
        if instance.pk and not instance.paid_at:
            instance.paid_at = timezone.now()

        if instance.is_confirmed and not instance.confirmed_at:
            instance.confirmed_at = timezone.now()

        if commit:
            instance.save()
        return instance
