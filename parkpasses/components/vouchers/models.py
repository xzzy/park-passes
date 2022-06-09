"""
    This module contains the models required for implimenting vouchers
"""
from django.db import models
from ledger_api_client.ledger_models import EmailUserRO as EmailUser


class Voucher(models.Model):
    """A class to represent a voucher"""

    purchaser = models.ForeignKey(
        EmailUser, on_delete=models.PROTECT, blank=True, null=True
    )
    purchaser_name = models.CharField(max_length=50, null=False, blank=False)
    purchaser_email = models.EmailField(null=False, blank=False)
    recipient_name = models.CharField(max_length=50, null=False, blank=False)
    recipient_email = models.EmailField(null=False, blank=False)
    datetime_to_email = models.DateTimeField(null=False)
    personal_message = models.TextField(null=False)
    amount = models.DecimalField(
        max_digits=7, decimal_places=2, blank=False, null=False
    )
    expiry = models.DateTimeField(null=False)
    code = models.CharField(max_length=10)
    pin = models.DecimalField(max_digits=6, decimal_places=0, blank=False, null=False)
    NEW = "N"
    DELIVERED = "D"
    NOT_DELIVERED = "ND"
    PROCESSING_STATUS_CHOICES = [
        (NEW, "New"),
        (DELIVERED, "Delivered"),
        (NOT_DELIVERED, "Not Delivered"),
    ]
    processing_status = models.CharField(
        max_length=2,
        choices=PROCESSING_STATUS_CHOICES,
        default=NEW,
    )


class VoucherTransaction(models.Model):
    """A class to represent a voucher transaction"""

    voucher = models.ForeignKey(Voucher, on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=7, decimal_places=2, blank=False, null=False
    )
