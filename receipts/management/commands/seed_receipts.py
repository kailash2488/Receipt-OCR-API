import os
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from receipts.models import Receipt
from receipts.views import ReceiptViewSet


class Command(BaseCommand):
    help = "Seed the database with sample receipts for demonstration and testing"

    def handle(self, *args, **options):
        sample_dir = settings.BASE_DIR / 'sample_receipts'
        sample_files = [
            "starbucks_coffee.png",
            "whole_foods_grocery.png",
            "capital_bistro_dinner.png"
        ]

        created_count = 0
        viewset = ReceiptViewSet()

        for filename in sample_files:
            file_path = sample_dir / filename
            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f"File not found: {file_path}"))
                continue

            with open(file_path, 'rb') as f:
                django_file = File(f, name=filename)
                receipt = Receipt.objects.create(
                    image=django_file,
                    original_filename=filename,
                    status='PROCESSING'
                )
                viewset._process_receipt(receipt)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Created receipt for {receipt.merchant_name or filename} (Total: {receipt.currency} {receipt.total_amount})"
                ))

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} sample receipts!"))
