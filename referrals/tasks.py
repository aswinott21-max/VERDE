
import logging

from celery import shared_task

from referrals.models import Referral, ReferralReward
from referrals.services import (
    credit_referral_reward,
    process_referral,
    review_credited_referral_for_exceptions,
)

logger = logging.getLogger(__name__)


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
        referral, rewards = process_referral(referral_id)

        if referral.status == Referral.Status.ELIGIBLE:
            for reward in rewards:
                if reward.status != ReferralReward.Status.PENDING:
                    continue

                try:
                    credit_referral_reward(reward.pk)
                except Exception:
                    logger.exception(
                        "Failed to credit referral reward %s for referral %s",
                        reward.pk,
                        referral_id,
                    )

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
