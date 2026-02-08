from django.conf import settings
from django.db import models


class UserProfile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)
	phone = models.CharField(max_length=30)
	birth_date = models.DateField()
	has_disability = models.BooleanField(default=False)
	disability_type = models.CharField(max_length=120, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Profile for {self.user.username}"


class WebAuthnCredential(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="webauthn_credentials")
	credential_id = models.BinaryField(unique=True)
	public_key = models.BinaryField()
	aaguid = models.BinaryField()
	sign_count = models.IntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"WebAuthn credential for {self.user.username}"


class Reclamation(models.Model):
	CATEGORY_CHOICES = [
		("recommendation", "Recommendation"),
		("alert", "Alert"),
		("reclamation", "Reclamation"),
	]

	name = models.CharField(max_length=120)
	email = models.EmailField()
	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
	message = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.category} from {self.name}"
