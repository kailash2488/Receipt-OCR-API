"""
Receipts API Views & ViewSets.
"""

import csv
import logging
from django.http import HttpResponse
from django.views.generic import TemplateView
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from receipts.models import Receipt, ReceiptItem
from receipts.serializers import (
    ReceiptSerializer,
    ReceiptUploadSerializer,
    StatelessExtractionSerializer,
    AnalyticsResponseSerializer,
    HealthCheckSerializer,
)
from receipts.services.ocr_service import OCRService
from receipts.services.parser_service import ReceiptParser
from receipts.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class ReceiptViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Receipts with integrated OCR and line-item extraction.
    """
    queryset = Receipt.objects.all().prefetch_related('items')
    serializer_class = ReceiptSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Category filter
        category = params.get('category')
        if category:
            qs = qs.filter(category=category.upper())

        # Status filter
        stat = params.get('status')
        if stat:
            qs = qs.filter(status=stat.upper())

        # Merchant search
        merchant = params.get('merchant')
        if merchant:
            qs = qs.filter(merchant_name__icontains=merchant)

        # Date range filters
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(transaction_date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(transaction_date__lte=date_to)

        # Amount range filters
        min_amount = params.get('min_amount')
        if min_amount:
            qs = qs.filter(total_amount__gte=min_amount)

        max_amount = params.get('max_amount')
        if max_amount:
            qs = qs.filter(total_amount__lte=max_amount)

        # Ordering
        ordering = params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'transaction_date', '-transaction_date', 'total_amount', '-total_amount']:
            qs = qs.order_by(ordering)

        return qs

    @extend_schema(
        request=ReceiptUploadSerializer,
        responses={201: ReceiptSerializer},
        description="Upload a receipt image. OCR and financial extraction will execute automatically."
    )
    def create(self, request, *args, **kwargs):
        upload_serializer = ReceiptUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        image_file = upload_serializer.validated_data['image']
        auto_process = upload_serializer.validated_data.get('auto_process', True)

        receipt = Receipt.objects.create(
            image=image_file,
            original_filename=image_file.name,
            status='PROCESSING' if auto_process else 'PENDING'
        )

        if auto_process:
            self._process_receipt(receipt)

        serializer = self.get_serializer(receipt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _process_receipt(self, receipt: Receipt):
        """Runs the OCR engine and parser pipeline, populating fields."""
        try:
            # 1. OCR Extraction
            ocr_result = OCRService.extract_text(receipt.image.path)
            raw_text = ocr_result.get("raw_text", "")

            receipt.raw_text = raw_text
            receipt.ocr_engine = ocr_result.get("engine", "unknown")
            receipt.ocr_confidence = ocr_result.get("confidence", 0.0)

            # 2. Heuristic Data Parsing
            parsed = ReceiptParser.parse(raw_text)

            receipt.merchant_name = parsed.get("merchant_name")
            receipt.transaction_date = parsed.get("transaction_date")
            receipt.total_amount = parsed.get("total_amount")
            receipt.subtotal_amount = parsed.get("subtotal_amount")
            receipt.tax_amount = parsed.get("tax_amount")
            receipt.tip_amount = parsed.get("tip_amount")
            receipt.currency = parsed.get("currency", "USD")
            receipt.payment_method = parsed.get("payment_method")
            receipt.category = parsed.get("category", "OTHER")

            # 3. Create line items
            receipt.items.all().delete()
            for item in parsed.get("items", []):
                ReceiptItem.objects.create(
                    receipt=receipt,
                    description=item["description"],
                    quantity=item.get("quantity", 1),
                    unit_price=item.get("unit_price"),
                    total_price=item.get("total_price")
                )

            receipt.status = 'COMPLETED'
            receipt.error_message = ''
        except Exception as e:
            logger.exception(f"Error processing receipt {receipt.id}: {e}")
            receipt.status = 'FAILED'
            receipt.error_message = str(e)

        receipt.save()

    @extend_schema(
        request=StatelessExtractionSerializer,
        description="Stateless OCR extraction: Upload an image to parse and receive JSON without persisting anything to the database."
    )
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def extract(self, request):
        serializer = StatelessExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data['image']
        
        # Save temporarily for processing
        import tempfile
        import os
        suffix = os.path.splitext(image_file.name)[-1] or '.jpg'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in image_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            ocr_result = OCRService.extract_text(tmp_path)
            raw_text = ocr_result.get("raw_text", "")
            parsed = ReceiptParser.parse(raw_text)

            response_data = {
                "ocr_engine": ocr_result.get("engine"),
                "confidence": ocr_result.get("confidence"),
                "raw_text": raw_text,
                "parsed_data": parsed,
            }
            return Response(response_data, status=status.HTTP_200_OK)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @extend_schema(description="Reprocess a receipt image with OCR and parser pipelines.")
    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        receipt = self.get_object()
        receipt.status = 'PROCESSING'
        receipt.save()

        self._process_receipt(receipt)
        return Response(self.get_serializer(receipt).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: AnalyticsResponseSerializer},
        description="Get aggregated expense statistics, category breakdown, and monthly spend trends."
    )
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        metrics = AnalyticsService.get_summary_metrics()
        return Response(metrics, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter('export_format', OpenApiTypes.STR, description='Export format: csv or json', required=False)
        ],
        description="Export all receipts as a downloadable CSV or JSON file."
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        fmt = (request.query_params.get('export_format') or request.query_params.get('format') or 'csv').lower()
        receipts = self.get_queryset()

        if fmt == 'json':
            serializer = self.get_serializer(receipts, many=True)
            return Response(serializer.data)

        # Default CSV export
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="receipts_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Merchant', 'Date', 'Total Amount', 'Currency', 'Category',
            'Payment Method', 'OCR Confidence', 'Status', 'Created At'
        ])

        for r in receipts:
            writer.writerow([
                str(r.id),
                r.merchant_name or '',
                r.transaction_date.strftime('%Y-%m-%d') if r.transaction_date else '',
                r.total_amount or '',
                r.currency,
                r.category,
                r.payment_method or '',
                r.ocr_confidence,
                r.status,
                r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])

        return response


class HealthCheckView(APIView):
    """System health check and engine capability reporting."""
    @extend_schema(
        responses={200: HealthCheckSerializer},
        description="Health check and engine status."
    )
    def get(self, request):
        import shutil
        has_tesseract = bool(shutil.which('tesseract'))
        return Response({
            "status": "healthy",
            "version": "1.0.0",
            "tesseract_installed": has_tesseract,
            "active_ocr_engine": "tesseract" if has_tesseract else "heuristic_fallback",
        }, status=status.HTTP_200_OK)


class DashboardView(TemplateView):
    """Interactive Web Demo UI."""
    template_name = 'dashboard.html'
