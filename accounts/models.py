from django.db import models
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager, PermissionsMixin)
# Create your models here.


class UserManager(BaseUserManager):
    def create_user(self, email, password=None):
        if not email:
            raise ValueError('Users must have an email address')
        if not password:
            raise ValueError('Users must have a password')
        user = self.model(
            email=self.normalize_email(email),
        )
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password):
        if password is None:
            raise TypeError("User must have a password")
        user = self.create_user(email, password=password)
        user.save()

        user.is_superuser = True
        user.is_staff = True
        user.is_verified = True
        user.is_approved = True
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True, max_length=255, blank=False)
    phone = models.CharField(max_length=120, blank=True)
    is_organizer = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return self.first_name + " " + self.last_name

    @property
    def profile(self):
        try:
            return self.user_profile
        except Profile.DoesNotExist:
            return Profile.objects.create(user=self)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} Profile"


class Contact(models.Model):
    CONTACT_TYPES = [
        ('general', 'General Inquiry'),
        ('support', 'Technical Support'),
        ('business', 'Business Inquiry'),
        ('newsletter', 'Newsletter Subscription'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES, default='general')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_replied = models.BooleanField(default=False)
    admin_reply = models.TextField(blank=True, help_text="Admin's reply to this contact message")
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contact_replies')
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"

    @property
    def status(self):
        """Return the current status of the contact"""
        if self.is_replied:
            return "Replied"
        elif self.is_read:
            return "Read"
        else:
            return "New"

    @property
    def priority_class(self):
        """Return CSS class based on contact type for styling"""
        priority_map = {
            'support': 'text-red-600 bg-red-50',
            'business': 'text-purple-600 bg-purple-50',
            'general': 'text-blue-600 bg-blue-50',
            'newsletter': 'text-green-600 bg-green-50',
        }
        return priority_map.get(self.contact_type, 'text-gray-600 bg-gray-50')
