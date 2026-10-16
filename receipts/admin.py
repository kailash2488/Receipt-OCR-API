from django.contrib import admin
from receipts.models import Receipt, ReceiptItem


class ReceiptItemInline(admin.TabularInline):
    model = ReceiptItem
    extra = 0
    fields = ['description', 'quantity', 'unit_price', 'total_price']


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'merchant_name', 'transaction_date', 'total_amount',
        'currency', 'category', 'status', 'ocr_confidence', 'created_at'
    ]
    list_filter = ['status', 'category', 'currency', 'ocr_engine', 'created_at']
    search_fields = ['merchant_name', 'raw_text', 'id']
    readonly_fields = ['id', 'ocr_confidence', 'ocr_engine', 'raw_text', 'created_at', 'updated_at']
    inlines = [ReceiptItemInline]
    date_hierarchy = 'created_at'


@admin.register(ReceiptItem)
class ReceiptItemAdmin(admin.ModelAdmin):
    list_display = ['description', 'receipt', 'quantity', 'unit_price', 'total_price']
    search_fields = ['description', 'receipt__merchant_name']
