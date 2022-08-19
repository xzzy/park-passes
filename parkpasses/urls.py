from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.urls import path
from ledger_api_client.urls import urlpatterns as ledger_patterns
from rest_framework import routers

from parkpasses import views
from parkpasses.admin import admin
from parkpasses.components.cart.api import LedgerCheckoutView
from parkpasses.components.cart.views import CartView, CheckoutSuccessView
from parkpasses.components.help.views import ParkPassesHelpView

# API patterns
router = routers.DefaultRouter()

api_patterns = [
    url(r"^api/", include(router.urls)),
]

# URL Patterns
urlpatterns = [
    # ========================================================================== External Public
    url(r"^$", views.ParkPassesRoutingView.as_view(), name="home"),
    url(r"^help/", ParkPassesHelpView.as_view(), name="help"),
    url(r"^contact/", views.ParkPassesContactView.as_view(), name="ds_contact"),
    url(r"^faq/", views.ParkPassesFAQView.as_view(), name="faq"),
    url(
        r"^further_info/",
        views.ParkPassesFurtherInformationView.as_view(),
        name="ds_further_info",
    ),
    # ========================================================================== External Authenticated
    url(r"^cart/", CartView.as_view(), name="cart"),
    url(r"^ledger-checkout/", LedgerCheckoutView.as_view(), name="ledger-checkout"),
    url(
        r"checkout-success/(?P<uuid>.+)/",
        CheckoutSuccessView.as_view(),
        name="checkout-success",
    ),
    url(r"^external/", views.ExternalView.as_view(), name="external"),
    url(r"^account/$", views.ExternalView.as_view(), name="manage-account"),
    url(r"^profiles/", views.ExternalView.as_view(), name="manage-profiles"),
    # ========================================================================== Internal
    url(r"^internal/", views.InternalView.as_view(), name="internal"),
    url(r"^internal/vouchers/", views.InternalView.as_view(), name="internal-vouchers"),
    url(
        r"^internal/discount-codes/",
        views.InternalView.as_view(),
        name="internal-discount-codes",
    ),
    # ========================================================================== Retailer
    url(r"^retailer/", views.RetailerView.as_view(), name="retailer"),
    # ========================================================================== Component API end-points
    url(r"api/passes/", include("parkpasses.components.passes.urls")),
    url(r"api/parks/", include("parkpasses.components.parks.urls")),
    url(r"api/concessions/", include("parkpasses.components.concessions.urls")),
    url(r"api/discount-codes/", include("parkpasses.components.discount_codes.urls")),
    url(r"api/vouchers/", include("parkpasses.components.vouchers.urls")),
    url(r"api/cart/", include("parkpasses.components.cart.urls")),
    url(r"api/help/", include("parkpasses.components.help.urls")),
    url(r"api/orders/", include("parkpasses.components.orders.urls")),
    url(r"api/users/", include("parkpasses.components.users.urls")),
    # ========================================================================== Management Commands
    url(
        r"^mgt-commands/$", views.ManagementCommandsView.as_view(), name="mgt-commands"
    ),
    # ========================================================================== Admin
    path(r"admin/", admin.site.urls),
] + ledger_patterns


if settings.DEBUG:  # Serve media locally in development.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    urlpatterns += [
        # ...
        path("__debug__/", include("debug_toolbar.urls")),
    ]