from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clientes/<int:client_id>/", views.client_detail, name="client_detail"),
]
