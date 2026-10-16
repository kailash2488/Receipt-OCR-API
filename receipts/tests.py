import os
import io
import datetime
from decimal import Decimal
from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from receipts.models import Receipt, ReceiptItem
from receipts.services.parser_service import ReceiptParser
from receipts.services.ocr_service import OCRService
from receipts.services.analytics_service import AnalyticsService


def create_dummy_image(name="test_receipt.png") -> SimpleUploadedFile:
    file_obj = io.BytesIO()
    image = Image.new("RGB", (300, 400), color=(255, 255, 255))
    image.save(file_obj, format="PNG")
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/png")


class ReceiptParserTests(TestCase):
    def setUp(self):
        self.sample_text = (
            "BLUE BOTTLE COFFEE #402\n"
            "315 LINDEN ST, SAN FRANCISCO\n"
            "TEL: 415-555-0143\n"
            "DATE: 2024-11-20 09:15\n"
            "------------------------\n"
            "1 LATTE             $5.50\n"
            "2 CROISSANT         $7.00\n"
            "------------------------\n"
            "SUBTOTAL:          $12.50\n"
            "TAX:                $1.10\n"
            "TIP:                $2.00\n"
            "TOTAL:             $15.60\n"
            "PAYMENT: VISA 9841\n"
        )

    def test_merchant_extraction(self):
        lines = [line.strip() for line in self.sample_text.splitlines() if line.strip()]
        merchant = ReceiptParser.extract_merchant(lines)
        self.assertIn("BLUE BOTTLE COFFEE", merchant)

    def test_date_extraction(self):
        date = ReceiptParser.extract_date(self.sample_text)
        self.assertEqual(date, datetime.date(2024, 11, 20))

    def test_date_extraction_word_month(self):
        text = "Order Placed on Oct 15, 2024 at 12:00"
        date = ReceiptParser.extract_date(text)
        self.assertEqual(date, datetime.date(2024, 10, 15))

    def test_amounts_extraction(self):
        lines = [line.strip() for line in self.sample_text.splitlines() if line.strip()]
        amounts = ReceiptParser.extract_amounts(lines, self.sample_text)
        self.assertEqual(amounts["total"], Decimal("15.60"))
        self.assertEqual(amounts["subtotal"], Decimal("12.50"))
        self.assertEqual(amounts["tax"], Decimal("1.10"))
        self.assertEqual(amounts["tip"], Decimal("2.00"))

    def test_currency_and_payment(self):
        currency = ReceiptParser.extract_currency(self.sample_text)
        payment = ReceiptParser.extract_payment_method(self.sample_text)
        self.assertEqual(currency, "USD")
        self.assertEqual(payment, "VISA")

    def test_line_items_extraction(self):
        lines = [line.strip() for line in self.sample_text.splitlines() if line.strip()]
        items = ReceiptParser.extract_line_items(lines)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["description"], "LATTE")
        self.assertEqual(items[0]["total_price"], Decimal("5.50"))
        self.assertEqual(items[1]["description"], "CROISSANT")
        self.assertEqual(items[1]["quantity"], 2)

    def test_categorization(self):
        cat = ReceiptParser.categorize("Blue Bottle Coffee", [], self.sample_text)
        self.assertEqual(cat, "DINING")

        grocery_text = "WHOLE FOODS MARKET\nORGANIC APPLES $3.99\nTOTAL: $3.99"
        cat_grocery = ReceiptParser.categorize("Whole Foods Market", [], grocery_text)
        self.assertEqual(cat_grocery, "GROCERIES")


class OCRServiceTests(TestCase):
    def test_image_preprocessing(self):
        img = Image.new("RGB", (200, 200), color=(200, 200, 200))
        processed = OCRService.preprocess_image(img)
        self.assertEqual(processed.mode, "L")
        # Ensure image was upscaled for optimal resolution
        self.assertGreaterEqual(processed.size[0], 1200)

    def test_fallback_ocr(self):
        dummy_file = create_dummy_image("starbucks_coffee_test.png")
        temp_path = f"/tmp/{dummy_file.name}"
        with open(temp_path, "wb") as f:
            f.write(dummy_file.read())

        try:
            result = OCRService.extract_text(temp_path)
            self.assertIn("STARBUCKS", result["raw_text"])
            self.assertGreater(result["confidence"], 50.0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class ReceiptAPITests(APITestCase):
    def setUp(self):
        self.dummy_image = create_dummy_image("starbucks_sample.png")

    def test_health_check_endpoint(self):
        url = reverse("health-check")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["version"], "1.0.0")

    def test_dashboard_view(self):
        url = reverse("dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Receipt OCR")

    def test_create_and_process_receipt(self):
        url = reverse("receipt-list")
        response = self.client.post(
            url,
            {"image": self.dummy_image, "auto_process": True},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertIsNotNone(response.data["total_amount"])
        self.assertGreater(len(response.data["items"]), 0)

        # Check in DB
        receipt_id = response.data["id"]
        receipt = Receipt.objects.get(id=receipt_id)
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertGreater(receipt.items.count(), 0)

    def test_stateless_extract_endpoint(self):
        url = reverse("receipt-extract")
        dummy = create_dummy_image("whole_foods_sample.png")
        response = self.client.post(url, {"image": dummy}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("parsed_data", response.data)
        self.assertIn("merchant_name", response.data["parsed_data"])
        self.assertIn("raw_text", response.data)

    def test_analytics_endpoint(self):
        # Create completed receipts
        Receipt.objects.create(
            merchant_name="Store A",
            total_amount=Decimal("50.00"),
            transaction_date=datetime.date(2024, 10, 1),
            category="DINING",
            status="COMPLETED"
        )
        Receipt.objects.create(
            merchant_name="Store B",
            total_amount=Decimal("150.00"),
            transaction_date=datetime.date(2024, 10, 5),
            category="GROCERIES",
            status="COMPLETED"
        )

        url = reverse("receipt-analytics")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_spent"], 200.0)
        self.assertEqual(response.data["total_receipts"], 2)
        self.assertEqual(response.data["average_transaction"], 100.0)
        self.assertEqual(len(response.data["by_category"]), 2)

    def test_export_csv_and_json(self):
        Receipt.objects.create(
            merchant_name="Export Store",
            total_amount=Decimal("42.50"),
            transaction_date=datetime.date(2024, 9, 15),
            category="RETAIL",
            status="COMPLETED"
        )
        export_url = reverse("receipt-export")

        # CSV format
        resp_csv = self.client.get(f"{export_url}?export_format=csv")
        self.assertEqual(resp_csv.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_csv["Content-Type"], "text/csv")
        self.assertIn(b"Export Store", resp_csv.content)

        # JSON format
        resp_json = self.client.get(f"{export_url}?export_format=json")
        self.assertEqual(resp_json.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_json.data), 1)
        self.assertEqual(resp_json.data[0]["merchant_name"], "Export Store")

    def test_reprocess_receipt(self):
        receipt = Receipt.objects.create(
            image=self.dummy_image,
            status="PENDING"
        )
        url = reverse("receipt-reprocess", kwargs={"pk": receipt.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "COMPLETED")
