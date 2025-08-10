from django.urls import path
from .views import (
    committee_list,
    committee_detail,
    committee_create,
    committee_update,
    committee_delete,
    membership_list,
    membership_create,
    membership_update,
    membership_delete,
    contribution_create,
    contribution_update,
    contribution_delete,
    contribution_verify,
    payout_create,
    payout_update,
    payout_delete,
    organizer_dashboard,
    member_dashboard,
    member_committee_detail,
    member_contribution_create,
    see_all_members,
    toggle_committee_status,
    manage_contributions,
    manage_payouts,
    bulk_contribution,
)
app_name = 'committee'

urlpatterns = [
    # Committee URLs
    path('committees/', committee_list, name='committee_list'),
    path('committee/<int:pk>/', committee_detail, name='committee_detail'),
    path('committee/create/', committee_create, name='committee_create'),
    path('committee/<int:pk>/update/', committee_update, name='committee_update'),
    path('committee/<int:pk>/delete/', committee_delete, name='committee_delete'),

    # Membership URLs
    path('committee/<int:pk>/members/', membership_list, name='membership_list'),
    path('committee/<int:committee_pk>/members/add/', membership_create, name='membership_create'),
    path('committee/memberships/<int:pk>/update/', membership_update, name='membership_update'),
    path('committee/memberships/<int:pk>/delete/', membership_delete, name='membership_delete'),

    # Contribution URLs
    path('memberships/<int:membership_pk>/contributions/add/', contribution_create, name='contribution_create'),
    path('memberships/<int:pk>/update/', contribution_update, name='contribution_update'),
    path('memberships/<int:pk>/delete/', contribution_delete, name='contribution_delete'),
    path('memberships/<int:pk>/verify/', contribution_verify, name='contribution_verify'),

    # Payout URLs
    path('memberships/<int:membership_pk>/payouts/add/', payout_create, name='payout_create'),
    path('payouts/<int:pk>/update/', payout_update, name='payout_update'),
    path('payouts/<int:pk>/delete/', payout_delete, name='payout_delete'),

    # Organizer Dashboard URLs
    path('organizer-dashboard/', organizer_dashboard, name='organizer_dashboard'),
    path('see-all-members/', see_all_members, name='see_all_members'),
    path('committee/<int:pk>/toggle-status/', toggle_committee_status, name='toggle_status'),
    path('contributions/', manage_contributions, name='manage_contributions'),
    path('payouts/', manage_payouts, name='manage_payouts'),
    path('contributions/bulk/', bulk_contribution, name='bulk_contribution'),

    # Member Dashboard URLs
    path('member-dashboard/', member_dashboard, name='member_dashboard'),
    path('member/committee/<int:pk>/', member_committee_detail, name='member_committee_detail'),
    path('member/contributions/<int:membership_pk>/add/', member_contribution_create, name='member_contribution_create'),

]