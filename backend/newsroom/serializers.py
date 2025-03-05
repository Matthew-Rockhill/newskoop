# newsroom/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Category, Story, StoryContent, AudioClip, 
    Bulletin, BulletinStory, Show, Task, TaskNote
)

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories"""
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'parent_name',
            'is_news_story', 'is_news_bulletin', 'is_sport', 'is_finance', 'is_specialty',
            'children_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_children_count(self, obj):
        return obj.children.count()


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for hierarchical category display"""
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'children']
    
    def get_children(self, obj):
        children = obj.children.all()
        if not children:
            return []
        return CategoryTreeSerializer(children, many=True).data


class AudioClipSerializer(serializers.ModelSerializer):
    """Serializer for audio clips"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioClip
        fields = [
            'id', 'title', 'description', 'file', 'file_url',
            'duration', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_file_url(self, obj):
        if obj.file:
            return self.context['request'].build_absolute_uri(obj.file.url)
        return None


class StoryContentSerializer(serializers.ModelSerializer):
    """Serializer for story content"""
    class Meta:
        model = StoryContent
        fields = ['id', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class StoryListSerializer(serializers.ModelSerializer):
    """Serializer for listing stories"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    categories_display = serializers.SerializerMethodField()
    audio_count = serializers.SerializerMethodField()
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    
    class Meta:
        model = Story
        fields = [
            'id', 'title', 'author', 'author_name', 'categories_display',
            'status', 'language', 'language_display', 'audio_count',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at']
    
    def get_categories_display(self, obj):
        return [category.name for category in obj.categories.all()]
    
    def get_audio_count(self, obj):
        return obj.audio_clips.count()


class StoryDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed story view"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    content = StoryContentSerializer(required=False)
    audio_clips = AudioClipSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        many=True, 
        write_only=True,
        source='categories',
        required=False
    )
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    translations = StoryListSerializer(many=True, read_only=True)
    
    class Meta:
        model = Story
        fields = [
            'id', 'title', 'author', 'author_name', 
            'content', 'audio_clips', 'categories', 'category_ids',
            'status', 'status_display', 'language', 'language_display',
            'original_story', 'translations', 'word_count',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at', 'word_count']
    
    def create(self, validated_data):
        content_data = validated_data.pop('content', None)
        categories_data = validated_data.pop('categories', [])
        
        # Create the story
        story = Story.objects.create(**validated_data)
        
        # Add categories
        if categories_data:
            story.categories.set(categories_data)
        
        # Create content if provided
        if content_data:
            StoryContent.objects.create(story=story, **content_data)
        else:
            # Create empty content
            StoryContent.objects.create(story=story, content="")
        
        return story
    
    def update(self, instance, validated_data):
        content_data = validated_data.pop('content', None)
        categories_data = validated_data.pop('categories', None)
        
        # Update story fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update categories if provided
        if categories_data is not None:
            instance.categories.set(categories_data)
        
        # Update content if provided
        if content_data:
            content, created = StoryContent.objects.get_or_create(story=instance)
            content.content = content_data.get('content', content.content)
            content.save()
        
        return instance


class BulletinStorySerializer(serializers.ModelSerializer):
    """Serializer for stories in bulletins"""
    story_detail = StoryListSerializer(source='story', read_only=True)
    
    class Meta:
        model = BulletinStory
        fields = ['id', 'story', 'story_detail', 'order']
        read_only_fields = ['id']


class BulletinListSerializer(serializers.ModelSerializer):
    """Serializer for listing bulletins"""
    editor_name = serializers.CharField(source='editor.get_full_name', read_only=True)
    categories_display = serializers.SerializerMethodField()
    story_count = serializers.SerializerMethodField()
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    
    class Meta:
        model = Bulletin
        fields = [
            'id', 'title', 'editor', 'editor_name', 'categories_display',
            'status', 'language', 'language_display', 'story_count',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at']
    
    def get_categories_display(self, obj):
        return [category.name for category in obj.categories.all()]
    
    def get_story_count(self, obj):
        return obj.bulletin_stories.count()


class BulletinDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed bulletin view"""
    editor_name = serializers.CharField(source='editor.get_full_name', read_only=True)
    bulletin_stories = BulletinStorySerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        many=True, 
        write_only=True,
        source='categories',
        required=False
    )
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    translations = BulletinListSerializer(many=True, read_only=True)
    story_order = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Bulletin
        fields = [
            'id', 'title', 'editor', 'editor_name', 
            'intro', 'outro', 'bulletin_stories', 'story_order',
            'categories', 'category_ids',
            'status', 'status_display', 'language', 'language_display',
            'original_bulletin', 'translations',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at']
    
    def create(self, validated_data):
        categories_data = validated_data.pop('categories', [])
        story_order = validated_data.pop('story_order', [])
        
        # Create the bulletin
        bulletin = Bulletin.objects.create(**validated_data)
        
        # Add categories
        if categories_data:
            bulletin.categories.set(categories_data)
        
        # Add stories in order
        for index, story_id in enumerate(story_order):
            try:
                story = Story.objects.get(id=story_id)
                BulletinStory.objects.create(
                    bulletin=bulletin,
                    story=story,
                    order=index
                )
            except Story.DoesNotExist:
                continue
        
        return bulletin
    
    def update(self, instance, validated_data):
        categories_data = validated_data.pop('categories', None)
        story_order = validated_data.pop('story_order', None)
        
        # Update bulletin fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update categories if provided
        if categories_data is not None:
            instance.categories.set(categories_data)
        
        # Update stories if provided
        if story_order is not None:
            # Clear existing bulletin stories
            instance.bulletin_stories.all().delete()
            
            # Add new order
            for index, story_id in enumerate(story_order):
                try:
                    story = Story.objects.get(id=story_id)
                    BulletinStory.objects.create(
                        bulletin=instance,
                        story=story,
                        order=index
                    )
                except Story.DoesNotExist:
                    continue
        
        return instance


class ShowSerializer(serializers.ModelSerializer):
    """Serializer for shows"""
    creator_name = serializers.CharField(source='creator.get_full_name', read_only=True)
    categories_display = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Show
        fields = [
            'id', 'title', 'description', 'creator', 'creator_name',
            'audio_file', 'audio_url', 'duration',
            'categories', 'categories_display',
            'status', 'status_display', 'language', 'language_display',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'published_at']
    
    def get_categories_display(self, obj):
        return [category.name for category in obj.categories.all()]
    
    def get_audio_url(self, obj):
        if obj.audio_file:
            return self.context['request'].build_absolute_uri(obj.audio_file.url)
        return None


class TaskNoteSerializer(serializers.ModelSerializer):
    """Serializer for task notes"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = TaskNote
        fields = ['id', 'user', 'user_name', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for tasks"""
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    notes = TaskNoteSerializer(many=True, read_only=True)
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    related_story_title = serializers.CharField(source='related_story.title', read_only=True, allow_null=True)
    related_bulletin_title = serializers.CharField(source='related_bulletin.title', read_only=True, allow_null=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'task_type', 'task_type_display', 'title', 'description',
            'assigned_by', 'assigned_by_name', 'assigned_to', 'assigned_to_name',
            'due_date', 'related_story', 'related_story_title',
            'related_bulletin', 'related_bulletin_title',
            'status', 'status_display', 'notes',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks"""
    class Meta:
        model = Task
        fields = [
            'task_type', 'title', 'description',
            'assigned_to', 'due_date', 
            'related_story', 'related_bulletin',
        ]
    
    def create(self, validated_data):
        # Add the current user as the assigner
        validated_data['assigned_by'] = self.context['request'].user
        return super().create(validated_data)


class TranslationRequestSerializer(serializers.Serializer):
    """Serializer for requesting story translations"""
    language = serializers.ChoiceField(choices=Story.LANGUAGE_CHOICES)
    translator = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    auto_assign = serializers.BooleanField(default=True)
    due_date = serializers.DateTimeField(required=False)
    
    def validate(self, data):
        story = self.context.get('story')
        language = data.get('language')
        
        # Check if the story already has a translation in this language
        if story.translations.filter(language=language).exists():
            raise serializers.ValidationError(
                f"Translation in {dict(Story.LANGUAGE_CHOICES)[language]} already exists"
            )
        
        # If auto_assign is False, translator must be provided
        if not data.get('auto_assign') and not data.get('translator'):
            raise serializers.ValidationError("Translator must be specified when auto_assign is false")
        
        return data