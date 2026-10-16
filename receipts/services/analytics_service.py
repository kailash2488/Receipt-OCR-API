"""
Analytics Service: Aggregates receipt data for financial reporting,
expense tracking, category breakdown, and monthly trends.
"""

from django.db.models import Sum, Count, Avg, Max, Min
from django.db.models.functions import TruncMonth
from decimal import Decimal
from typing import Dict, Any, List
from receipts.models import Receipt


class AnalyticsService:
    @staticmethod
    def get_summary_metrics() -> Dict[str, Any]:
        """Calculates global expenditure totals, averages, and counts."""
        qs = Receipt.objects.filter(status='COMPLETED')

        aggregates = qs.aggregate(
            total_spent=Sum('total_amount'),
            avg_receipt=Avg('total_amount'),
            max_receipt=Max('total_amount'),
            min_receipt=Min('total_amount'),
            total_count=Count('id')
        )

        # Spending by category
        category_breakdown = list(
            qs.values('category')
            .annotate(
                total=Sum('total_amount'),
                count=Count('id')
            )
            .order_by('-total')
        )

        # Monthly expenditure trend
        monthly_trend = list(
            qs.exclude(transaction_date__isnull=True)
            .annotate(month=TruncMonth('transaction_date'))
            .values('month')
            .annotate(
                total=Sum('total_amount'),
                count=Count('id')
            )
            .order_by('month')
        )

        # Top merchants by spend
        top_merchants = list(
            qs.exclude(merchant_name__isnull=True)
            .values('merchant_name')
            .annotate(
                total=Sum('total_amount'),
                count=Count('id')
            )
            .order_by('-total')[:5]
        )

        return {
            "total_spent": float(aggregates['total_spent'] or 0),
            "average_transaction": round(float(aggregates['avg_receipt'] or 0), 2),
            "max_transaction": float(aggregates['max_receipt'] or 0),
            "total_receipts": aggregates['total_count'],
            "by_category": [
                {
                    "category": item['category'],
                    "total": float(item['total'] or 0),
                    "count": item['count']
                }
                for item in category_breakdown
            ],
            "monthly_trend": [
                {
                    "month": item['month'].strftime('%Y-%m') if item['month'] else "Unknown",
                    "total": float(item['total'] or 0),
                    "count": item['count']
                }
                for item in monthly_trend
            ],
            "top_merchants": [
                {
                    "merchant": item['merchant_name'],
                    "total": float(item['total'] or 0),
                    "count": item['count']
                }
                for item in top_merchants
            ]
        }
