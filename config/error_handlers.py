
from django.http import HttpResponseServerError
from django.shortcuts import render


# Admin URL prefixes used to select the admin error-page templates.
ADMIN_PATH_PREFIXES = (
    "/admin/",
    "/admin-login/",
    "/adminpanel/",
    "/admin-sales-report/",
    "/admin-settings/",
    "/catalog/admin/",
    "/products/admin/",
    "/orders/admin/",
    "/coupons/admin/",
    "/referrals/admin/",
)


def _is_admin_request(request):
    # Check the requested path so even unmatched admin URLs use admin pages.
    path = request.path_info

    return any(
        path == prefix.rstrip("/") or path.startswith(prefix)
        for prefix in ADMIN_PATH_PREFIXES
    )


def _render_error(request, status_code):
    # Select the correct template based on whether the request is admin-facing.
    if _is_admin_request(request):
        template_name = f"adminpanel/errors/{status_code}.html"
    else:
        template_name = f"{status_code}.html"

    return render(request, template_name, status=status_code)


def handler400(request, exception):
    return _render_error(request, 400)


def handler403(request, exception):
    if _is_admin_request(request) and getattr(request.user, "is_staff", False):
        return _render_error(request, 403)

    return render(request, "403.html", status=403)


def handler404(request, exception):
    return _render_error(request, 404)


def handler500(request):
    try:
        return _render_error(request, 500)
    except Exception:
        # Keep a minimal response if the full error template cannot render.
        return HttpResponseServerError(
            "Something went wrong. Please try again later."
        )
