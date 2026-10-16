import uuid
from django.db import models
from django.core.validators import FileExtensionValidator


class Receipt(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Processing'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    CATEGORY_CHOICES = [
        ('DINING', 'Food & Dining'),
        ('GROCERIES', 'Groceries & Supermarket'),
        ('RETAIL', 'Retail & Shopping'),
        ('TRAVEL', 'Travel & Transportation'),
        ('UTILITIES', 'Utilities & Bills'),
        ('HEALTHCARE', 'Healthcare & Pharmacy'),
        ('ENTERTAINMENT', 'Entertainment'),
        ('OFFICE', 'Office Supplies'),
        ('OTHER', 'Other / General'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(
        upload_to='receipts/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff'])]
    )
    original_filename = models.CharField(max_length=255, blank=True)

    # Financial fields
    merchant_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    transaction_date = models.DateField(blank=True, null=True, db_index=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_index=True)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10, default='USD')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='OTHER', db_index=True)

    # OCR & Processing metadata
    raw_text = models.TextField(blank=True, help_text="Full unparsed OCR text")
    ocr_engine = models.CharField(max_length=50, default='auto')
    ocr_confidence = models.FloatField(default=0.0, help_text="Estimated confidence score (0-100)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant_name', 'transaction_date']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        merchant = self.merchant_name or "Unknown Merchant"
        total = f"{self.currency} {self.total_amount}" if self.total_amount is not None else "No Total"
        return f"{merchant} ({total}) - {self.created_at.strftime('%Y-%m-%d')}"


class ReceiptItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description} ({self.total_price})"
