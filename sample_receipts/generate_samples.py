"""
Generates synthetic sample receipt images for testing and demonstration.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def create_receipt_image(filename: str, lines: list):
    width, height = 550, 750
    image = Image.new("RGB", (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(image)

    # Use default bitmap font
    y = 40
    for line in lines:
        if line.startswith("===") or line.startswith("---"):
            draw.line([(40, y + 8), (width - 40, y + 8)], fill=(120, 120, 120), width=1)
            y += 25
        elif line.startswith("#HEADER#"):
            draw.text((width // 4, y), line.replace("#HEADER#", ""), fill=(20, 20, 20))
            y += 30
        else:
            draw.text((50, y), line, fill=(30, 30, 30))
            y += 24

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    image.save(filename, "PNG")
    print(f"Generated: {filename}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Coffee receipt
    coffee_lines = [
        "#HEADER#STARBUCKS COFFEE #10423",
        "123 MARKET STREET, SAN FRANCISCO, CA",
        "TEL: (415) 555-0199",
        "DATE: 2024-10-15 08:42 AM",
        "------------------------------------",
        "1 CARAMEL MACCHIATO         $5.45",
        "1 CROISSANT                  $3.75",
        "------------------------------------",
        "SUBTOTAL:                    $9.20",
        "TAX (8.5%):                  $0.78",
        "TIP:                         $1.50",
        "TOTAL:                      $11.48",
        "------------------------------------",
        "VISA CARD ************4242",
        "AUTH CODE: 981244",
        "THANK YOU FOR VISITING!"
    ]
    create_receipt_image(os.path.join(base_dir, "starbucks_coffee.png"), coffee_lines)

    # 2. Grocery receipt
    grocery_lines = [
        "#HEADER#WHOLE FOODS MARKET",
        "450 RHODE ISLAND ST, SAN FRANCISCO",
        "DATE: 10/12/2024  14:30",
        "CASHIER: SARAH M",
        "====================================",
        "ORGANIC WHOLE MILK          $4.99",
        "SOURDOUGH BREAD             $5.50",
        "AVOCADOS 3PK                $3.99",
        "ORGANIC APPLES              $6.49",
        "====================================",
        "SUBTOTAL:                  $20.97",
        "TAX:                        $1.68",
        "TOTAL:                     $22.65",
        "PAYMENT: MASTERCARD 5521",
        "ITEMS SOLD: 4",
        "HAVE A GREAT DAY!"
    ]
    create_receipt_image(os.path.join(base_dir, "whole_foods_grocery.png"), grocery_lines)

    # 3. Bistro dinner receipt
    bistro_lines = [
        "#HEADER#THE CAPITAL BISTRO",
        "789 DOWNTOWN AVE, NEW YORK, NY",
        "TABLE 14 - GUESTS: 2",
        "DATE: 2024-09-28 20:15",
        "------------------------------------",
        "1 GRILLED SALMON            $28.00",
        "1 RIBEYE STEAK              $36.00",
        "2 SPARKLING WATER            $8.00",
        "1 CHOCOLATE LAVA CAKE       $11.00",
        "------------------------------------",
        "SUBTOTAL:                   $83.00",
        "STATE TAX:                   $7.47",
        "TIP (18%):                  $15.00",
        "GRAND TOTAL:               $105.47",
        "PAYMENT: AMEX 1004"
    ]
    create_receipt_image(os.path.join(base_dir, "capital_bistro_dinner.png"), bistro_lines)

