from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Avg


class UserManager(BaseUserManager):
    """Users sign in with their email address instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("name", "Admin")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """
    App1_Accounts.User
    pk, name, email, password, phone, address, createdAt
    (password is stored hashed by Django's AbstractUser.)
    """

    username = None
    first_name = None
    last_name = None

    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    avatar = models.ImageField("profile picture", upload_to="avatars/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name or self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return (self.name or self.email).split(" ")[0]

    @property
    def initials(self):
        parts = (self.name or self.email).split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def seller_rating(self):
        avg = self.reviews_received.aggregate(avg=Avg("rating"))["avg"]
        return round(avg, 1) if avg else None
