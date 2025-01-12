"""
    This module contains the models required to impliment passes.

    - PassType (Local, Holiday, Annual etc.)
    - PassTypePricingWindow (A period of time that specific pricing can be specified)
    - PassTypePricingWindowOption (The duration options for a pass i.e. 5 days, 14 days, etc.)
    - Pass (The pass itself which contains the information required to generate the QR Code)
"""

import logging
import math
import os
from decimal import Decimal

import qrcode
from autoslug import AutoSlugField
from ckeditor.fields import RichTextField
from django.conf import settings
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone
from django_resized import ResizedImageField

from parkpasses.components.parks.models import ParkGroup
from parkpasses.components.passes.emails import PassEmails
from parkpasses.components.passes.exceptions import (
    MultipleDefaultPricingWindowsExist,
    NoDefaultPricingWindowExists,
    PassTemplateDoesNotExist,
    SendPassAutoRenewFailureNotificationEmailFailed,
    SendPassAutoRenewNotificationEmailFailed,
    SendPassAutoRenewSuccessNotificationEmailFailed,
    SendPassExpiredNotificationEmailFailed,
    SendPassExpiryNotificationEmailFailed,
    SendPassPurchasedEmailNotificationFailed,
    SendPassVehicleDetailsNotYetProvidedEmailNotificationFailed,
)
from parkpasses.components.passes.utils import PassUtils
from parkpasses.components.retailers.models import RetailerGroup
from parkpasses.ledger_api_utils import retrieve_email_user

logger = logging.getLogger(__name__)


def pass_type_image_path(instance, filename):
    """Stores the pass type images in a unique folder

    based on the content type and object_id
    """
    return f"{instance._meta.app_label}/{instance._meta.model.__name__}/{instance.name}/{filename}"


class PassType(models.Model):
    """A class to represent a pass type"""

    slug = AutoSlugField(unique=True, populate_from="display_name")
    image = ResizedImageField(
        size=[300, 150],
        quality=99,
        upload_to=pass_type_image_path,
        help_text="Ideal dimension for image are 300px (width) x 150px (height)",
        null=False,
        blank=False,
    )
    name = models.CharField(max_length=100)  # Name reserved for system use
    display_name = models.CharField(max_length=50, null=False, blank=False)
    description = RichTextField(null=True)
    oracle_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    display_order = models.SmallIntegerField(null=False, blank=False)
    display_retailer = models.BooleanField(null=False, blank=False, default=True)
    display_externally = models.BooleanField(null=False, blank=False, default=True)

    class Meta:
        app_label = "parkpasses"
        verbose_name = "Pass Type"
        verbose_name_plural = "Pass Types"
        ordering = ["id"]

    def __str__(self):
        return f"{self.display_name}"

    @classmethod
    def get_default_options_by_pass_type_id(self, pass_type_id):
        default_pricing_window = (
            PassTypePricingWindow.get_default_pricing_window_by_pass_type_id(
                pass_type_id
            )
        )
        options = PassTypePricingWindowOption.objects.filter(
            pricing_window=default_pricing_window
        ).count()
        if 0 == options:
            logger.critical(
                "CRITICAL: There are no options for pricing window : {} for pass type {}".format(
                    default_pricing_window.name, default_pricing_window.pass_type.name
                )
            )
            raise NoDefaultPricingWindowExists(
                "CRITICAL: There are no options for pricing window : {} for pass type {}".format(
                    default_pricing_window.name, default_pricing_window.pass_type.name
                )
            )
        else:
            return PassTypePricingWindowOption.objects.filter(
                pricing_window=default_pricing_window
            )


class PassTypePricingWindowManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("pass_type")


class PassTypePricingWindow(models.Model):
    """A class to represent a pass type pricing window

    The default pricing window for a pass type will have no expiry date
    The system will not allow for each pass type to have more than one
    default pricing window.
    """

    objects = PassTypePricingWindowManager()

    name = models.CharField(max_length=50, null=False, blank=False)
    pass_type = models.ForeignKey(
        PassType,
        on_delete=models.PROTECT,
        related_name="pricing_window",
        null=False,
        blank=False,
    )
    date_start = models.DateField()
    date_expiry = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "parkpasses"
        verbose_name = "Pricing Window"
        ordering = ["pass_type", "date_start", "date_expiry"]

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        if not self.date_expiry:
            default_pricing_window_count = (
                PassTypePricingWindow.objects.filter(
                    pass_type=self.pass_type,
                    date_expiry__isnull=True,
                )
                .exclude(pk=self.pk)
                .count()
            )
            if default_pricing_window_count > 0:
                raise ValidationError(
                    "There can only be one default pricing window for a pass type. \
                    Default pricing windows are those than have no expiry date."
                )
            else:
                if self.date_start > timezone.now().date():
                    raise ValidationError(
                        "The default pricing window start date must be in the past."
                    )
        else:
            if self.date_start >= self.date_expiry:
                raise ValidationError(
                    "The start date must occur before the expiry date."
                )
            if self.date_expiry.date() <= timezone.now().date():
                raise ValidationError("The expiry date must be in the future.")

        super().save(*args, **kwargs)

    @property
    def status(self):
        if not self.date_expiry:
            return "Current"
        if self.date_start > timezone.now().date():
            return "Future"
        elif self.date_expiry <= timezone.now().date():
            return "Expired"
        else:
            return "Current"

    @classmethod
    def get_default_pricing_window_by_pass_type_id(self, pass_type_id):
        try:
            default_pricing_window = PassTypePricingWindow.objects.get(
                pass_type__id=pass_type_id, name="Default"
            )
        except ObjectDoesNotExist:
            logger.critical(
                f"CRITICAL: There is no default pricing window for pass type with id: {pass_type_id}"
            )
            raise NoDefaultPricingWindowExists(
                f"CRITICAL: There is no default pricing window for pass type with id: {pass_type_id}"
            )
        except MultipleObjectsReturned:
            logger.critical(
                f"CRITICAL: There is more than one default pricing window for pass type with id: {pass_type_id}"
            )
            raise MultipleDefaultPricingWindowsExist(
                f"CRITICAL: There is more than one default pricing window for pass type with id: {pass_type_id}"
            )
        return default_pricing_window

    def is_valid(self):
        if not self.date_expiry and settings.PRICING_WINDOW_DEFAULT_NAME == self.name:
            """The default pricing window is always valid as it forms the template that other pricing windows
            must follow"""
            return True
        else:
            default_pricing_window = (
                PassTypePricingWindow.get_default_pricing_window_by_pass_type_id(
                    self.pass_type.id
                )
            )
            if sorted(list(self.options.values_list("name", "duration"))) == sorted(
                list(default_pricing_window.options.values_list("name", "duration"))
            ):
                return True
            else:
                return False


class PassTypePricingWindowOptionManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("pricing_window", "pricing_window__pass_type")
        )


class PassTypePricingWindowOption(models.Model):
    """A class to represent a pass type pricing window option"""

    objects = PassTypePricingWindowOptionManager()

    pricing_window = models.ForeignKey(
        PassTypePricingWindow, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=50)  # i.e. '5 days'
    duration = models.SmallIntegerField()  # in days i.e. 5, 14, 28, 365
    price = models.DecimalField(max_digits=7, decimal_places=2, blank=False, null=False)

    class Meta:
        app_label = "parkpasses"
        verbose_name = "Duration Option"
        verbose_name = "Duration Options"
        ordering = ["pricing_window", "price"]

    def __str__(self):
        return f"{self.pricing_window.pass_type.display_name} - {self.name} \
            (Pricing Window: {self.pricing_window.name})"

    @classmethod
    def get_current_options_by_pass_type_id(self, pass_type_id):
        try:
            pass_type = PassType.objects.get(id=pass_type_id)
        except ObjectDoesNotExist:
            logger.info(f"No Pass Type Exists with ID: {pass_type_id}.")
            return []

        pricing_windows_for_pass_count = PassTypePricingWindow.objects.filter(
            pass_type=pass_type
        ).count()

        if 0 == pricing_windows_for_pass_count:
            logger.critical(
                "CRITICAL: There is no default pricing window for Pass Type: {}.".format(
                    pass_type
                )
            )
            return []
        # If there is only one pricing window for the pass type it must be the default
        if 1 == PassTypePricingWindow.objects.filter(pass_type=pass_type).count():
            pricing_window = PassTypePricingWindow.objects.get(pass_type=pass_type)
        else:
            # Get any pricing windows that are currently valid excluding the default pricing window
            current_pricing_window_count = (
                PassTypePricingWindow.objects.exclude(date_expiry__isnull=True)
                .filter(
                    pass_type=pass_type,
                    date_start__lte=timezone.now(),
                    date_expiry__gte=timezone.now(),
                )
                .count()
            )

            # If there are none just get the default pricing window
            if 0 == current_pricing_window_count:
                pricing_window = PassTypePricingWindow.objects.get(
                    pass_type=pass_type, date_expiry__isnull=True
                )

            elif 1 == current_pricing_window_count:
                pricing_window = PassTypePricingWindow.objects.exclude(
                    date_expiry__isnull=True
                ).get(
                    pass_type=pass_type,
                    date_start__lte=timezone.now(),
                    date_expiry__gte=timezone.now(),
                )
            else:
                # When there are two or more currently valid pricing windows we return the window that
                # started the most recently And log a warning so that admins can be alerted to this.
                # Validation shouldn't allow this sitation to occur but ... just in case.
                logger.warning(
                    f"WARNING: There are more than one currently valid pricing windows for Pass Type: {pass_type}"
                )
                pricing_window = (
                    PassTypePricingWindow.objects.exclude(date_expiry__isnull=True)
                    .filter(
                        pass_type=pass_type,
                        date_start__lte=timezone.now(),
                        date_expiry__gte=timezone.now(),
                    )
                    .order_by("date_start")
                    .last()
                )

        return PassTypePricingWindowOption.objects.filter(pricing_window=pricing_window)

    @classmethod
    def get_default_options_by_pass_type_id(self, pass_type_id):
        return PassTypePricingWindowOption.objects.filter(
            pricing_window__name=settings.PRICING_WINDOW_DEFAULT_NAME,
            pricing_window__date_expiry__isnull=True,
            pricing_window__pass_type__id=pass_type_id,
        )


def pass_template_file_path(instance, filename):
    """Stores the pass template documents in a unique folder

    based on the content type and object_id
    """
    return f"{instance._meta.app_label}/{instance._meta.model.__name__}/{instance.version}/{filename}"


upload_protected_files_storage = FileSystemStorage(
    location=settings.PROTECTED_MEDIA_ROOT, base_url="/protected_media"
)


class PassTemplate(models.Model):
    """A class to represent a pass template

    The template file field will be the word document that is used as a template to generate a park pass.

    The highest version number will be the template that is used to generate passes.
    """

    template = models.FileField(
        upload_to=pass_template_file_path,
        storage=upload_protected_files_storage,
        null=False,
        blank=False,
    )
    version = models.SmallIntegerField(unique=True, null=False, blank=False)

    class Meta:
        app_label = "parkpasses"
        verbose_name = "Pass Template"
        verbose_name_plural = "Pass Templates"

    def __str__(self):
        return f"{self.template.name} (Version: {self.version}) (Size: {self.pretty_size()})"

    def pretty_size(self):
        size_bytes = self.template.size
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"


class PassManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "option",
                "option__pricing_window",
                "option__pricing_window__pass_type",
                "sold_via",
                "cancellation",
            )
        )


class Pass(models.Model):
    """A class to represent a pass"""

    objects = PassManager()

    NEW_SOUTH_WALES = "NSW"
    VICTORIA = "VIC"
    QUEENSLAND = "QLD"
    WESTERN_AUSTRALIA = "WA"
    SOUTH_AUSTRALIA = "SA"
    TASMANIA = "TAS"
    AUSTRALIAN_CAPITAL_TERRITORY = "ACT"
    NORTHERN_TERRITORY = "NT"

    STATE_CHOICES = [
        (NEW_SOUTH_WALES, "Western Australia"),
        (VICTORIA, "Victoria"),
        (QUEENSLAND, "Queensland"),
        (WESTERN_AUSTRALIA, "Western Australia"),
        (SOUTH_AUSTRALIA, "South Australia"),
        (TASMANIA, "Tasmania"),
        (AUSTRALIAN_CAPITAL_TERRITORY, "Australian Capital Territory"),
        (NORTHERN_TERRITORY, "Western Australia"),
    ]

    FUTURE = "FU"
    CURRENT = "CU"
    EXPIRED = "EX"
    CANCELLED = "CA"
    VALID = "VA"
    PROCESSING_STATUS_CHOICES = [
        (CANCELLED, "Cancelled"),
        (VALID, "Valid"),
    ]

    user = models.IntegerField(null=True, blank=True)  # EmailUserRO
    option = models.ForeignKey(PassTypePricingWindowOption, on_delete=models.PROTECT)
    pass_number = models.CharField(max_length=50, null=True, blank=True)
    first_name = models.CharField(max_length=50, null=False, blank=False)
    last_name = models.CharField(max_length=50, null=False, blank=False)
    email = models.EmailField(null=False, blank=False)
    mobile = models.CharField(max_length=10, null=False, blank=False, default="")
    company = models.CharField(max_length=50, null=True, blank=True)
    address_line_1 = models.CharField(max_length=100, null=True, blank=True)
    address_line_2 = models.CharField(max_length=100, null=True, blank=True)
    suburb = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(
        max_length=3,
        choices=STATE_CHOICES,
        default=WESTERN_AUSTRALIA,
        null=True,
        blank=True,
    )
    postcode = models.CharField(
        null=True,
        blank=True,
        max_length=4,
        validators=[
            MinLengthValidator(4, "Australian postcodes must contain 4 digits")
        ],
    )
    rac_member_number = models.CharField(max_length=20, null=True, blank=True)
    vehicle_registration_1 = models.CharField(max_length=10, null=True, blank=True)
    vehicle_registration_2 = models.CharField(max_length=10, null=True, blank=True)
    drivers_licence_number = models.CharField(max_length=11, null=True, blank=True)
    park_group = models.ForeignKey(
        ParkGroup, on_delete=models.PROTECT, null=True, blank=True
    )
    date_start = models.DateField(null=False, blank=False)
    date_expiry = models.DateField(null=False, blank=False)
    renew_automatically = models.BooleanField(null=False, blank=False, default=False)
    prevent_further_vehicle_updates = models.BooleanField(
        null=False, blank=False, default=False
    )
    park_pass_pdf = models.FileField(
        storage=upload_protected_files_storage, null=True, blank=True, max_length=500
    )
    processing_status = models.CharField(
        max_length=2, choices=PROCESSING_STATUS_CHOICES, null=True, blank=True
    )
    in_cart = models.BooleanField(null=False, blank=False, default=True)
    purchase_email_sent = models.BooleanField(null=False, blank=False, default=False)
    sold_via = models.ForeignKey(
        RetailerGroup, on_delete=models.PROTECT, null=True, blank=True
    )
    datetime_created = models.DateTimeField(auto_now_add=True)
    datetime_updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "parkpasses"
        verbose_name_plural = "Passes"
        ordering = ["-datetime_created"]

    def __str__(self):
        if self.pass_number:
            return f"{self.pass_number}"
        return "Pass number not yet assigned."

    @property
    def email_user(self):
        return retrieve_email_user(self.user)

    @property
    def pricing_window(self):
        return self.option.pricing_window.name

    @property
    def price(self):
        return self.option.price

    @property
    def pass_type(self):
        return self.option.pricing_window.pass_type.display_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def price_after_concession_applied(self):
        if hasattr(self, "concession_usage"):
            concession = self.concession_usage.concession
            discount_amount = concession.discount_as_amount(self.price)
            price_after_discount = self.price - discount_amount
            return price_after_discount
        return self.price

    @property
    def price_after_discount_code_applied(self):
        if hasattr(self, "discount_code_usage"):
            discount_code = self.discount_code_usage.discount_code
            discount_amount = discount_code.discount_as_amount(
                self.price_after_concession_applied
            )
            price_after_discount = self.price_after_concession_applied - discount_amount
            return price_after_discount
        return self.price_after_concession_applied

    @property
    def price_after_voucher_applied(self):
        if hasattr(self, "voucher_transaction"):
            voucher_transaction_balance = self.voucher_transaction.balance()
            return self.price_after_discount_code_applied + voucher_transaction_balance
        return self.price_after_discount_code_applied

    @property
    def price_after_all_discounts(self):
        """Convenience method that makes more descriptive sense"""
        return self.price_after_voucher_applied.quantize(Decimal("0.00"))

    @property
    def price_display(self):
        return f"${self.price_after_all_discounts}"

    @property
    def gst(self):
        gst_calcuation = Decimal(100 / (100 + int(settings.LEDGER_GST)))
        return Decimal(
            self.price_after_all_discounts
            - (self.price_after_all_discounts * gst_calcuation)
        ).quantize(Decimal("0.00"))

    @property
    def gst_display(self):
        return f"${self.gst}"

    @property
    def pro_rata_refund_amount_display(self):
        return f"${self.pro_rata_refund_amount()}"

    @property
    def status(self):
        if self.isCancelled:
            return Pass.CANCELLED
        elif self.date_start > timezone.now().date():
            return Pass.FUTURE
        elif self.date_expiry <= timezone.now().date():
            return Pass.EXPIRED
        else:
            return Pass.CURRENT

    @property
    def status_display(self):
        if self.isCancelled:
            return "Cancelled"
        elif self.date_start > timezone.now().date():
            return "Future"
        elif self.date_expiry <= timezone.now().date():
            return "Expired"
        else:
            return "Current"

    @property
    def isCancelled(self):
        if hasattr(self, "cancellation"):
            return True
        return False

    def pro_rata_refund_percentage(self):
        if self.date_start >= timezone.now().date():
            return 100
        if self.date_expiry <= timezone.now().date():
            return 0
        duration = self.option.duration
        delta = timezone.now().date() - self.date_start
        days_used = delta.days
        days_remaining = self.option.duration - days_used
        return round(days_remaining * 100 / duration)

    def pro_rata_refund_amount(self):
        amount = self.price_after_all_discounts * Decimal(
            self.pro_rata_refund_percentage() / 100
        )
        return Decimal(amount).quantize(Decimal("0.00"))

    def generate_qrcode(self):
        logger.info(f"Generating qr code for pass {self.pass_number}.")
        from parkpasses.components.passes.serializers import (
            ExternalQRCodePassSerializer,
        )

        qr = qrcode.QRCode()
        serializer = ExternalQRCodePassSerializer(self)
        # replace this line with the real encryption server at a later date
        logger.debug(f"serializer.data: {serializer.data}")
        encrypted_pass_data = self.imaginary_encryption_endpoint(serializer.data)
        qr.add_data(encrypted_pass_data)
        qr.make(fit=True)
        qr_image = qr.make_image(fill="black", back_color="white")
        qr_image_path = f"{settings.MEDIA_ROOT}/{self._meta.app_label}/"
        qr_image_path += f"{self._meta.model.__name__}/passes/{self.user}/{self.pk}"
        if not os.path.exists(qr_image_path):
            os.makedirs(qr_image_path)
        logger.info(
            f"Saving qr code for pass {self.pass_number} to {qr_image_path}/qr_image.png."
        )
        qr_image.save(f"{qr_image_path}/qr_image.png")
        logger.info(f"Qr code for pass {self.pass_number} saved.")
        return f"{qr_image_path}/qr_image.png"

    def generate_park_pass_pdf(self):
        logger.info(f"Generating pdf for pass {self.pass_number}.")
        if not PassTemplate.objects.count():
            logger.critical(
                "CRITICAL: The system can not find a Pass Template to use for generating park passes.",
            )
            raise PassTemplateDoesNotExist(
                "CRITICAL: The system can not find a Pass Template to use for generating park passes."
            )
        qr_code_path = self.generate_qrcode()
        pass_template = PassTemplate.objects.order_by("-version").first()
        pass_utils = PassUtils()
        pass_utils.generate_pass_pdf_from_docx_template(
            self, pass_template, qr_code_path
        )

    def imaginary_encryption_endpoint(self, json_pass_data):
        return json_pass_data

    def can_cancel_automatic_renewal(self):
        return self.date_expiry > timezone.now() + timezone.timedelta(days=1)

    def cancel_automatic_renewal(self):
        if not self.renew_automatically:
            raise ValidationError("This pass does not have automatic renewal enabled.")
        elif not self.can_cancel_automatic_renewal():
            raise ValidationError(
                "You must cancel automatic renewal of a pass at least 24 hours before the pass is due to renew."
            )
        else:
            self.renew_automatically = False
            self.save(update_fields=["renew_automatically"])
            logger.info(
                "Automatic renewal of pass {} has been cancelled.".format(
                    self.pass_number
                )
            )

    def set_processing_status(self):
        logger.info(f"Setting processing status for park pass: {self}.")
        if PassCancellation.objects.filter(park_pass=self).count():
            self.processing_status = Pass.CANCELLED
            logger.info(
                f"Processing status set as: {Pass.CANCELLED}.",
            )
        else:
            self.processing_status = Pass.VALID
            logger.info(
                f"Processing status set as: {Pass.VALID}.",
            )

    def save(self, *args, **kwargs):
        logger.info(f"Save pass called for park pass: {self}.")
        self.date_expiry = self.date_start + timezone.timedelta(
            days=self.option.duration
        )
        logger.info(f"Pass expiry date set as: {self.date_expiry}.")

        self.set_processing_status()

        # if self.user:
        #     logger.info(
        #         f"Pass has a user id: {self.user}",
        #     )
        #     email_user = self.email_user
        #     self.first_name = email_user.first_name
        #     self.last_name = email_user.last_name
        #     self.email = email_user.email
        #     logger.info(
        #         "Populated pass details from ledger email user.",
        #     )

        logger.info(f"Saving park pass: {self}")
        super().save(*args, **kwargs)
        logger.info(f"Park pass: {self} saved.")

        if not self.pass_number:
            logger.info(
                "Park pass does not yet have a pass number.",
            )
            self.pass_number = f"PP{self.pk:06d}"
            logger.info(
                f"Park pass assigned pass number: {self.pass_number}.",
            )

        if not Pass.CANCELLED == self.processing_status:
            if not self.in_cart:
                logger.info(
                    "Park pass has not been cancelled and is not in cart so generating park pass pdf.",
                )

                """Consider: Running generate_park_pass_pdf() with a message queue would be much better"""
                self.generate_park_pass_pdf()

                logger.info(
                    "Park pass pdf generated.",
                )

                if not self.purchase_email_sent:
                    logger.info(
                        "Park pass purchase email has not yet been sent.",
                    )
                    self.send_purchased_notification_email()
                    logger.info(
                        f"Pass purchased notification email sent for pass {self.pass_number}",
                    )
                    self.purchase_email_sent = True
                    logger.info(
                        "Assigning purchase email as sent.",
                    )

                else:
                    logger.info(
                        "Park pass purchase email has already been sent.",
                    )
                    self.send_updated_notification_email()
                    logger.info(
                        f"Pass update notification email sent for pass {self.pass_number}",
                    )

        logger.info(f"Updating park pass: {self}.")
        super().save(force_update=True)
        logger.info("Park pass updated.")

    def send_autorenew_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_autorenew_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_autorenew_notification_email(self)
        except Exception as e:
            raise SendPassAutoRenewNotificationEmailFailed(
                error_message.format(self.id, e)
            )

    def send_autorenew_success_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += "send_autorenew_success_notification_email for Pass with id {}. Exception {}"
        try:
            PassEmails.send_pass_autorenew_success_notification_email(self)
        except Exception as e:
            raise SendPassAutoRenewSuccessNotificationEmailFailed(
                error_message.format(self.id, e)
            )

    def send_autorenew_failure_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += "send_autorenew_failure_notification_email for Pass with id {}. Exception {}"
        try:
            PassEmails.send_pass_autorenew_failure_notification_email(self)
        except Exception as e:
            raise SendPassAutoRenewFailureNotificationEmailFailed(
                error_message.format(self.id, e)
            )

    def send_expiry_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_expiry_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_expiry_notification_email(self)
        except Exception as e:
            raise SendPassExpiryNotificationEmailFailed(
                error_message.format(self.id, e)
            )

    def send_expired_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_expired_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_expired_notification_email(self)
        except Exception as e:
            raise SendPassExpiredNotificationEmailFailed(
                error_message.format(self.id, e)
            )

    def send_purchased_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_purchased_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_purchased_notification_email(self)
        except Exception as e:
            raise SendPassPurchasedEmailNotificationFailed(
                error_message.format(self.id, e)
            )

    def send_updated_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_updated_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_updated_notification_email(self)
        except Exception as e:
            raise SendPassPurchasedEmailNotificationFailed(
                error_message.format(self.id, e)
            )

    def send_vehicle_details_not_yet_provided_notification_email(self):
        error_message = "An exception occured trying to run "
        error_message += (
            "send_purchased_notification_email for Pass with id {}. Exception {}"
        )
        try:
            PassEmails.send_pass_vehicle_details_not_yet_provided_notification_email(
                self
            )
        except Exception as e:
            raise SendPassVehicleDetailsNotYetProvidedEmailNotificationFailed(
                error_message.format(self.id, e)
            )


class PassCancellationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("park_pass")


class PassCancellation(models.Model):
    """A class to represent a pass cancellation

    A one to one related model to store the cancellation reason

    Also, will be able to have a list of files attached to it to justify/explain
    the cancellation"""

    objects = PassCancellationManager()

    park_pass = models.OneToOneField(
        Pass, on_delete=models.PROTECT, related_name="cancellation"
    )
    cancellation_reason = models.TextField(null=False, blank=False)
    datetime_cancelled = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "parkpasses"
        verbose_name_plural = "Pass Cancellations"

    def __str__(self):
        return f"Cancellation for Pass: {self.park_pass.pass_number}(Date Cancelled: {self.datetime_cancelled})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.park_pass.processing_status = Pass.CANCELLED
        self.park_pass.save()

    def delete(self, *args, **kwargs):
        """If the pass cancellation is deleted we automatically recalculate the status"""
        park_pass = self.park_pass
        deleted = super().delete()
        park_pass.set_processing_status()
        park_pass.save()
        return deleted
