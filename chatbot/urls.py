from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.chat_api, name="chat_api"),
    path("csrf/", views.chatbot_csrf, name="chatbot_csrf"),
]