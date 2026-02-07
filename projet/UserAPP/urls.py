from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),              # /
    path('transcribe/', views.transcribe, name='transcribe'),
    path('avatar/', views.show_avatar, name='avatar'),
    path('learning/', views.learning, name='learning'),
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('signout/', views.signout, name='signout'),
    path('profile/', views.profile, name='profile'),
    path('reclamation/', views.submit_reclamation, name='reclamation'),

]