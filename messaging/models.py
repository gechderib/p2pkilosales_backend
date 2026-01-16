from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser
from listings.models import TravelListing


class Conversation(models.Model):
    """
    Conversations are purely between users, not linked to packages or travel listings.
    """
    participants = models.ManyToManyField(CustomUser, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation {self.id} - {self.participants.count()} participants"

    @staticmethod
    def get_or_create_conversation(user1, user2):
        """
        Finds or creates a 1-on-1 conversation between two users.
        """
        from django.db.models import Count
        
        # Look for an existing conversation with exactly these two participants
        conversation = Conversation.objects.annotate(
            num_participants=Count('participants')
        ).filter(
            num_participants=2,
            participants=user1
        ).filter(
            participants=user2
        ).first()

        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(user1, user2)
            return conversation, True
        
        return conversation, False

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} in conversation {self.conversation.id}"


class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.CharField(max_length=255, blank=True, null=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for message {self.message.id} - {self.file_name}"

class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    travel_listing = models.ForeignKey(TravelListing, on_delete=models.CASCADE, null=True, blank=True)
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.email} - {self.message[:30]}"