# accounts/views.py
import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

# We'll add specific views as we develop them