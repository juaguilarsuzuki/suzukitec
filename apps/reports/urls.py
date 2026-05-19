from django.urls import path
from . import views

urlpatterns = [
    path("", views.report_generator, name="report_generator"),
    path("gerar/", views.generate_report, name="generate_report"),
    path("<int:report_id>/", views.report_detail, name="report_detail"),
    path("<int:report_id>/download/", views.download_pdf, name="download_pdf"),
    path("<int:report_id>/enviar/", views.send_report_email, name="send_report_email"),
    path("<int:report_id>/regenerar/", views.trigger_report, name="trigger_report"),
]
