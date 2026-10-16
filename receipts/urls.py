from django.urls import path, include
from rest_framework.routers import DefaultRouter
from receipts.views import ReceiptViewSet, HealthCheckView

router = DefaultRouter()
router.register(r'receipts', ReceiptViewSet, basename='receipt')

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('', include(router.urls)),
]
