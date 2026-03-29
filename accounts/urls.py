from django.urls import path
from .views import UserRegistrationView, UserLoginView

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="api_register"),
    path("login/", UserLoginView.as_view(), name="api_login"),
]
