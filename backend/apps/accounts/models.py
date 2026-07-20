from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.OWNER)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Three tiers, not two — `role` and `is_superuser` are deliberately
    separate axes:
      - is_superuser=True: developer/system access (Django admin). Never
        created through the portal, never listed there either — see
        apps/portal/user_views.py, which filters on is_superuser=False.
      - role=OWNER: the business admin tier. Full portal access, including
        managing other users. Doesn't require is_superuser.
      - role=ATTENDANT: desktop POS only. Rejected at the portal login view
        (apps/portal/auth_views.py) — this role has no portal use.
    A single owner-only login was CLAUDE.md's original launch scope; staff
    accounts are the intentional next step the `role` field was always
    modeled to support without a redesign.
    """

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        ATTENDANT = 'ATTENDANT', 'Attendant'

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
