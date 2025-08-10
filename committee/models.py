from django.db import models
from accounts.models import User
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from datetime import date


class Committee(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('DEACTIVATED', 'Deactivated'),
        ('COMPLETED', 'Completed'),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    monthly_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Exact amount each member must contribute monthly (no partial payments).")
    duration_months = models.PositiveIntegerField()
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_committees')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + relativedelta(months=self.duration_months)
        # Automatically complete only if ACTIVE and end_date passed
        if self.status == 'ACTIVE' and self.end_date and self.end_date < date.today():
            self.status = 'COMPLETED'

        super().save(*args, **kwargs)

    def deactivate(self):
        """Deactivate only if active and not completed"""
        if self.status == 'ACTIVE' and not self.is_completed:
            self.status = 'DEACTIVATED'  # Fixed to match STATUS_CHOICES
            self.save()
            return True
        return False

    def reactivate(self):
        """Reactivate only if deactivated and not completed"""
        if self.status == 'DEACTIVATED' and not self.is_completed:  # Fixed status check
            self.status = 'ACTIVE'
            self.save()
            return True
        return False

    @property
    def is_completed(self):
        return self.end_date and self.end_date < date.today()

    @property
    def total_collected(self):
        return Contribution.objects.filter(
            membership__committee=self,
            payment_status='PAID'
        ).aggregate(total=models.Sum('amount_paid'))['total'] or 0


class Membership(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('LEFT', 'Left'),
        ('REMOVED', 'Removed'),
    ]
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='memberships')
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='committees_joined')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('committee', 'member')
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.member.full_name} - {self.committee.name}"

    def save(self, *args, **kwargs):
        if self.status in ['LEFT', 'REMOVED'] and not self.left_at:
            self.left_at = timezone.now()
        elif self.status == 'ACTIVE':
            self.left_at = None
        super().save(*args, **kwargs)

    @property
    def total_contributed(self):
        return self.contributions.filter(payment_status='PAID').aggregate(
            total=models.Sum('amount_paid')
        )['total'] or 0


class Contribution(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('LATE', 'Late'),
    ]
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='contributions')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    for_month = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    verified_by_organizer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('membership', 'for_month')
        ordering = ['for_month']

    def __str__(self):
        return f"{self.membership.member.full_name} paid {self.amount_paid} for {self.for_month}"

    def clean(self):
        if self.payment_date and self.due_date:
            self.payment_status = 'LATE' if self.payment_date > self.due_date else 'PAID'

    def save(self, *args, **kwargs):
        if not self.due_date and self.for_month:
            self.due_date = date(self.for_month.year, self.for_month.month, 5)
        self.clean()
        super().save(*args, **kwargs)

    def get_status_class(self):
        if self.payment_status == 'PAID':
            return 'bg-green-100 text-green-800'
        elif self.payment_status == 'PENDING':
            return 'bg-yellow-100 text-yellow-800'
        elif self.payment_status == 'LATE':
            return 'bg-red-100 text-red-800'
        return 'bg-gray-100 text-gray-800'


class Payout(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='payouts')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payouts_received')
    is_confirmed = models.BooleanField(default=False)
    received_in_cash = models.BooleanField(default=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('membership',)

    def __str__(self):
        return f"{self.membership.member.full_name} received {self.total_amount} from {self.membership.committee.name}"

    def get_status_display(self):
        return "Confirmed" if self.is_confirmed else "Pending"

    def get_status_class(self):
        if self.is_confirmed:
            return 'bg-green-100 text-green-800'
        return 'bg-yellow-100 text-yellow-800'


# class Invitation(models.Model):
#     STATUS_CHOICES = [
#         ('PENDING', 'Pending'),
#         ('ACCEPTED', 'Accepted'),
#         ('EXPIRED', 'Expired'),
#     ]

#     committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='invitations')
#     invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitations_sent')
#     email = models.EmailField()
#     token = models.CharField(max_length=100, unique=True)
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Invitation to {self.email} for {self.committee.name}"
