from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from .models import Conversation, Message, MessageAttachment, Notification
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageAttachmentSerializer, NotificationSerializer
)
from .utils import send_message_to_conversation
from config.views import StandardResponseViewSet
from .permissions import IsMessageOwner
from config.utils import standard_response
from django.utils import timezone
import datetime

# Create your views here.

@extend_schema(tags=['Messaging'])
class ConversationViewSet(StandardResponseViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(participants=user).distinct()


    def get_serializer_class(self):
        if self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        # This viewset is used for manual conversation creation between users.
        conversation = serializer.save()

    @extend_schema(tags=['Messaging'], description="Get all messages in a conversation")
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        messages = conversation.messages.all().order_by('-created_at')  # Latest first
        
        # Optional filtering
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read_bool = is_read.lower() in ['true', '1', 'yes']
            messages = messages.filter(is_read=is_read_bool)
        
        # Optional sender filter
        sender_id = request.query_params.get('sender_id')
        if sender_id:
            messages = messages.filter(sender_id=sender_id)
        
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @extend_schema(tags=['Messaging'], description="Send a message in a conversation")
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        conversation = self.get_object()
        serializer = MessageSerializer(data=request.data)
        
        if serializer.is_valid():
            message = serializer.save(
                conversation=conversation,
                sender=request.user
            )
            
            # Send message through WebSocket
            message_data = MessageSerializer(message).data
            send_message_to_conversation(conversation.id, message_data)

            # Send notification to other participants
            from .utils import send_notification_to_user
            for participant in conversation.participants.all():
                if participant != request.user:
                    notification = Notification.objects.create(
                        user=participant,
                        conversation=conversation,
                        message=f"New message from {request.user.username}: {message.content[:30]}..."
                    )
                    notification_data = NotificationSerializer(notification).data
                    send_notification_to_user(participant.id, notification_data)
            
            return Response(message_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @extend_schema(tags=['Messaging'], description="Get unread message count for all conversations")
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        user = request.user
        conversations = self.get_queryset()
        
        unread_counts = {}
        for conversation in conversations:
            unread_counts[conversation.id] = conversation.messages.filter(
                is_read=False
            ).exclude(
                sender=user
            ).count()
        
        return Response(unread_counts)

@extend_schema(tags=['Messaging'])
class MessageViewSet(StandardResponseViewSet):
    """
    API endpoint for messages
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(conversation__participants=user).distinct().order_by('-created_at')

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsMessageOwner()]
        return [permissions.IsAuthenticated()]

    @extend_schema(tags=['Messaging'], description="Mark a message as read (and all previous messages in the conversation)")
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        
        # Mark this message and all previous messages in this conversation as read
        updated_count = Message.objects.filter(
            conversation=message.conversation,
            id__lte=message.id
        ).exclude(sender=request.user).update(is_read=True)
        
        # Broadcast via WebSocket
        broadcast_messages_read(message.conversation.id, request.user.id, message.id)
        
        return standard_response(
            data={'updated_count': updated_count, 'last_message_id': message.id},
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.created_at < timezone.now() - datetime.timedelta(days=1):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["Messages older than 24 hours cannot be updated."]
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.created_at < timezone.now() - datetime.timedelta(days=1):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["Messages older than 24 hours cannot be updated."]
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.created_at < timezone.now() - datetime.timedelta(days=1):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["Messages older than 24 hours cannot be deleted."]
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(tags=['Messaging'])
class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MessageAttachment.objects.filter(message__conversation__participants=user).distinct()

    def perform_create(self, serializer):
        message_id = self.request.data.get('message')
        user = self.request.user
        
        # Check if user has access to the message
        message = get_object_or_404(
            Message.objects.filter(conversation__participants=user),
            id=message_id
        )
        attachment = serializer.save(message=message)
        
        # Send updated message through WebSocket
        message_data = MessageSerializer(message).data
        send_message_to_conversation(message.conversation.id, message_data)

@extend_schema(tags=['Messaging'])
class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(tags=['Messaging'], description="Mark a notification as read")
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response(self.get_serializer(notification).data)

    @extend_schema(tags=['Messaging'], description="Mark all notifications as read")
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)
        return Response({'status': 'all marked as read'})