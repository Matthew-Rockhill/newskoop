# newsroom/models.py
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser, RadioStation
import uuid

class Category(models.Model):
    """Hierarchical category system for organizing content"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For mapping to station access permissions
    is_news_story = models.BooleanField(default=False)
    is_news_bulletin = models.BooleanField(default=False)
    is_sport = models.BooleanField(default=False) 
    is_finance = models.BooleanField(default=False)
    is_specialty = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def full_path(self):
        """Return the full category path (parent > child > etc)"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name


class Story(models.Model):
    """Base content unit - a story/script for radio stations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic metadata
    title = models.CharField(max_length=255)
    author = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='authored_stories')
    categories = models.ManyToManyField(Category, related_name='stories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Publishing information
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'In Review'),
        ('APPROVED', 'Approved'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Language tracking (original language)
    LANGUAGE_CHOICES = [
        ('EN', 'English'),
        ('AF', 'Afrikaans'),
        ('XH', 'Xhosa'),
    ]
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='EN')
    
    # For translated stories, link to original
    original_story = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='translations')
    
    class Meta:
        verbose_name_plural = 'Stories'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def publish(self):
        """Publish the story"""
        self.status = 'PUBLISHED'
        self.published_at = timezone.now()
        self.save()
    
    @property
    def has_audio(self):
        """Check if story has audio clips"""
        return self.audio_clips.exists()
    
    @property 
    def word_count(self):
        """Calculate word count of the story"""
        try:
            return len(self.content.content.split())
        except:
            return 0


class StoryContent(models.Model):
    """Content for a story (allows for language variations)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.OneToOneField(Story, on_delete=models.CASCADE, related_name='content')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Content for {self.story.title}"


class AudioClip(models.Model):
    """Audio clips associated with stories"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='audio_clips')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='audio_clips/%Y/%m/%d/')
    duration = models.PositiveIntegerField(help_text="Duration in seconds", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return self.title


class Bulletin(models.Model):
    """A curated collection of stories"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic metadata
    title = models.CharField(max_length=255)
    editor = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='bulletins')
    categories = models.ManyToManyField(Category, related_name='bulletins')
    
    # Content
    intro = models.TextField()
    outro = models.TextField(blank=True)
    
    # Publishing information
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'In Review'),
        ('APPROVED', 'Approved'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Language
    LANGUAGE_CHOICES = [
        ('EN', 'English'),
        ('AF', 'Afrikaans'),
        ('XH', 'Xhosa'),
    ]
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='EN')
    
    # For translated bulletins, link to original
    original_bulletin = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='translations')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def publish(self):
        """Publish the bulletin"""
        self.status = 'PUBLISHED'
        self.published_at = timezone.now()
        self.save()


class BulletinStory(models.Model):
    """Junction model for ordering stories in bulletins"""
    bulletin = models.ForeignKey(Bulletin, on_delete=models.CASCADE, related_name='bulletin_stories')
    story = models.ForeignKey(Story, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['order']
        unique_together = ['bulletin', 'story']
    
    def __str__(self):
        return f"{self.bulletin.title} - {self.story.title}"


class Show(models.Model):
    """Pre-recorded shows (podcast-like)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic metadata
    title = models.CharField(max_length=255)
    description = models.TextField()
    creator = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='shows')
    categories = models.ManyToManyField(Category, related_name='shows')
    
    # Audio file
    audio_file = models.FileField(upload_to='shows/%Y/%m/%d/')
    duration = models.PositiveIntegerField(help_text="Duration in seconds", null=True, blank=True)
    
    # Publishing information
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'In Review'),
        ('APPROVED', 'Approved'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Language
    LANGUAGE_CHOICES = [
        ('EN', 'English'),
        ('AF', 'Afrikaans'),
        ('XH', 'Xhosa'),
    ]
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='EN')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def publish(self):
        """Publish the show"""
        self.status = 'PUBLISHED'
        self.published_at = timezone.now()
        self.save()


class Task(models.Model):
    """Task management system for content creation workflow"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Task details
    TASK_TYPE_CHOICES = [
        ('STORY_CREATE', 'Create Story'),
        ('STORY_EDIT', 'Edit Story'),
        ('STORY_TRANSLATE', 'Translate Story'),
        ('BULLETIN_CREATE', 'Create Bulletin'),
        ('SHOW_CREATE', 'Create Show'),
        ('FOLLOW_UP', 'Follow Up'),
        ('OTHER', 'Other'),
    ]
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Assignment information
    assigned_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='assigned_tasks')
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='tasks')
    due_date = models.DateTimeField(null=True, blank=True)
    
    # Related content (optional)
    related_story = models.ForeignKey(Story, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    related_bulletin = models.ForeignKey(Bulletin, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    
    # Status tracking
    STATUS_CHOICES = [
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'In Review'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def complete(self):
        """Mark task as completed"""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()


class TaskNote(models.Model):
    """Notes and updates on tasks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note on {self.task.title} by {self.user.email}"