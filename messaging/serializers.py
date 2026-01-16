from rest_framework import serializers
from .models import Conversation, Message, MessageAttachment, Notification
from users.serializers import UserProfileSerializer
from config.utils import upload_image
class MessageAttachmentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    class Meta:
        model = MessageAttachment
        fields = ('id', 'file', 'file_name', 'file_url', 'file_type', 'created_at')
        read_only_fields = ('file_name', 'file_url', 'file_type', 'created_at')
    
    def create(self, validated_data):
        file = validated_data.pop('file', None)
        # Set file_name and file_type automatically from the uploaded file
        if file:
            validated_data['file_name'] = file.name
            validated_data['file_type'] = getattr(file, 'content_type', '')
        instance = MessageAttachment.objects.create(**validated_data)

        if file:
            file_url = upload_image(file, public_id=f'message_attachments/{instance.message.id}/{file.name}')
            instance.file_url = file_url
            instance.save()
        return instance
    
    def update(self, instance, validated_data):
        file = validated_data.pop('file', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if file:
            instance.file_name = file.name
            instance.file_type = getattr(file, 'content_type', '')
            file_url = upload_image(file, public_id=f'message_attachments/{instance.message.id}/{file.name}')
            instance.file_url = file_url
        
        instance.save()
        return instance
    
class MessageSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'content', 'is_read',
                 'created_at', 'attachments', 'uploaded_files')
        read_only_fields = ('created_at', 'is_read', 'conversation')

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        content = validated_data.get('content', '')

        # if their is no uploaded_files the content is requred field
        if len(uploaded_files) == 0 and not content:
            raise serializers.ValidationError(
                "content is requered if you didn't provide a file"
            )

        message = Message.objects.create(**validated_data)            
        
        # Handle file attachments
        for file in uploaded_files:
            file_url = upload_image(file, public_id=f'message_attachments/{message.id}/{file.name}')
            MessageAttachment.objects.create(
                message=message,
                # file=file,
                file_url=file_url,
                file_name=file.name,
                file_type=file.content_type
            )
        
        return message
    
    def update(self, instance, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle file attachments
        if uploaded_files:
            for file in uploaded_files:
                file_url = upload_image(file, public_id=f'message_attachments/{instance.id}/{file.name}')
                MessageAttachment.objects.create(
                    message=instance,
                    # file=file,
                    file_url=file_url,
                    file_name=file.name,
                    file_type=file.content_type
                )
        
        instance.save()
        return instance

class ConversationSerializer(serializers.ModelSerializer):
    participants = UserProfileSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'participants', 'created_at', 'updated_at', 'last_message', 'unread_count')
        read_only_fields = ('created_at', 'updated_at')

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return MessageSerializer(last_message).data
        return None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.filter(is_read=False).exclude(sender=user).count()

class ConversationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a conversation between users.
    Conversations are purely user-to-user, not linked to packages or travel listings.
    """
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    travel_listing_id = serializers.IntegerField(write_only=True, required=False)
    package_request_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Conversation
        fields = ('participant_ids', 'travel_listing_id', 'package_request_id')

    def validate(self, data):
        request_user = self.context['request'].user
        participant_ids = data.get('participant_ids')
        travel_listing_id = data.get('travel_listing_id')
        package_request_id = data.get('package_request_id')

        if not any([participant_ids, travel_listing_id, package_request_id]):
            raise serializers.ValidationError(
                "One of participant_ids, travel_listing_id, or package_request_id is required."
            )

        other_user = None

        if participant_ids:
            # Filter out the request user from the list if present
            other_ids = [pid for pid in participant_ids if pid != request_user.id]
            
            if len(other_ids) != 1:
                raise serializers.ValidationError("Currently, conversations must be between exactly two users (you and one other).")
            
            participant_id = other_ids[0]
            
            from users.models import CustomUser
            try:
                other_user = CustomUser.objects.get(id=participant_id)
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError(f"User with id {participant_id} does not exist.")

        elif travel_listing_id:
            from listings.models import TravelListing
            try:
                listing = TravelListing.objects.get(id=travel_listing_id)
                other_user = listing.user
            except TravelListing.DoesNotExist:
                raise serializers.ValidationError("TravelListing with provided id does not exist.")

        elif package_request_id:
            from listings.models import PackageRequest
            try:
                pkg_request = PackageRequest.objects.get(id=package_request_id)
                # If request user is the package request creator, other user is listing owner
                if pkg_request.user == request_user:
                    other_user = pkg_request.travel_listing.user
                # If request user is the listing owner, other user is package request creator
                elif pkg_request.travel_listing.user == request_user:
                    other_user = pkg_request.user
                else:
                    raise serializers.ValidationError(
                        "You are not a participant in this package request."
                    )
            except PackageRequest.DoesNotExist:
                raise serializers.ValidationError("PackageRequest with provided id does not exist.")

        if request_user == other_user:
            raise serializers.ValidationError("You cannot create a conversation with yourself.")

        # Store the resolved other_user in validated_data for create method
        data['other_user'] = other_user
        return data

    def create(self, validated_data):
        request_user = self.context['request'].user
        other_user = validated_data['other_user']
        conversation, created = Conversation.get_or_create_conversation(request_user, other_user)
        return conversation

    def to_representation(self, instance):
        return ConversationSerializer(instance, context=self.context).data

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'user', 'travel_listing', 'conversation', 'message', 'is_read', 'created_at')
        read_only_fields = ('created_at',) 