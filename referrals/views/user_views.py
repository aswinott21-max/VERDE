
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from referrals.models import Referral, ReferralReward,ReferralOffer
from referrals.services import generate_referral_code


@login_required
def user_referrals_page(request):
    # Load the logged-in customer's referral information
    referral_code = generate_referral_code(request.user)

    referrals = Referral.objects.filter(
        referrer=request.user
    ).select_related(
        "referred_user"
    ).order_by("-created_at")

    active_offer = ReferralOffer.objects.filter(is_active=True).first()
    
    rewards = ReferralReward.objects.filter(recipient=request.user).select_related("referral").order_by("-created_at")

    # Calculate dashboard metrics from actual referral and reward records
    referral_stats = referrals.aggregate(
        total=Count("id"),
        successful=Count(
            "id",
            filter=Q(status=Referral.Status.REWARDED),
        ),
        pending=Count(
            "id",
            filter=Q(
                status__in=[
                    Referral.Status.PENDING,
                    Referral.Status.ELIGIBLE,
                ]
            ),
        ),
    )

    earned_amount = rewards.filter(status=ReferralReward.Status.CREDITED).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]


    return render(
        request,
        "referrals/user_referrals.html",
        {
            "referral_code": referral_code.code,
            "referrals": referrals,
            "referrals": referrals,
            "active_offer": active_offer,
            "rewards": rewards,
            "referral_stats": referral_stats,
            "earned_amount": earned_amount,
        },
    )
