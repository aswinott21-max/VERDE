from django.shortcuts import render
from django.views.decorators.cache import never_cache
from ..decorators import admin_required

@never_cache
@admin_required
def admin_dashboard_page(request):

    return render(request,"adminpanel/admin_dashboard.html")