
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.utils import timezone

from adminpanel.decorators import admin_required
from referrals.models import Referral, ReferralOffer


@never_cache
@admin_required
def admin_referrals_page(request):
    search = request.GET.get("search", "").strip()

    referrals = Referral.objects.select_related(
        "referrer",
        "referred_user",
        "referral_offer",
    ).order_by("-created_at")

    if search:
        referrals = referrals.filter(
            Q(referrer__full_name__icontains=search)
            | Q(referrer__email__icontains=search)
            | Q(referred_user__full_name__icontains=search)
            | Q(referred_user__email__icontains=search)
            | Q(referral_code__icontains=search)
            | Q(id__icontains=search)
        )

    paginator = Paginator(referrals, 10)
    referrals_page = paginator.get_page(request.GET.get("page"))

    active_offer = ReferralOffer.objects.filter(is_active=True).first()

    

    if request.method == "POST":

        if request.POST.get("action") == "save_review_note":
            referral_id = request.POST.get("referral_id", "").strip()
            note = request.POST.get("review_note", "").strip()

            if not note:
                messages.error(request, "Enter a review note.")
                return redirect("referrals:admin_referrals_page")

            try:
                with transaction.atomic():
                    referral = Referral.objects.select_for_update().get(
                        pk=referral_id,
                        status=Referral.Status.MANUAL_REVIEW,
                    )

                    timestamp = timezone.localtime().strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    reviewer = request.user.email or str(request.user)
                    entry = f"[Admin review: {timestamp} by {reviewer}] {note}"

                    existing = referral.disqualification_reason.strip()
                    referral.disqualification_reason = (
                        f"{existing}\n\n{entry}" if existing else entry
                    )
                    referral.save(
                        update_fields=[
                            "disqualification_reason",
                            "updated_at",
                        ]
                    )

                messages.success(request, "Review note saved.")

            except Referral.DoesNotExist:
                messages.error(
                    request,
                    "Manual-review referral not found.",
                )

            return redirect("referrals:admin_referrals_page")
        reward_amount = request.POST.get("reward_amount", "").strip()

        try:
            from decimal import Decimal, InvalidOperation

            amount = Decimal(reward_amount)

            if not amount.is_finite() or amount <= 0:
                raise InvalidOperation

            if amount.as_tuple().exponent < -2:
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                "Enter a valid reward amount greater than zero, "
                "with no more than two decimal places.",
            )
            return redirect("referrals:admin_referrals_page")

        with transaction.atomic():
            active_offer = ReferralOffer.objects.select_for_update().filter(
                is_active=True
            ).first()

            if active_offer:
                active_offer.reward_amount = amount
                active_offer.save(update_fields=["reward_amount", "updated_at"])
            else:
                ReferralOffer.objects.create(
                    reward_amount=amount,
                    is_active=True,
                )

        messages.success(request, "Global referral reward updated.")
        return redirect("referrals:admin_referrals_page")

    return render(
        request,
        "referrals/admin_referrals.html",
        {
            "referrals": referrals_page,
            "active_offer": active_offer,
            "search": search,
        },
    )
