
from celery import shared_task

from referrals.models import Referral
from referrals.services import (process_referral,review_credited_referral_for_exceptions,)


@shared_task
def process_pending_referrals():
    """Process referrals and flag post-reward order exceptions."""

    processed = 0
    reviewed = 0

    referral_ids = Referral.objects.filter(
        status__in=[
            Referral.Status.PENDING,
            Referral.Status.ELIGIBLE,
        ]
    ).values_list("id", flat=True)

    for referral_id in referral_ids.iterator():
        process_referral(referral_id)
        processed += 1

    rewarded_ids = Referral.objects.filter(
        status=Referral.Status.REWARDED,
    ).values_list("id", flat=True)

    for referral_id in rewarded_ids.iterator():
        referral = review_credited_referral_for_exceptions(referral_id)

        if referral.status == Referral.Status.MANUAL_REVIEW:
            reviewed += 1

    return {
        "processed": processed,
        "flagged_for_review": reviewed,
    }
