# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import uuid

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'STAFF')
        extra_fields.setdefault('staff_role', 'SUPERADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class RadioStation(models.Model):
    """Model for radio stations that use the Newskoop platform"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Content access fields
    access_general = models.BooleanField(default=True, help_text="Access to general content")
    access_christian = models.BooleanField(default=False, help_text="Access to Christian content")
    access_muslim = models.BooleanField(default=False, help_text="Access to Muslim content")
    
    # Language access
    access_english = models.BooleanField(default=True, help_text="Access to English content")
    access_afrikaans = models.BooleanField(default=False, help_text="Access to Afrikaans content")
    access_xhosa = models.BooleanField(default=False, help_text="Access to Xhosa content")
    
    # Content category access
    access_news_stories = models.BooleanField(default=False, help_text="Access to News Stories")
    access_news_bulletins = models.BooleanField(default=False, help_text="Access to News Bulletins")
    access_sport = models.BooleanField(default=False, help_text="Access to Sport content")
    access_finance = models.BooleanField(default=False, help_text="Access to Finance content")
    access_specialty = models.BooleanField(default=False, help_text="Access to Specialty content")
    
    def __str__(self):
        return self.name


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Customized user model for Newskoop platform"""
    
    # User type choices
    class UserType(models.TextChoices):
        STAFF = 'STAFF', 'Newskoop Staff'
        RADIO = 'RADIO', 'Radio Station Staff'
    
    # Staff role choices
    class StaffRole(models.TextChoices):
        SUPERADMIN = 'SUPERADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        EDITOR = 'EDITOR', 'Editor'
        SUB_EDITOR = 'SUB_EDITOR', 'Sub Editor'
        JOURNALIST = 'JOURNALIST', 'Journalist'
        INTERN = 'INTERN', 'Intern'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    mobile_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # New fields for user type and role
    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.STAFF,
    )
    
    # Staff role - only applicable for STAFF user types
    staff_role = models.CharField(
        max_length=20,
        choices=StaffRole.choices,
        blank=True,
        null=True,
    )
    
    # Radio station - only applicable for RADIO user types
    radio_station = models.ForeignKey(
        RadioStation,
        on_delete=models.CASCADE,
        related_name='users',
        blank=True,
        null=True
    )
    
    # Flag to indicate if this user is the primary contact for their radio station
    is_primary_contact = models.BooleanField(default=False)
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        return self.first_name or self.email.split('@')[0]
    
    def save(self, *args, **kwargs):
        # Set is_staff flag based on user_type
        if self.user_type == self.UserType.STAFF:
            self.is_staff = True
        else:
            # Only staff users can be superusers
            self.is_superuser = False
            
            # Only staff users with appropriate roles can have staff status
            if not (self.staff_role in [self.StaffRole.SUPERADMIN, self.StaffRole.ADMIN]):
                self.is_staff = False
        
        # Ensure RADIO users have a radio_station
        if self.user_type == self.UserType.RADIO and not self.radio_station:
            raise ValueError("Radio station users must be associated with a radio station")
            
        super().save(*args, **kwargs)