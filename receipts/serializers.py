"""
Serializers for Receipt OCR API.
"""

from rest_framework import serializers
from receipts.models import Receipt, ReceiptItem


class ReceiptItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total_price']


class ReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptItemSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Receipt
        fields = [
            'id',
            'image',
            'original_filename',
            'merchant_name',
            'transaction_date',
            'total_amount',
            'subtotal_amount',
            'tax_amount',
            'tip_amount',
            'currency',
            'payment_method',
            'category',
            'category_display',
            'raw_text',
            'ocr_engine',
            'ocr_confidence',
            'status',
            'status_display',
            'error_message',
            'created_at',
            'updated_at',
            'items',
        ]
        read_only_fields = [
            'id',
            'raw_text',
            'ocr_engine',
            'ocr_confidence',
            'status',
            'error_message',
            'created_at',
            'updated_at',
        ]


class ReceiptUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True, help_text="Receipt image file (JPEG, PNG, WEBP)")
    auto_process = serializers.BooleanField(default=True, required=False, help_text="Immediately run OCR and extraction")


class StatelessExtractionSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True, help_text="Receipt image to extract data from without database storage")


class CategoryAnalyticsItemSerializer(serializers.Serializer):
    category = serializers.CharField()
    total = serializers.FloatField()
    count = serializers.IntegerField()


class MonthlyTrendItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    total = serializers.FloatField()
    count = serializers.IntegerField()


class MerchantSpendItemSerializer(serializers.Serializer):
    merchant = serializers.CharField()
    total = serializers.FloatField()
    count = serializers.IntegerField()


class AnalyticsResponseSerializer(serializers.Serializer):
    total_spent = serializers.FloatField()
    average_transaction = serializers.FloatField()
    max_transaction = serializers.FloatField()
    total_receipts = serializers.IntegerField()
    by_category = CategoryAnalyticsItemSerializer(many=True)
    monthly_trend = MonthlyTrendItemSerializer(many=True)
    top_merchants = MerchantSpendItemSerializer(many=True)


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()
    tesseract_installed = serializers.BooleanField()
    active_ocr_engine = serializers.CharField()

