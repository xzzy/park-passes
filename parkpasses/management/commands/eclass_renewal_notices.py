import logging

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from parkpasses.components.approvals.email import (
    send_approval_eclass_renewal_email_notification,
)
from parkpasses.components.approvals.models import Approval

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send Approval renewal notice for eclass licence when approval is due to expire in \
    6 months and has not been extended."

    def handle(self, *args, **options):
        logger.info("Running command {}")

        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()
        expiry_notification_date = today + relativedelta(months=+6)
        application_type_name = "E Class"
        renewal_conditions = {
            "expiry_date__lte": expiry_notification_date,
            "renewal_sent": False,
            "replaced_by__isnull": True,
            "extended": False,
            "current_proposal__application_type__name": application_type_name,
        }
        logger.info(f"Running command {__name__}")

        # 2 month licences cannot be renewed
        qs = Approval.objects.filter(**renewal_conditions)
        logger.info(f"{qs}")
        for a in qs:
            if a.status == "current" or a.status == "suspended":
                try:
                    send_approval_eclass_renewal_email_notification(a)
                    a.renewal_sent = True
                    a.save()
                    logger.info(f"Renewal notice sent for Approval {a.id}")
                    updates.append(a.lodgement_number)
                except Exception as e:
                    err_msg = "Error sending renewal notice for Approval {}".format(
                        a.lodgement_number
                    )
                    logger.error(f"{err_msg}\n{str(e)}")
                    errors.append(err_msg)

        cmd_name = __name__.split(".")[-1].replace("_", " ").upper()
        err_str = (
            f'<strong style="color: red;">Errors: {len(errors)}</strong>'
            if len(errors) > 0
            else '<strong style="color: green;">Errors: 0</strong>'
        )
        msg = "<p>{} completed. Errors: {}. IDs updated: {}.</p>".format(
            cmd_name, err_str, updates
        )
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script