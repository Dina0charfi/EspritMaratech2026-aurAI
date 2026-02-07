from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),              # /
    path('transcribe/', views.transcribe, name='transcribe'),
    path('avatar/', views.show_avatar, name='avatar'),
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),

]