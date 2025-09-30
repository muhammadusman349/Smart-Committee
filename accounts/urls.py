from django.urls import path
from .views import (
    profile_view,
    home,
    financial_tracking,
    member_management,
    reporting_analytics,
    security_compliance,
    features,
    privacy_policy,
    terms_of_service,
    contact,
    newsletter_signup,
    admin_contacts_list,
    admin_contact_detail,
    admin_contact_mark_read,
    admin_contact_delete
)

urlpatterns = [
    path('', home, name='home'),
    path('profile/', profile_view, name='profile'),

    # Service Pages
    path('services/financial-tracking/', financial_tracking, name='financial_tracking'),
    path('services/member-management/', member_management, name='member_management'),
    path('services/reporting-analytics/', reporting_analytics, name='reporting_analytics'),
    path('services/security-compliance/', security_compliance, name='security_compliance'),

    # Features Page
    path('features/', features, name='features'),

    # Legal Pages
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-of-service/', terms_of_service, name='terms_of_service'),

    # Contact Pages
    path('contact/', contact, name='contact'),
    path('newsletter-signup/', newsletter_signup, name='newsletter_signup'),

    # Admin Contact Management
    path('admin/contacts/', admin_contacts_list, name='admin_contacts_list'),
    path('admin/contacts/<int:contact_id>/', admin_contact_detail, name='admin_contact_detail'),
    path('admin/contacts/<int:contact_id>/mark-read/', admin_contact_mark_read, name='admin_contact_mark_read'),
    path('admin/contacts/<int:contact_id>/delete/', admin_contact_delete, name='admin_contact_delete'),
]
