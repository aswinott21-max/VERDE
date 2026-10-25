from django.urls import path

from . import views

app_name = "sales_reports"

urlpatterns = [
    path("", views.sales_report_page, name="sales_report"),
    path("download/excel/", views.download_sales_report_excel, name="download_excel"),
    path("download/pdf/", views.download_sales_report_pdf, name="download_pdf"),
]