from django.contrib import admin
from .models import Committee, Membership, Contribution, Payout, Invitation

# Register your models here.


class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organizer', 'status', 'start_date', 'end_date', 'total_collected', 'created_at', 'updated_at')   
    search_fields = ('name', 'organizer__email')
    list_filter = ('status', 'start_date', 'end_date')


admin.site.register(Committee, CommitteeAdmin)


class MembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'committee', 'member', 'status', 'joined_at', 'left_at', 'total_contributed', 'created_at', 'updated_at')
    search_fields = ('committee__name', 'member__email')
    list_filter = ('status', 'joined_at', 'left_at')


admin.site.register(Membership, MembershipAdmin)


class ContributionAdmin(admin.ModelAdmin):
    list_display = ('id', 'membership', 'amount_paid', 'for_month', 'due_date', 'payment_date', 'payment_status', 'verified_by_organizer', 'created_at', 'updated_at')
    search_fields = ('membership__committee__name', 'membership__member__email')
    list_filter = ('payment_status', 'verified_by_organizer')


admin.site.register(Contribution, ContributionAdmin)


class PayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'membership', 'total_amount', 'paid_at', 'received_by', 'is_confirmed', 'confirmed_at', 'received_in_cash', 'created_at', 'updated_at')
    search_fields = ('membership__committee__name', 'membership__member__email')
    list_filter = ('is_confirmed', 'received_in_cash')


admin.site.register(Payout, PayoutAdmin)


class InvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'committee', 'invited_by', 'status', 'created_at', 'expires_at')
    search_fields = ('email',)
    list_filter = ('status',)


admin.site.register(Invitation, InvitationAdmin)
