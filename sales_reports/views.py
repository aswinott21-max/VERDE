from io import BytesIO

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render

from adminpanel.decorators import admin_required
from .services import get_sales_report,get_referral_summary



# Create your views here.

@admin_required
def sales_report_page(request):
    #Display sales reports for the selected date range

    #choose the report period and calculate its default dates
    today =timezone.localdate()
    period = request.GET.get("period","day")

    if period not in {"day", "week", "year", "custom"}:
        period = "day"

    if period =="week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:
        start_date = today
        end_date = today

    #use supplied dates only for a custom report
    error = None

    if period == "custom":
        start_date = parse_date(request.GET.get("start_date",""))
        end_date = parse_date(request.GET.get("end_date", ""))

        if not start_date or not end_date:
            error = "Please select both start date and end dates"
        elif start_date > end_date:
            error ="Start date cannot be after end date"

        if error:
            start_date = today
            end_date = today

    #reuse the central service for report calculations
    report = get_sales_report(start_date, end_date, period=period)

    context = {**report, "period" : period, "error":error,"referral_summery":get_referral_summary(),}
    #**report, - to unpack the dictionary returned by  get_sales_report()
    return render (request, "sales_reports/sales_report.html",context)

def download_sales_report_excel(request):
    #Download the sales report as an Excel workbook

    today = timezone.localdate()
    start_date = parse_date(request.GET.get("start_date", "")) or today
    end_date = parse_date(request.GET.get("end_date","")) or today

    if start_date > end_date:
        return HttpResponse("Start date cannot be after end date",status=400)
    report = get_sales_report(start_date,end_date)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales Report"

    sheet.append(["VERDÉ Sales Report"])
    sheet.append(["Start Date", start_date.isoformat()])
    sheet.append(["End Date", end_date.isoformat()])
    sheet.append([])
    sheet.append(["Metric", "Amount / Count"])
    sheet.append(["Sales Count", report["sales_count"]])
    sheet.append(["Gross Amount", float(report["gross_amount"])])
    sheet.append(["Discounts", float(report["discount_amount"])])
    sheet.append(["Order Amount", float(report["order_amount"])])
    sheet.append(["Coupon Discounts", float(report["coupon_discount"])])
    sheet.append(["Completed Refunds", float(report["refund_amount"])])
    sheet.append(["Net Revenue", float(report["net_revenue"])])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = (f'attachment; filename="sales_report_{start_date}_{end_date}.xlsx"')
    workbook.save(response)
    return response

@admin_required
def download_sales_report_pdf(request):
    #Download the sales report as a PDF
    today = timezone.localdate()
    start_date = parse_date(request.GET.get("start_date","")) or today
    end_date= parse_date(request.GET.get("end_date", "")) or today

    if start_date > end_date:
        return  HttpResponse("Start date cannot be after end date",status=400)

    report = get_sales_report(start_date,end_date)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)

    rows = [
        ["VERDÉ Sales Report", ""],
        ["Start Date", start_date.isoformat()],
        ["End Date", end_date.isoformat()],
        ["Sales Count", str(report["sales_count"])],
        ["Gross Amount", f'INR {report["gross_amount"]:.2f}'],
        ["Discounts", f'INR {report["discount_amount"]:.2f}'],
        ["Coupon Discounts", f'INR {report["coupon_discount"]:.2f}'],
        ["Order Amount", f'INR {report["order_amount"]:.2f}'],
        ["Completed Refunds", f'INR {report["refund_amount"]:.2f}'],
        ["Net Revenue", f'INR {report["net_revenue"]:.2f}'],
    ]

    table = Table(rows, colWidths=[220, 220])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#315B3E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    document.build([table])
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Context-Disposition"] = (f'attachmentl; filename="sales_report_{start_date}_{end_date}.pdf')
    return response
