from django.urls import path
from . import views

urlpatterns = [
    path("<int:report_id>/", views.report_detail, name="report_detail"),
    path("<int:report_id>/download/", views.download_pdf, name="download_pdf"),
    path("<int:report_id>/gerar/", views.trigger_report, name="trigger_report"),
]
