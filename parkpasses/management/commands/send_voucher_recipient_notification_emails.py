"""
This management commands sends emails to customers who have had a voucher purchased
for them on the date that the purchaser specified.

Usage: ./manage.sh send_voucher_recipient_notification_emails
        (this command should be run by a cron job or task runner not manually)

"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

from parkpasses.components.vouchers.models import Voucher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sends any voucher emails that are due to be sent on the day the command is run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--test",
            action="store_true",
            help="Delete poll instead of closing it",
        )

    def handle(self, *args, **options):
        no_replay_email_user, created = EmailUser.objects.get_or_create(
            email=settings.NO_REPLY_EMAIL, password=""
        )
        today = timezone.now().date()
        vouchers = Voucher.objects.filter(
            datetime_to_email__date=today,
            processing_status__in=[Voucher.NEW, Voucher.NOT_DELIVERED],
        )
        if options["test"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {len(vouchers)} vouchers that would be sent to their recipients today {today}"
                )
            )
        for voucher in vouchers:
            if options["test"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"TEST: pretending to call send_voucher_recipient_notification_email on Voucher: {voucher}"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"TEST: pretending to call send_voucher_purchase_notification_email on Voucher: {voucher}"
                    )
                )
            else:
                voucher.send_voucher_recipient_notification_email()
                logger.info(
                    f"Notification email sent to recipient of Voucher: {voucher}"
                )
                voucher.send_voucher_purchase_notification_email()
                logger.info(
                    f"Notification email sent to purchaser of Voucher: {voucher}"
                )
