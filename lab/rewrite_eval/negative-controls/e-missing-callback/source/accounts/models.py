from django.db import models


class Account(models.Model):
    email = models.EmailField(unique=True)


class Profile(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE)
    bio = models.TextField(default="")
