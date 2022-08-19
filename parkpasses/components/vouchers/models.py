"""
    This module contains the models required for implimenting vouchers

    Each voucher may have one or more voucher transactions which allow
    vouchers to retain a positive balance so they can be used to pay
    for multiple seperate transactions.
"""
import datetime
import logging
import random
import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from parkpasses import settings
from parkpasses.components.passes.models import Pass
from parkpasses.components.vouchers.exceptions import (
    RemainingBalanceExceedsVoucherAmountException,
    RemainingVoucherBalanceLessThanZeroException,
)
from parkpasses.ledger_api_utils import retrieve_email_user

logger = logging.getLogger(__name__)


class VoucherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related("transactions")


class Voucher(models.Model):
    """A class to represent a voucher"""

    objects = VoucherManager()

    voucher_number = models.CharField(max_length=10, blank=True)
    purchaser = models.IntegerField(null=True, blank=True)  # EmailUserRO
    recipient_name = models.CharField(max_length=50, null=False, blank=False)
    recipient_email = models.EmailField(null=False, blank=False)
    datetime_to_email = models.DateTimeField(null=False)
    personal_message = models.TextField(null=False)
    amount = models.DecimalField(
        max_digits=7, decimal_places=2, blank=False, null=False
    )
    expiry = models.DateTimeField(null=False)
    code = models.CharField(unique=True, max_length=10)
    pin = models.DecimalField(max_digits=6, decimal_places=0, blank=False, null=False)
    datetime_purchased = models.DateTimeField(auto_now_add=True)
    datetime_updated = models.DateTimeField(auto_now=True)
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
    in_cart = models.BooleanField(null=False, blank=False, default=True)

    class Meta:
        app_label = "parkpasses"
        indexes = (models.Index(fields=["code"]),)

    def __str__(self):
        return f"{self.voucher_number} (${self.amount})"

    @property
    def get_purchaser(self):
        return retrieve_email_user(self.purchaser)

    @property
    def has_expired(self):
        if datetime.datetime.now() >= self.expiry:
            return True
        return False

    @property
    def remaining_balance(self):
        remaining_balance = self.amount
        for transaction in self.transactions.all():
            if transaction.credit > 0.00:
                remaining_balance += transaction.credit
            if transaction.debit > 0.00:
                remaining_balance -= transaction.debit
        if remaining_balance > self.amount:
            exception_message = (
                f"The remaining balance of {remaining_balance} for voucher with id"
                f"{self.id} is greater than the amount of the voucher."
            )
            logger.error(exception_message)
            raise RemainingBalanceExceedsVoucherAmountException(exception_message)
        if remaining_balance < 0.00:
            exception_message = (
                f"The remaining balance of {remaining_balance}"
                f"for voucher with id {self.id} is below 0.00."
            )
            logger.error(exception_message)
            raise RemainingVoucherBalanceLessThanZeroException(exception_message)
        return remaining_balance

    @classmethod
    def get_new_voucher_code(self):
        is_voucher_code_unique = False
        while not is_voucher_code_unique:
            voucher_code = str(uuid.uuid4()).upper()[:8]
            if not Voucher.objects.filter(code=voucher_code).exists():
                is_voucher_code_unique = True
        return voucher_code

    @classmethod
    def get_new_pin(self):
        return f"{random.randint(0,999999):06d}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.get_new_voucher_code()
        if not self.pin:
            self.pin = self.get_new_pin()
        if not self.expiry:
            self.expiry = datetime.datetime.now() + datetime.timedelta(
                days=settings.PARKPASSES_VOUCHER_EXPIRY_IN_DAYS
            )
        super().save(*args, **kwargs)


# Update the voucher_number field after saving
@receiver(post_save, sender=Voucher, dispatch_uid="update_voucher_number")
def update_voucher_number(sender, instance, **kwargs):
    if not instance.voucher_number:
        voucher_number = f"V{instance.pk:06d}"
        instance.voucher_number = voucher_number
        instance.save()


class VoucherTransactionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("voucher")


class VoucherTransaction(models.Model):
    """A class to represent a voucher transaction"""

    objects = VoucherTransactionManager()

    voucher = models.ForeignKey(
        Voucher, related_name="transactions", on_delete=models.PROTECT
    )
    park_pass = models.OneToOneField(
        Pass, on_delete=models.PROTECT, primary_key=True, null=False, blank=False
    )
    credit = models.DecimalField(
        max_digits=7, decimal_places=2, blank=False, null=False
    )
    debit = models.DecimalField(max_digits=7, decimal_places=2, blank=False, null=False)
    datetime_created = models.DateTimeField(auto_now_add=True)
    datetime_updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "parkpasses"

    def __str__(self):
        return f"Credit: {self.credit} | Debit:{self.debit}"