from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import MessageAttachment
from config.utils import delete_image

@receiver(post_delete, sender=MessageAttachment)
def delete_attachment_from_cloudinary(sender, instance, **kwargs):
    if instance.public_id:
        try:
            delete_image(instance.public_id)
        except Exception as e:
            # Log error but don't fail the deletion
            print(f"Error deleting image from Cloudinary: {e}")
