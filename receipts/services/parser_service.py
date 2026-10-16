"""
Financial & Receipt Parser Service:
Extracts structured financial metadata, line items, and merchant information
from unstructured OCR text using heuristic NLP and multi-pass regular expressions.
"""

import re
import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Tuple


class ReceiptParser:
    # Currencies and symbols
    CURRENCY_SYMBOLS = {
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '₹': 'INR',
        '¥': 'JPY',
        'USD': 'USD',
        'EUR': 'EUR',
        'GBP': 'GBP',
        'CAD': 'CAD',
        'AUD': 'AUD',
        'INR': 'INR',
    }

    # Keyword categorization mappings
    CATEGORY_KEYWORDS = {
        'DINING': [
            'coffee', 'cafe', 'café', 'restaurant', 'bistro', 'bar', 'grill', 'pizza',
            'burger', 'bakery', 'starbucks', 'diner', 'kitchen', 'sushi', 'taco',
            'steakhouse', 'brewery', 'subway', 'mcdonald', 'chipotle', 'food'
        ],
        'GROCERIES': [
            'grocery', 'supermarket', 'market', 'foods', 'trader joe', 'whole foods',
            'safeway', 'kroger', 'aldi', 'costco', 'walmart neighborhood', 'bakery',
            'produce', 'deli', 'dairy', 'provisions'
        ],
        'TRAVEL': [
            'uber', 'lyft', 'taxi', 'airline', 'airways', 'flight', 'rail', 'train',
            'metro', 'transit', 'shell', 'chevron', 'exxon', 'bp', 'mobil', 'gas',
            'fuel', 'parking', 'hotel', 'motel', 'airbnb'
        ],
        'RETAIL': [
            'target', 'walmart', 'amazon', 'best buy', 'ikea', 'home depot', 'lowe',
            'nordstrom', 'zara', 'h&m', 'clothing', 'apparel', 'shoes', 'electronics',
            'department store', 'outlet'
        ],
        'HEALTHCARE': [
            'pharmacy', 'cvs', 'walgreens', 'rite aid', 'clinic', 'hospital', 'health',
            'dental', 'medical', 'doctor', 'physician', 'rx', 'optometry', 'care'
        ],
        'UTILITIES': [
            'electric', 'power', 'water', 'energy', 'utility', 'internet', 'comcast',
            'verizon', 'at&t', 't-mobile', 'telecom', 'broadband'
        ],
        'OFFICE': [
            'staples', 'office depot', 'fedex', 'ups', 'usps', 'paper', 'stationery',
            'printing', 'shipping', 'packaging'
        ],
        'ENTERTAINMENT': [
            'cinema', 'theatre', 'theater', 'movie', 'concert', 'ticket', 'amusement',
            'bowling', 'arcade', 'netflix', 'spotify', 'steam', 'playstation'
        ]
    }

    @classmethod
    def parse(cls, raw_text: str) -> Dict[str, Any]:
        """
        Main parsing coordinator.
        Transforms raw string into a structured dictionary ready for model persistence.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        merchant = cls.extract_merchant(lines)
        date = cls.extract_date(raw_text)
        amounts = cls.extract_amounts(lines, raw_text)
        currency = cls.extract_currency(raw_text)
        payment_method = cls.extract_payment_method(raw_text)
        items = cls.extract_line_items(lines)
        category = cls.categorize(merchant, items, raw_text)

        return {
            "merchant_name": merchant,
            "transaction_date": date,
            "total_amount": amounts.get("total"),
            "subtotal_amount": amounts.get("subtotal"),
            "tax_amount": amounts.get("tax"),
            "tip_amount": amounts.get("tip"),
            "currency": currency,
            "payment_method": payment_method,
            "category": category,
            "items": items,
        }

    @classmethod
    def extract_merchant(cls, lines: List[str]) -> Optional[str]:
        """
        Identifies the merchant/store name.
        Typically located in the top 1-4 lines of a receipt.
        Filters out addresses, dates, phone numbers, and greeting boilerplate.
        """
        if not lines:
            return None

        # Ignore lines matching common non-merchant headers
        ignore_patterns = [
            r'welcome', r'receipt', r'invoice', r'tax\s+invoice', r'customer\s+copy',
            r'order\s*#', r'table\s*#', r'tel:', r'phone:', r'www\.', r'http',
            r'^\d+\s+[a-z\s]+(st|ave|blvd|rd|dr|lane|highway|way)',  # street addresses
            r'^[0-9\-\(\)\s\+\.]{7,}$',  # pure phone numbers
            r'^date', r'^time', r'cashier'
        ]

        for line in lines[:6]:
            line_lower = line.lower().strip()
            # If line is too short or all punctuation
            if len(line) < 3 or not re.search(r'[A-Za-z]', line):
                continue

            # Check if matches any ignore pattern
            if any(re.search(pat, line_lower) for pat in ignore_patterns):
                continue

            # Clean store numbers or suffixes like "Store #10423"
            clean_name = re.sub(r'#\s*\d+', '', line).strip()
            clean_name = re.sub(r'\s{2,}', ' ', clean_name)
            return clean_name

        return lines[0] if lines else "Unknown Store"

    @classmethod
    def extract_date(cls, text: str) -> Optional[datetime.date]:
        """
        Extracts transaction date across various global date formats:
          - ISO: YYYY-MM-DD
          - US/Common: MM/DD/YYYY or DD/MM/YYYY
          - Short year: MM/DD/YY
          - Word months: 15 Oct 2024, October 15, 2024
        """
        # ISO format: 2024-10-15 or 2024/10/15
        iso_match = re.search(r'\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b', text)
        if iso_match:
            try:
                y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                return datetime.date(y, m, d)
            except ValueError:
                pass

        # Text month: "Oct 15, 2024" or "15 Oct 2024" or "October 15 2024"
        text_month_match = re.search(
            r'\b(?:(0?[1-9]|[12]\d|3[01])\s+)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:(0?[1-9]|[12]\d|3[01]),?\s+)?(20\d{2})\b',
            text,
            re.IGNORECASE
        )
        if text_month_match:
            day_str = text_month_match.group(1) or text_month_match.group(3) or "1"
            month_str = text_month_match.group(2)[:3].title()
            year_str = text_month_match.group(4)
            months = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                      'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
            try:
                return datetime.date(int(year_str), months[month_str], int(day_str))
            except (ValueError, KeyError):
                pass

        # Slash/dash format: MM/DD/YYYY or DD/MM/YYYY
        slash_match = re.search(r'\b(0?[1-9]|1[0-2]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2]|[12]\d|3[01])[-/.](20\d{2}|\d{2})\b', text)
        if slash_match:
            p1, p2, yr = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            if yr < 100:
                yr += 2000
            # Disambiguate day vs month
            try:
                if p1 > 12:  # Must be DD/MM/YYYY
                    return datetime.date(yr, p2, p1)
                elif p2 > 12:  # Must be MM/DD/YYYY
                    return datetime.date(yr, p1, p2)
                else:  # Assume MM/DD/YYYY as standard receipt convention
                    return datetime.date(yr, p1, p2)
            except ValueError:
                pass

        return None

    @classmethod
    def extract_amounts(cls, lines: List[str], full_text: str) -> Dict[str, Optional[Decimal]]:
        """
        Parses Total, Subtotal, Tax, and Tip amounts with confidence validation.
        """
        results: Dict[str, Optional[Decimal]] = {
            "total": None,
            "subtotal": None,
            "tax": None,
            "tip": None,
        }

        # Regex helper to parse price at the end of a line or after a keyword
        price_re = re.compile(r'[$€£₹]?\s*([0-9]+[.,][0-9]{2})\b')

        for line in lines:
            line_clean = line.strip()
            line_upper = line_clean.upper()

            # Skip lines that are card numbers or dates
            if re.search(r'\b(20\d{2}|[0-9]{4}\s+[0-9]{4})\b', line_clean):
                if not any(k in line_upper for k in ['TOTAL', 'DUE', 'BALANCE']):
                    continue

            # TOTAL or GRAND TOTAL or BALANCE DUE
            if re.search(r'\b(GRAND\s+TOTAL|TOTAL\s+AMOUNT|AMOUNT\s+DUE|TOTAL|BAL\s*DUE)\b', line_upper):
                if 'SUB' not in line_upper and 'TAX' not in line_upper and 'TIP' not in line_upper and 'SAVINGS' not in line_upper:
                    matches = price_re.findall(line_clean)
                    if matches:
                        try:
                            val = Decimal(matches[-1].replace(',', ''))
                            if results["total"] is None or val > (results["total"] or 0):
                                results["total"] = val
                        except InvalidOperation:
                            pass

            # SUBTOTAL
            elif 'SUBTOTAL' in line_upper or 'SUB TOTAL' in line_upper or 'NET AMOUNT' in line_upper:
                matches = price_re.findall(line_clean)
                if matches:
                    try:
                        results["subtotal"] = Decimal(matches[-1].replace(',', ''))
                    except InvalidOperation:
                        pass

            # TAX
            elif re.search(r'\b(TAX|SALES\s+TAX|VAT|GST|HST)\b', line_upper):
                matches = price_re.findall(line_clean)
                if matches:
                    try:
                        results["tax"] = Decimal(matches[-1].replace(',', ''))
                    except InvalidOperation:
                        pass

            # TIP
            elif re.search(r'\b(TIP|GRATUITY)\b', line_upper):
                matches = price_re.findall(line_clean)
                if matches:
                    try:
                        results["tip"] = Decimal(matches[-1].replace(',', ''))
                    except InvalidOperation:
                        pass

        # Post-validation fallback:
        # If total is still missing, find the largest reasonable monetary value in the receipt
        if results["total"] is None:
            all_prices = []
            for p in price_re.findall(full_text):
                try:
                    val = Decimal(p.replace(',', ''))
                    if 0.50 <= val <= 10000:
                        all_prices.append(val)
                except InvalidOperation:
                    pass
            if all_prices:
                results["total"] = max(all_prices)

        return results

    @classmethod
    def extract_currency(cls, text: str) -> str:
        """Determines currency based on symbols or codes present."""
        for symbol, code in cls.CURRENCY_SYMBOLS.items():
            if symbol in text:
                return code
        return "USD"

    @classmethod
    def extract_payment_method(cls, text: str) -> Optional[str]:
        """Detects payment method: Visa, Mastercard, Amex, Cash, etc."""
        text_upper = text.upper()
        if 'VISA' in text_upper:
            return 'VISA'
        if 'MASTERCARD' in text_upper or 'MC ' in text_upper:
            return 'MASTERCARD'
        if 'AMEX' in text_upper or 'AMERICAN EXPRESS' in text_upper:
            return 'AMERICAN EXPRESS'
        if 'DISCOVER' in text_upper:
            return 'DISCOVER'
        if 'APPLE PAY' in text_upper:
            return 'APPLE PAY'
        if 'GOOGLE PAY' in text_upper:
            return 'GOOGLE PAY'
        if 'CASH' in text_upper:
            return 'CASH'
        if 'DEBIT' in text_upper:
            return 'DEBIT CARD'
        if 'CREDIT' in text_upper:
            return 'CREDIT CARD'
        return None

    @classmethod
    def extract_line_items(cls, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Parses itemized lines into structured items:
        e.g. "1 CARAMEL MACCHIATO    $5.45" -> {description: "CARAMEL MACCHIATO", quantity: 1, total_price: 5.45}
        """
        items: List[Dict[str, Any]] = []
        item_line_re = re.compile(r'^(?:(\d+)\s+)?([A-Za-z0-9\s\.\&\-\/\']+?)\s+[$€£₹]?\s*([0-9]+[.,][0-9]{2})$')

        stop_words = [
            'TOTAL', 'SUBTOTAL', 'TAX', 'TIP', 'GRATUITY', 'BALANCE', 'CHANGE', 'CASH',
            'VISA', 'MASTERCARD', 'AMEX', 'DISCOVER', 'PAYMENT', 'AMOUNT', 'AUTH',
            'CARD', 'THANK YOU', 'ITEMS SOLD', 'TABLE', 'GUESTS', 'TEL:', 'PHONE'
        ]

        for line in lines:
            line_clean = line.strip()
            line_upper = line_clean.upper()

            # Skip header and summary lines
            if any(sw in line_upper for sw in stop_words):
                continue

            match = item_line_re.match(line_clean)
            if match:
                qty_str, desc, price_str = match.groups()
                desc = desc.strip()

                # Filter out pure noise lines
                if len(desc) < 2 or not re.search(r'[A-Za-z]', desc):
                    continue

                try:
                    price = Decimal(price_str.replace(',', ''))
                    qty = int(qty_str) if qty_str else 1
                    unit_price = round(price / qty, 2) if qty > 1 else price

                    items.append({
                        "description": desc,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total_price": price
                    })
                except (InvalidOperation, ZeroDivisionError):
                    continue

        return items

    @classmethod
    def categorize(cls, merchant: Optional[str], items: List[Dict[str, Any]], raw_text: str) -> str:
        """
        Categorizes receipt into standard financial buckets based on:
          1. Merchant name
          2. Line item descriptions
          3. Keyword occurrence frequencies
        """
        search_blob = f"{merchant or ''} {' '.join(i.get('description', '') for i in items)} {raw_text}".lower()

        scores: Dict[str, int] = {cat: 0 for cat in cls.CATEGORY_KEYWORDS}

        for cat, keywords in cls.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in search_blob:
                    scores[cat] += 2 if merchant and kw in merchant.lower() else 1

        best_category = max(scores, key=scores.get)
        if scores[best_category] > 0:
            return best_category

        return 'OTHER'
