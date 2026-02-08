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
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('webauthn/register/', views.webauthn_register_page, name='webauthn_register_page'),
    path('webauthn/register/options/', views.webauthn_register_options, name='webauthn_register_options'),
    path('webauthn/register/verify/', views.webauthn_register_verify, name='webauthn_register_verify'),
    path('webauthn/authenticate/options/', views.webauthn_authenticate_options, name='webauthn_authenticate_options'),
    path('webauthn/authenticate/verify/', views.webauthn_authenticate_verify, name='webauthn_authenticate_verify'),
    path('reclamation/', views.submit_reclamation, name='reclamation'),
    path('api/animation/', views.get_animation, name='get_animation'),
]