# newsroom/views.py
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction

from accounts.models import CustomUser
from .models import (
    Category, Story, StoryContent, AudioClip, 
    Bulletin, BulletinStory, Show, Task, TaskNote
)

logger = logging.getLogger(__name__)

# Helper functions
def is_staff(user):
    """Check if user is Newskoop staff"""
    return user.is_authenticated and user.user_type == CustomUser.UserType.STAFF

# Staff role checks
def is_editor_or_above(user):
    """Check if user is an editor or above"""
    return (user.is_authenticated and 
            user.user_type == CustomUser.UserType.STAFF and
            user.staff_role in [
                CustomUser.StaffRole.SUPERADMIN,
                CustomUser.StaffRole.ADMIN,
                CustomUser.StaffRole.EDITOR
            ])

def is_sub_editor_or_above(user):
    """Check if user is a sub-editor or above"""
    return (user.is_authenticated and 
            user.user_type == CustomUser.UserType.STAFF and
            user.staff_role in [
                CustomUser.StaffRole.SUPERADMIN,
                CustomUser.StaffRole.ADMIN,
                CustomUser.StaffRole.EDITOR,
                CustomUser.StaffRole.SUB_EDITOR
            ])

def can_create_story(user):
    """Check if user can create stories"""
    return (user.is_authenticated and 
            user.user_type == CustomUser.UserType.STAFF)

def can_edit_story(user, story):
    """Check if user can edit a story"""
    # Admins, editors, and sub-editors can edit any story
    if is_sub_editor_or_above(user):
        return True
    
    # Author can edit their own stories if in draft or review
    if story.author == user and story.status in ['DRAFT', 'REVIEW']:
        return True
    
    return False

def can_publish_story(user):
    """Check if user can publish stories"""
    return is_sub_editor_or_above(user)

def can_create_bulletin(user):
    """Check if user can create bulletins"""
    return is_sub_editor_or_above(user)

def can_create_show(user):
    """Check if user can create shows"""
    # Special case - some contractors may have this permission
    # but not other permissions
    return (user.is_authenticated and 
            user.user_type == CustomUser.UserType.STAFF)

# Dashboard Views
@login_required
def newsroom_dashboard(request):
    """Main dashboard for the newsroom"""
    context = {}
    user = request.user
    
    # Get counts
    story_count = Story.objects.count()
    published_story_count = Story.objects.filter(status='PUBLISHED').count()
    bulletin_count = Bulletin.objects.count()
    show_count = Show.objects.count()
    
    # Get recent content
    recent_stories = Story.objects.all().order_by('-created_at')[:5]
    recent_bulletins = Bulletin.objects.all().order_by('-created_at')[:5]
    
    # Get user tasks
    user_tasks = Task.objects.filter(
        assigned_to=user, 
        status__in=['TODO', 'IN_PROGRESS']
    ).order_by('due_date')[:5]
    
    context.update({
        'story_count': story_count,
        'published_story_count': published_story_count,
        'bulletin_count': bulletin_count,
        'show_count': show_count,
        'recent_stories': recent_stories,
        'recent_bulletins': recent_bulletins,
        'user_tasks': user_tasks,
    })
    
    return render(request, 'newsroom/dashboard.html', context)

# Story Views
@login_required
@user_passes_test(is_staff)
def story_list(request):
    """View for listing stories with filtering"""
    # Get filter parameters
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    language_filter = request.GET.get('language')
    search_query = request.GET.get('q')
    
    # Start with all stories
    stories = Story.objects.all()
    
    # Apply filters
    if status_filter:
        stories = stories.filter(status=status_filter)
    
    if category_filter:
        stories = stories.filter(categories__id=category_filter)
    
    if language_filter:
        stories = stories.filter(language=language_filter)
    
    if search_query:
        stories = stories.filter(
            Q(title__icontains=search_query) | 
            Q(content__content__icontains=search_query)
        )
    
    # Order by most recent first
    stories = stories.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(stories, 20)  # 20 stories per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'language_filter': language_filter,
        'search_query': search_query,
        'status_choices': Story.STATUS_CHOICES,
        'language_choices': Story.LANGUAGE_CHOICES,
    }
    
    return render(request, 'newsroom/stories/story_list.html', context)

@login_required
@user_passes_test(can_create_story)
def story_create(request):
    """View for creating a new story"""
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        content = request.POST.get('content')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        
        # Basic validation
        if not title:
            messages.error(request, 'Story title is required.')
            return redirect('story_create')
        
        # Create the story
        try:
            with transaction.atomic():
                # Create story
                story = Story.objects.create(
                    title=title,
                    author=request.user,
                    language=language
                )
                
                # Add categories
                if category_ids:
                    categories = Category.objects.filter(id__in=category_ids)
                    story.categories.set(categories)
                
                # Create content
                StoryContent.objects.create(
                    story=story,
                    content=content or ""
                )
                
                messages.success(request, f'Story "{title}" has been created.')
                return redirect('story_detail', story_id=story.id)
                
        except Exception as e:
            logger.error(f'Error creating story: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form
    categories = Category.objects.all()
    
    context = {
        'categories': categories,
        'language_choices': Story.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/stories/create.html', context)

@login_required
@user_passes_test(is_staff)
def story_detail(request, story_id):
    """View for viewing story details"""
    story = get_object_or_404(Story, id=story_id)
    
    # Check if story has content
    try:
        content = story.content
    except StoryContent.DoesNotExist:
        # Create empty content if none exists
        content = StoryContent.objects.create(story=story, content="")
    
    # Get audio clips
    audio_clips = story.audio_clips.all()
    
    # Get translations
    translations = story.translations.all()
    
    # Check permissions
    can_edit = can_edit_story(request.user, story)
    can_publish = can_publish_story(request.user)
    
    context = {
        'story': story,
        'content': content,
        'audio_clips': audio_clips,
        'translations': translations,
        'can_edit': can_edit,
        'can_publish': can_publish,
    }
    
    return render(request, 'newsroom/stories/detail.html', context)

@login_required
def story_edit(request, story_id):
    """View for editing a story"""
    story = get_object_or_404(Story, id=story_id)
    
    # Check permission
    if not can_edit_story(request.user, story):
        messages.error(request, 'You do not have permission to edit this story.')
        return redirect('story_detail', story_id=story.id)
    
    # Get or create content
    try:
        content = story.content
    except StoryContent.DoesNotExist:
        content = StoryContent.objects.create(story=story, content="")
    
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        new_content = request.POST.get('content')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        
        # Basic validation
        if not title:
            messages.error(request, 'Story title is required.')
            return redirect('story_edit', story_id=story.id)
        
        # Update the story
        try:
            with transaction.atomic():
                # Update story
                story.title = title
                story.language = language
                story.save()
                
                # Update categories
                if category_ids:
                    categories = Category.objects.filter(id__in=category_ids)
                    story.categories.set(categories)
                else:
                    story.categories.clear()
                
                # Update content
                content.content = new_content
                content.save()
                
                messages.success(request, f'Story "{title}" has been updated.')
                return redirect('story_detail', story_id=story.id)
                
        except Exception as e:
            logger.error(f'Error updating story: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form with current data
    categories = Category.objects.all()
    selected_categories = story.categories.all()
    
    context = {
        'story': story,
        'content': content,
        'categories': categories,
        'selected_categories': selected_categories,
        'language_choices': Story.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/stories/edit.html', context)

@login_required
@user_passes_test(can_publish_story)
def story_publish(request, story_id):
    """View for publishing a story"""
    story = get_object_or_404(Story, id=story_id)
    
    if request.method == 'POST':
        try:
            story.status = 'PUBLISHED'
            story.published_at = timezone.now()
            story.save()
            
            messages.success(request, f'Story "{story.title}" has been published.')
        except Exception as e:
            logger.error(f'Error publishing story: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('story_detail', story_id=story.id)

@login_required
def story_upload_audio(request, story_id):
    """View for uploading audio clips to a story"""
    story = get_object_or_404(Story, id=story_id)
    
    # Check permission
    if not can_edit_story(request.user, story):
        messages.error(request, 'You do not have permission to edit this story.')
        return redirect('story_detail', story_id=story.id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        audio_file = request.FILES.get('audio_file')
        
        # Basic validation
        if not title or not audio_file:
            messages.error(request, 'Title and audio file are required.')
            return redirect('story_detail', story_id=story.id)
        
        try:
            # Create audio clip
            AudioClip.objects.create(
                story=story,
                title=title,
                description=description,
                file=audio_file
            )
            
            messages.success(request, f'Audio clip "{title}" has been uploaded.')
        except Exception as e:
            logger.error(f'Error uploading audio: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('story_detail', story_id=story.id)

@login_required
def story_delete_audio(request, story_id, audio_id):
    """View for deleting an audio clip"""
    story = get_object_or_404(Story, id=story_id)
    audio = get_object_or_404(AudioClip, id=audio_id, story=story)
    
    # Check permission
    if not can_edit_story(request.user, story):
        messages.error(request, 'You do not have permission to edit this story.')
        return redirect('story_detail', story_id=story.id)
    
    if request.method == 'POST':
        try:
            audio_title = audio.title
            audio.delete()
            messages.success(request, f'Audio clip "{audio_title}" has been deleted.')
        except Exception as e:
            logger.error(f'Error deleting audio: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('story_detail', story_id=story.id)

@login_required
@user_passes_test(is_staff)
def story_translate(request, story_id):
    """View for creating a translation of a story"""
    story = get_object_or_404(Story, id=story_id)
    
    if request.method == 'POST':
        language = request.POST.get('language')
        
        # Check if translation already exists
        if story.translations.filter(language=language).exists():
            messages.error(request, f'A translation in this language already exists.')
            return redirect('story_detail', story_id=story.id)
        
        try:
            with transaction.atomic():
                # Create translation story
                translation = Story.objects.create(
                    title=story.title,
                    author=request.user,
                    language=language,
                    original_story=story
                )
                
                # Copy categories
                translation.categories.set(story.categories.all())
                
                # Create content (copy original)
                try:
                    original_content = story.content.content
                except StoryContent.DoesNotExist:
                    original_content = ""
                
                StoryContent.objects.create(
                    story=translation,
                    content=original_content
                )
                
                messages.success(request, f'Translation has been created. You can now edit it.')
                return redirect('story_edit', story_id=translation.id)
                
        except Exception as e:
            logger.error(f'Error creating translation: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request
    # Get available languages for translation (exclude already translated ones)
    existing_languages = [story.language] + list(story.translations.values_list('language', flat=True))
    available_languages = [lang for lang in Story.LANGUAGE_CHOICES if lang[0] not in existing_languages]
    
    context = {
        'story': story,
        'available_languages': available_languages
    }
    
    return render(request, 'newsroom/stories/translate.html', context)

# Bulletin Views
@login_required
@user_passes_test(is_staff)
def bulletin_list(request):
    """View for listing bulletins with filtering"""
    # Get filter parameters
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    language_filter = request.GET.get('language')
    search_query = request.GET.get('q')
    
    # Start with all bulletins
    bulletins = Bulletin.objects.all()
    
    # Apply filters
    if status_filter:
        bulletins = bulletins.filter(status=status_filter)
    
    if category_filter:
        bulletins = bulletins.filter(categories__id=category_filter)
    
    if language_filter:
        bulletins = bulletins.filter(language=language_filter)
    
    if search_query:
        bulletins = bulletins.filter(
            Q(title__icontains=search_query) | 
            Q(intro__icontains=search_query) |
            Q(outro__icontains=search_query)
        )
    
    # Order by most recent first
    bulletins = bulletins.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(bulletins, 20)  # 20 bulletins per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'language_filter': language_filter,
        'search_query': search_query,
        'status_choices': Bulletin.STATUS_CHOICES,
        'language_choices': Bulletin.LANGUAGE_CHOICES,
    }
    
    return render(request, 'newsroom/bulletins/list.html', context)

@login_required
@user_passes_test(can_create_bulletin)
def bulletin_create(request):
    """View for creating a new bulletin"""
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        intro = request.POST.get('intro')
        outro = request.POST.get('outro', '')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        story_ids = request.POST.getlist('stories')
        
        # Basic validation
        if not title or not intro:
            messages.error(request, 'Bulletin title and intro are required.')
            return redirect('bulletin_create')
        
        # Create the bulletin
        try:
            with transaction.atomic():
                # Create bulletin
                bulletin = Bulletin.objects.create(
                    title=title,
                    intro=intro,
                    outro=outro,
                    editor=request.user,
                    language=language
                )
                
                # Add categories
                if category_ids:
                    categories = Category.objects.filter(id__in=category_ids)
                    bulletin.categories.set(categories)
                
                # Add stories in order
                for index, story_id in enumerate(story_ids):
                    try:
                        story = Story.objects.get(id=story_id)
                        BulletinStory.objects.create(
                            bulletin=bulletin,
                            story=story,
                            order=index
                        )
                    except Story.DoesNotExist:
                        continue
                
                messages.success(request, f'Bulletin "{title}" has been created.')
                return redirect('bulletin_detail', bulletin_id=bulletin.id)
                
        except Exception as e:
            logger.error(f'Error creating bulletin: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form
    categories = Category.objects.all()
    
    # Get published stories for selection
    stories = Story.objects.filter(status='PUBLISHED')
    
    context = {
        'categories': categories,
        'stories': stories,
        'language_choices': Bulletin.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/bulletins/create.html', context)

@login_required
@user_passes_test(is_staff)
def bulletin_detail(request, bulletin_id):
    """View for viewing bulletin details"""
    bulletin = get_object_or_404(Bulletin, id=bulletin_id)
    
    # Get stories in order
    bulletin_stories = bulletin.bulletin_stories.all().order_by('order')
    
    # Get translations
    translations = bulletin.translations.all()
    
    # Check permissions
    can_edit = is_sub_editor_or_above(request.user)
    can_publish = is_editor_or_above(request.user)
    
    context = {
        'bulletin': bulletin,
        'bulletin_stories': bulletin_stories,
        'translations': translations,
        'can_edit': can_edit,
        'can_publish': can_publish,
    }
    
    return render(request, 'newsroom/bulletins/detail.html', context)

@login_required
@user_passes_test(is_sub_editor_or_above)
def bulletin_edit(request, bulletin_id):
    """View for editing a bulletin"""
    bulletin = get_object_or_404(Bulletin, id=bulletin_id)
    
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        intro = request.POST.get('intro')
        outro = request.POST.get('outro', '')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        story_ids = request.POST.getlist('stories')
        
        # Basic validation
        if not title or not intro:
            messages.error(request, 'Bulletin title and intro are required.')
            return redirect('bulletin_edit', bulletin_id=bulletin.id)
        
        # Update the bulletin
        try:
            with transaction.atomic():
                # Update bulletin
                bulletin.title = title
                bulletin.intro = intro
                bulletin.outro = outro
                bulletin.language = language
                bulletin.save()
                
                # Update categories
                if category_ids:
                    categories = Category.objects.filter(id__in=category_ids)
                    bulletin.categories.set(categories)
                else:
                    bulletin.categories.clear()
                
                # Update stories - remove existing and add new ones
                bulletin.bulletin_stories.all().delete()
                
                # Add stories in order
                for index, story_id in enumerate(story_ids):
                    try:
                        story = Story.objects.get(id=story_id)
                        BulletinStory.objects.create(
                            bulletin=bulletin,
                            story=story,
                            order=index
                        )
                    except Story.DoesNotExist:
                        continue
                
                messages.success(request, f'Bulletin "{title}" has been updated.')
                return redirect('bulletin_detail', bulletin_id=bulletin.id)
                
        except Exception as e:
            logger.error(f'Error updating bulletin: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form with current data
    categories = Category.objects.all()
    selected_categories = bulletin.categories.all()
    
    # Get published stories for selection
    stories = Story.objects.filter(status='PUBLISHED')
    
    # Get currently selected stories in order
    bulletin_stories = bulletin.bulletin_stories.all().order_by('order')
    selected_story_ids = [bs.story.id for bs in bulletin_stories]
    
    context = {
        'bulletin': bulletin,
        'categories': categories,
        'selected_categories': selected_categories,
        'stories': stories,
        'bulletin_stories': bulletin_stories,
        'selected_story_ids': selected_story_ids,
        'language_choices': Bulletin.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/bulletins/edit.html', context)

@login_required
@user_passes_test(is_editor_or_above)
def bulletin_publish(request, bulletin_id):
    """View for publishing a bulletin"""
    bulletin = get_object_or_404(Bulletin, id=bulletin_id)
    
    if request.method == 'POST':
        try:
            bulletin.status = 'PUBLISHED'
            bulletin.published_at = timezone.now()
            bulletin.save()
            
            messages.success(request, f'Bulletin "{bulletin.title}" has been published.')
        except Exception as e:
            logger.error(f'Error publishing bulletin: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('bulletin_detail', bulletin_id=bulletin.id)

@login_required
@user_passes_test(is_sub_editor_or_above)
def bulletin_translate(request, bulletin_id):
    """View for creating a translation of a bulletin"""
    bulletin = get_object_or_404(Bulletin, id=bulletin_id)
    
    if request.method == 'POST':
        language = request.POST.get('language')
        
        # Check if translation already exists
        if bulletin.translations.filter(language=language).exists():
            messages.error(request, f'A translation in this language already exists.')
            return redirect('bulletin_detail', bulletin_id=bulletin.id)
        
        try:
            with transaction.atomic():
                # Create translation bulletin
                translation = Bulletin.objects.create(
                    title=bulletin.title,
                    intro=bulletin.intro,
                    outro=bulletin.outro,
                    editor=request.user,
                    language=language,
                    original_bulletin=bulletin
                )
                
                # Copy categories
                translation.categories.set(bulletin.categories.all())
                
                # Copy stories in the same order
                for bs in bulletin.bulletin_stories.all().order_by('order'):
                    BulletinStory.objects.create(
                        bulletin=translation,
                        story=bs.story,
                        order=bs.order
                    )
                
                messages.success(request, f'Translation has been created. You can now edit it.')
                return redirect('bulletin_edit', bulletin_id=translation.id)
                
        except Exception as e:
            logger.error(f'Error creating translation: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request
    # Get available languages for translation (exclude already translated ones)
    existing_languages = [bulletin.language] + list(bulletin.translations.values_list('language', flat=True))
    available_languages = [lang for lang in Bulletin.LANGUAGE_CHOICES if lang[0] not in existing_languages]
    
    context = {
        'bulletin': bulletin,
        'available_languages': available_languages
    }
    
    return render(request, 'newsroom/bulletins/translate.html', context)

# Show Views
@login_required
@user_passes_test(is_staff)
def show_list(request):
    """View for listing shows with filtering"""
    # Get filter parameters
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    language_filter = request.GET.get('language')
    search_query = request.GET.get('q')
    
    # Start with all shows
    shows = Show.objects.all()
    
    # Apply filters
    if status_filter:
        shows = shows.filter(status=status_filter)
    
    if category_filter:
        shows = shows.filter(categories__id=category_filter)
    
    if language_filter:
        shows = shows.filter(language=language_filter)
    
    if search_query:
        shows = shows.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Order by most recent first
    shows = shows.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(shows, 20)  # 20 shows per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'language_filter': language_filter,
        'search_query': search_query,
        'status_choices': Show.STATUS_CHOICES,
        'language_choices': Show.LANGUAGE_CHOICES,
    }
    
    return render(request, 'newsroom/shows/list.html', context)

@login_required
@user_passes_test(can_create_show)
def show_create(request):
    """View for creating a new show"""
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        audio_file = request.FILES.get('audio_file')
        
        # Basic validation
        if not title or not description or not audio_file:
            messages.error(request, 'Title, description, and audio file are required.')
            return redirect('show_create')
        
        # Create the show
        try:
            # Create show
            show = Show.objects.create(
                title=title,
                description=description,
                creator=request.user,
                language=language,
                audio_file=audio_file
            )
            
            # Add categories
            if category_ids:
                categories = Category.objects.filter(id__in=category_ids)
                show.categories.set(categories)
            
            messages.success(request, f'Show "{title}" has been created.')
            return redirect('show_detail', show_id=show.id)
                
        except Exception as e:
            logger.error(f'Error creating show: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form
    categories = Category.objects.all()
    
    context = {
        'categories': categories,
        'language_choices': Show.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/shows/create.html', context)

@login_required
@user_passes_test(is_staff)
def show_detail(request, show_id):
    """View for viewing show details"""
    show = get_object_or_404(Show, id=show_id)
    
    # Check permissions
    can_edit = request.user == show.creator or is_editor_or_above(request.user)
    can_publish = is_editor_or_above(request.user)
    
    context = {
        'show': show,
        'can_edit': can_edit,
        'can_publish': can_publish,
    }
    
    return render(request, 'newsroom/shows/detail.html', context)

@login_required
def show_edit(request, show_id):
    """View for editing a show"""
    show = get_object_or_404(Show, id=show_id)
    
    # Check permission
    if not (request.user == show.creator or is_editor_or_above(request.user)):
        messages.error(request, 'You do not have permission to edit this show.')
        return redirect('show_detail', show_id=show.id)
    
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        category_ids = request.POST.getlist('categories')
        language = request.POST.get('language')
        audio_file = request.FILES.get('audio_file')
        
        # Basic validation
        if not title or not description:
            messages.error(request, 'Title and description are required.')
            return redirect('show_edit', show_id=show.id)
        
        # Update the show
        try:
            # Update show fields
            show.title = title
            show.description = description
            show.language = language
            
            # Update audio file if provided
            if audio_file:
                show.audio_file = audio_file
            
            show.save()
            
            # Update categories
            if category_ids:
                categories = Category.objects.filter(id__in=category_ids)
                show.categories.set(categories)
            else:
                show.categories.clear()
            
            messages.success(request, f'Show "{title}" has been updated.')
            return redirect('show_detail', show_id=show.id)
                
        except Exception as e:
            logger.error(f'Error updating show: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form with current data
    categories = Category.objects.all()
    selected_categories = show.categories.all()
    
    context = {
        'show': show,
        'categories': categories,
        'selected_categories': selected_categories,
        'language_choices': Show.LANGUAGE_CHOICES
    }
    
    return render(request, 'newsroom/shows/edit.html', context)

@login_required
@user_passes_test(is_editor_or_above)
def show_publish(request, show_id):
    """View for publishing a show"""
    show = get_object_or_404(Show, id=show_id)
    
    if request.method == 'POST':
        try:
            show.status = 'PUBLISHED'
            show.published_at = timezone.now()
            show.save()
            
            messages.success(request, f'Show "{show.title}" has been published.')
        except Exception as e:
            logger.error(f'Error publishing show: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('show_detail', show_id=show.id)

# Category Views
@login_required
@user_passes_test(is_editor_or_above)
def category_list(request):
    """View for listing and managing categories"""
    # Get parent categories with their children
    parent_categories = Category.objects.filter(parent=None).order_by('name')
    
    context = {
        'parent_categories': parent_categories
    }
    
    return render(request, 'newsroom/categories/list.html', context)

@login_required
@user_passes_test(is_editor_or_above)
def category_create(request):
    """View for creating a new category"""
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        
        # Access permissions
        is_news_story = request.POST.get('is_news_story') == 'on'
        is_news_bulletin = request.POST.get('is_news_bulletin') == 'on'
        is_sport = request.POST.get('is_sport') == 'on'
        is_finance = request.POST.get('is_finance') == 'on'
        is_specialty = request.POST.get('is_specialty') == 'on'
        
        # Basic validation
        if not name or not slug:
            messages.error(request, 'Category name and slug are required.')
            return redirect('category_create')
        
        # Check if slug is unique
        if Category.objects.filter(slug=slug).exists():
            messages.error(request, 'A category with this slug already exists.')
            return redirect('category_create')
        
        # Create the category
        try:
            parent = None
            if parent_id:
                parent = Category.objects.get(id=parent_id)
            
            category = Category.objects.create(
                name=name,
                slug=slug,
                description=description,
                parent=parent,
                is_news_story=is_news_story,
                is_news_bulletin=is_news_bulletin,
                is_sport=is_sport,
                is_finance=is_finance,
                is_specialty=is_specialty
            )
            
            messages.success(request, f'Category "{name}" has been created.')
            return redirect('category_list')
                
        except Exception as e:
            logger.error(f'Error creating category: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form
    parent_categories = Category.objects.filter(parent=None).order_by('name')
    
    context = {
        'parent_categories': parent_categories
    }
    
    return render(request, 'newsroom/categories/create.html', context)

@login_required
@user_passes_test(is_editor_or_above)
def category_edit(request, category_id):
    """View for editing a category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        
        # Access permissions
        is_news_story = request.POST.get('is_news_story') == 'on'
        is_news_bulletin = request.POST.get('is_news_bulletin') == 'on'
        is_sport = request.POST.get('is_sport') == 'on'
        is_finance = request.POST.get('is_finance') == 'on'
        is_specialty = request.POST.get('is_specialty') == 'on'
        
        # Basic validation
        if not name or not slug:
            messages.error(request, 'Category name and slug are required.')
            return redirect('category_edit', category_id=category.id)
        
        # Check if slug is unique (excluding this category)
        if Category.objects.filter(slug=slug).exclude(id=category.id).exists():
            messages.error(request, 'A category with this slug already exists.')
            return redirect('category_edit', category_id=category.id)
        
        # Update the category
        try:
            parent = None
            if parent_id:
                # Don't allow setting self or child as parent (avoid circular references)
                if str(category.id) == parent_id:
                    messages.error(request, 'Cannot set self as parent.')
                    return redirect('category_edit', category_id=category.id)
                
                # Ensure the parent is not a descendant
                def check_descendants(parent_id, category_id):
                    """Check if category_id is in the descendants of parent_id"""
                    descendants = Category.objects.filter(parent_id=category_id)
                    if not descendants:
                        return False
                    
                    for descendant in descendants:
                        if str(descendant.id) == parent_id:
                            return True
                        if check_descendants(parent_id, descendant.id):
                            return True
                    
                    return False
                
                if check_descendants(parent_id, category.id):
                    messages.error(request, 'Cannot set a descendant as parent.')
                    return redirect('category_edit', category_id=category.id)
                
                parent = Category.objects.get(id=parent_id)
            
            category.name = name
            category.slug = slug
            category.description = description
            category.parent = parent
            category.is_news_story = is_news_story
            category.is_news_bulletin = is_news_bulletin
            category.is_sport = is_sport
            category.is_finance = is_finance
            category.is_specialty = is_specialty
            category.save()
            
            messages.success(request, f'Category "{name}" has been updated.')
            return redirect('category_list')
                
        except Exception as e:
            logger.error(f'Error updating category: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form with current data
    parent_categories = Category.objects.filter(parent=None).exclude(id=category.id).order_by('name')
    
    context = {
        'category': category,
        'parent_categories': parent_categories
    }
    
    return render(request, 'newsroom/categories/edit.html', context)

@login_required
@user_passes_test(is_editor_or_above)
def category_delete(request, category_id):
    """View for deleting a category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        try:
            # Check if category has children
            if category.children.exists():
                messages.error(request, 'Cannot delete category with child categories. Delete or reassign children first.')
                return redirect('category_list')
            
            # Check if category has content
            if category.stories.exists() or category.bulletins.exists() or category.shows.exists():
                messages.error(request, 'Cannot delete category with associated content. Remove content first.')
                return redirect('category_list')
            
            name = category.name
            category.delete()
            messages.success(request, f'Category "{name}" has been deleted.')
        except Exception as e:
            logger.error(f'Error deleting category: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('category_list')

# Task Views
@login_required
@user_passes_test(is_staff)
def task_list(request):
    """View for listing tasks with filtering"""
    # Default to showing current user's tasks
    user_filter = request.GET.get('user')
    status_filter = request.GET.get('status')
    task_type_filter = request.GET.get('task_type')
    search_query = request.GET.get('q')
    
    # Start with all tasks visible to user
    if is_editor_or_above(request.user):
        # Editors and above can see all tasks
        tasks = Task.objects.all()
    else:
        # Others see only tasks they're assigned to or created
        tasks = Task.objects.filter(
            Q(assigned_to=request.user) | Q(assigned_by=request.user)
        )
    
    # Apply filters
    if user_filter:
        tasks = tasks.filter(assigned_to__id=user_filter)
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    if task_type_filter:
        tasks = tasks.filter(task_type=task_type_filter)
    
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Order by due date, then creation date
    tasks = tasks.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(tasks, 20)  # 20 tasks per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get staff users for filter dropdown
    staff_users = CustomUser.objects.filter(user_type=CustomUser.UserType.STAFF)
    
    context = {
        'page_obj': page_obj,
        'staff_users': staff_users,
        'user_filter': user_filter,
        'status_filter': status_filter,
        'task_type_filter': task_type_filter,
        'search_query': search_query,
        'status_choices': Task.STATUS_CHOICES,
        'task_type_choices': Task.TASK_TYPE_CHOICES,
    }
    
    return render(request, 'newsroom/tasks/list.html', context)

@login_required
@user_passes_test(is_staff)
def my_tasks(request):
    """View for showing current user's assigned tasks"""
    # Get tasks assigned to the current user
    tasks = Task.objects.filter(assigned_to=request.user).order_by('status', 'due_date')
    
    # Split tasks by status
    todo_tasks = tasks.filter(status='TODO')
    in_progress_tasks = tasks.filter(status='IN_PROGRESS')
    review_tasks = tasks.filter(status='REVIEW')
    completed_tasks = tasks.filter(status='COMPLETED').order_by('-completed_at')[:5]  # Show only recent completed
    
    context = {
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'review_tasks': review_tasks,
        'completed_tasks': completed_tasks
    }
    
    return render(request, 'newsroom/tasks/my_tasks.html', context)

@login_required
@user_passes_test(is_sub_editor_or_above)
def task_create(request):
    """View for creating a new task"""
    if request.method == 'POST':
        # Extract form data
        task_type = request.POST.get('task_type')
        title = request.POST.get('title')
        description = request.POST.get('description')
        assigned_to_id = request.POST.get('assigned_to')
        due_date = request.POST.get('due_date')
        related_story_id = request.POST.get('related_story')
        related_bulletin_id = request.POST.get('related_bulletin')
        
        # Basic validation
        if not title or not description or not assigned_to_id:
            messages.error(request, 'Title, description, and assignee are required.')
            return redirect('task_create')
        
        # Create the task
        try:
            # Get related objects
            assigned_to = CustomUser.objects.get(id=assigned_to_id)
            
            related_story = None
            if related_story_id:
                try:
                    related_story = Story.objects.get(id=related_story_id)
                except Story.DoesNotExist:
                    pass
            
            related_bulletin = None
            if related_bulletin_id:
                try:
                    related_bulletin = Bulletin.objects.get(id=related_bulletin_id)
                except Bulletin.DoesNotExist:
                    pass
            
            # Create task
            task = Task.objects.create(
                task_type=task_type,
                title=title,
                description=description,
                assigned_by=request.user,
                assigned_to=assigned_to,
                due_date=due_date if due_date else None,
                related_story=related_story,
                related_bulletin=related_bulletin
            )
            
            messages.success(request, f'Task "{title}" has been created and assigned to {assigned_to.get_full_name()}.')
            return redirect('task_detail', task_id=task.id)
                
        except Exception as e:
            logger.error(f'Error creating task: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show form
    staff_users = CustomUser.objects.filter(user_type=CustomUser.UserType.STAFF)
    stories = Story.objects.all().order_by('-created_at')[:50]  # Most recent 50
    bulletins = Bulletin.objects.all().order_by('-created_at')[:50]  # Most recent 50
    
    context = {
        'staff_users': staff_users,
        'stories': stories,
        'bulletins': bulletins,
        'task_type_choices': Task.TASK_TYPE_CHOICES
    }
    
    return render(request, 'newsroom/tasks/create.html', context)

@login_required
@user_passes_test(is_staff)
def task_detail(request, task_id):
    """View for viewing task details"""
    task = get_object_or_404(Task, id=task_id)
    
    # Check if user can view this task
    if not (is_editor_or_above(request.user) or task.assigned_to == request.user or task.assigned_by == request.user):
        messages.error(request, 'You do not have permission to view this task.')
        return redirect('my_tasks')
    
    # Get task notes
    notes = task.notes.all().order_by('-created_at')
    
    # Check if user can update task status
    can_update_status = request.user == task.assigned_to or is_editor_or_above(request.user)
    
    context = {
        'task': task,
        'notes': notes,
        'can_update_status': can_update_status,
        'status_choices': Task.STATUS_CHOICES
    }
    
    return render(request, 'newsroom/tasks/detail.html', context)

@login_required
@user_passes_test(is_staff)
def task_update_status(request, task_id):
    """View for updating task status"""
    task = get_object_or_404(Task, id=task_id)
    
    # Check if user can update this task
    if not (is_editor_or_above(request.user) or task.assigned_to == request.user):
        messages.error(request, 'You do not have permission to update this task.')
        return redirect('task_detail', task_id=task.id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        note_content = request.POST.get('note', '')
        
        try:
            # Add a status update note if provided
            if note_content:
                TaskNote.objects.create(
                    task=task,
                    user=request.user,
                    content=note_content
                )
            
            # Update status
            old_status = task.get_status_display()
            task.status = status
            
            # If completing, set the completion date
            if status == 'COMPLETED' and task.status != 'COMPLETED':
                task.completed_at = timezone.now()
            
            task.save()
            
            messages.success(request, f'Task status updated from {old_status} to {task.get_status_display()}.')
        except Exception as e:
            logger.error(f'Error updating task status: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('task_detail', task_id=task.id)

@login_required
@user_passes_test(is_staff)
def add_task_note(request, task_id):
    """View for adding a note to a task"""
    task = get_object_or_404(Task, id=task_id)
    
    # Check if user can add notes to this task
    if not (is_editor_or_above(request.user) or task.assigned_to == request.user or task.assigned_by == request.user):
        messages.error(request, 'You do not have permission to add notes to this task.')
        return redirect('task_detail', task_id=task.id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        
        if not content:
            messages.error(request, 'Note content is required.')
            return redirect('task_detail', task_id=task.id)
        
        try:
            TaskNote.objects.create(
                task=task,
                user=request.user,
                content=content
            )
            
            messages.success(request, 'Note has been added to the task.')
        except Exception as e:
            logger.error(f'Error adding task note: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('task_detail', task_id=task.id)

# Translation Dashboard
@login_required
@user_passes_test(is_staff)
def translation_dashboard(request):
    """Dashboard for translation tasks"""
    # Get all stories that need translation
    english_stories = Story.objects.filter(
        language='EN',
        status='PUBLISHED'
    )
    
    # Stories needing Afrikaans translation
    stories_needing_afrikaans = []
    for story in english_stories:
        # Check if it has Afrikaans translation
        if not story.translations.filter(language='AF').exists():
            stories_needing_afrikaans.append(story)
    
    # Stories needing Xhosa translation
    stories_needing_xhosa = []
    for story in english_stories:
        # Check if it has Xhosa translation
        if not story.translations.filter(language='XH').exists():
            stories_needing_xhosa.append(story)
    
    # Get all bulletins that need translation
    english_bulletins = Bulletin.objects.filter(
        language='EN',
        status='PUBLISHED'
    )
    
    # Bulletins needing Afrikaans translation
    bulletins_needing_afrikaans = []
    for bulletin in english_bulletins:
        # Check if it has Afrikaans translation
        if not bulletin.translations.filter(language='AF').exists():
            bulletins_needing_afrikaans.append(bulletin)
    
    # Bulletins needing Xhosa translation
    bulletins_needing_xhosa = []
    for bulletin in english_bulletins:
        # Check if it has Xhosa translation
        if not bulletin.translations.filter(language='XH').exists():
            bulletins_needing_xhosa.append(bulletin)
    
    # Get active translation tasks
    translation_tasks = Task.objects.filter(
        task_type='STORY_TRANSLATE',
        status__in=['TODO', 'IN_PROGRESS']
    ).order_by('due_date')
    
    context = {
        'stories_needing_afrikaans': stories_needing_afrikaans,
        'stories_needing_xhosa': stories_needing_xhosa,
        'bulletins_needing_afrikaans': bulletins_needing_afrikaans,
        'bulletins_needing_xhosa': bulletins_needing_xhosa,
        'translation_tasks': translation_tasks
    }
    
    return render(request, 'newsroom/translation/dashboard.html', context)

@login_required
@user_passes_test(is_sub_editor_or_above)
def create_translation_task(request):
    """View for creating a translation task"""
    if request.method == 'POST':
        content_type = request.POST.get('content_type')
        content_id = request.POST.get('content_id')
        language = request.POST.get('language')
        assigned_to_id = request.POST.get('assigned_to')
        due_date = request.POST.get('due_date')
        
        # Validation
        if not content_type or not content_id or not language or not assigned_to_id:
            messages.error(request, 'All fields are required.')
            return redirect('translation_dashboard')
        
        try:
            assigned_to = CustomUser.objects.get(id=assigned_to_id)
            
            if content_type == 'story':
                # Get the story
                story = Story.objects.get(id=content_id)
                
                # Check if translation already exists
                if story.translations.filter(language=language).exists():
                    messages.error(request, f'Translation in {dict(Story.LANGUAGE_CHOICES)[language]} already exists.')
                    return redirect('translation_dashboard')
                
                # Create task
                task = Task.objects.create(
                    task_type='STORY_TRANSLATE',
                    title=f'Translate story: {story.title}',
                    description=f'Translate this story from {story.get_language_display()} to {dict(Story.LANGUAGE_CHOICES)[language]}.',
                    assigned_by=request.user,
                    assigned_to=assigned_to,
                    due_date=due_date if due_date else None,
                    related_story=story
                )
            
            elif content_type == 'bulletin':
                # Get the bulletin
                bulletin = Bulletin.objects.get(id=content_id)
                
                # Check if translation already exists
                if bulletin.translations.filter(language=language).exists():
                    messages.error(request, f'Translation in {dict(Bulletin.LANGUAGE_CHOICES)[language]} already exists.')
                    return redirect('translation_dashboard')
                
                # Create task
                task = Task.objects.create(
                    task_type='STORY_TRANSLATE',
                    title=f'Translate bulletin: {bulletin.title}',
                    description=f'Translate this bulletin from {bulletin.get_language_display()} to {dict(Bulletin.LANGUAGE_CHOICES)[language]}.',
                    assigned_by=request.user,
                    assigned_to=assigned_to,
                    due_date=due_date if due_date else None,
                    related_bulletin=bulletin
                )
            
            messages.success(request, f'Translation task assigned to {assigned_to.get_full_name()}.')
            return redirect('task_detail', task_id=task.id)
            
        except Exception as e:
            logger.error(f'Error creating translation task: {str(e)}')
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('translation_dashboard')