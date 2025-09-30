from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, Profile, Contact

# Register your models here.


class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'first_name', 'last_name', 'phone', 'is_organizer', 'is_approved', 'is_superuser', 'is_verified', 'is_staff', 'is_active', 'created_at', 'updated_at')
    list_filter = ('email', 'first_name', 'last_name', 'phone', 'is_organizer', 'is_approved', 'is_superuser', 'is_verified', 'is_staff', 'is_active', 'created_at', 'updated_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone')


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'bio', 'location', 'birth_date', 'profile_picture')
    list_filter = ('user', 'bio', 'location', 'birth_date', 'profile_picture')
    search_fields = ('user', 'bio', 'location', 'birth_date', 'profile_picture')


class ContactAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'email', 'contact_type', 'subject', 
        'status_badge', 'priority_badge', 'created_at', 'action_buttons'
    )
    list_filter = (
        'contact_type', 'is_read', 'is_replied', 'created_at', 'updated_at'
    )
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at', 'updated_at', 'replied_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'contact_type')
        }),
        ('Message Details', {
            'fields': ('subject', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'is_replied')
        }),
        ('Admin Reply', {
            'fields': ('admin_reply', 'replied_by', 'replied_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        """Display status with color coding"""
        if obj.is_replied:
            return format_html(
                '<span style="background-color: #d4edda; color: #155724; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">✓ REPLIED</span>'
            )
        elif obj.is_read:
            return format_html(
                '<span style="background-color: #fff3cd; color: #856404; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">👁 READ</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #cce5ff; color: #004085; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">✉ NEW</span>'
            )
    status_badge.short_description = 'Status'

    def priority_badge(self, obj):
        """Display contact type with color coding"""
        colors = {
            'support': '#dc3545',
            'business': '#6f42c1', 
            'general': '#007bff',
            'newsletter': '#28a745'
        }
        color = colors.get(obj.contact_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_contact_type_display().upper()
        )
    priority_badge.short_description = 'Type'

    def action_buttons(self, obj):
        """Display action buttons"""
        buttons = []

        # View/Reply button
        view_url = reverse('admin_contact_detail', args=[obj.id])
        buttons.append(
            format_html(
                '<a href="{}" style="background-color: #007bff; color: white; padding: 2px 8px; text-decoration: none; border-radius: 3px; font-size: 11px; margin-right: 5px;">VIEW</a>',
                view_url
            )
        )

        # Mark as read button (if not read)
        if not obj.is_read:
            read_url = reverse('admin_contact_mark_read', args=[obj.id])
            buttons.append(
                format_html(
                    '<a href="{}" style="background-color: #28a745; color: white; padding: 2px 8px; text-decoration: none; border-radius: 3px; font-size: 11px; margin-right: 5px;">READ</a>',
                    read_url
                )
            )

        # Email button
        buttons.append(
            format_html(
                '<a href="mailto:{}?subject=Re: {}" style="background-color: #17a2b8; color: white; padding: 2px 8px; text-decoration: none; border-radius: 3px; font-size: 11px;">EMAIL</a>',
                obj.email,
                obj.subject
            )
        )

        return mark_safe(''.join(buttons))
    action_buttons.short_description = 'Actions'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('replied_by')

    actions = ['mark_as_read', 'mark_as_replied']

    def mark_as_read(self, request, queryset):
        """Bulk action to mark contacts as read"""
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} contacts marked as read.')
    mark_as_read.short_description = "Mark selected contacts as read"

    def mark_as_replied(self, request, queryset):
        """Bulk action to mark contacts as replied"""
        updated = queryset.update(is_replied=True)
        self.message_user(request, f'{updated} contacts marked as replied.')
    mark_as_replied.short_description = "Mark selected contacts as replied"


admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Contact, ContactAdmin)
