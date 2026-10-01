from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.views import redirect_to_login

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        #User must be logged in 
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="/admin-login/")

        #User must be an admin
        if not request.user.is_staff:
            return JsonResponse({"error": "You are not authorized to access this page"}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper