"""
models.py — ビジネスロジック（CLI 版から流用・Web 向けに拡張）
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

STANDARD_TAX_RATE = 0.10
REDUCED_TAX_RATE  = 0.08


class TaxCategory(Enum):
    STANDARD = "standard"
    REDUCED  = "reduced"

    @property
    def label(self) -> str:
        return "標準税率（10%）" if self == TaxCategory.STANDARD else "軽減税率（8%）"

    @property
    def rate(self) -> float:
        return STANDARD_TAX_RATE if self == TaxCategory.STANDARD else REDUCED_TAX_RATE


class DiscountType(Enum):
    AMOUNT  = "amount"
    PERCENT = "percent"


@dataclass
class Product:
    id: str
    name: str
    price: float
    tax_category: TaxCategory
    emoji: str = ""
    category_id: Optional[int] = None
    category_name: str = ""

    @property
    def tax_amount(self) -> float:
        return self.price * self.tax_category.rate

    @property
    def price_with_tax(self) -> float:
        return self.price + self.tax_amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "price_with_tax": round(self.price_with_tax),
            "tax_category": self.tax_category.value,
            "tax_label": self.tax_category.label,
            "emoji": self.emoji,
            "category_id": self.category_id,
            "category_name": self.category_name,
        }


@dataclass
class CartItem:
    product: Product
    quantity: int = 1

    @property
    def subtotal_ex_tax(self) -> float:
        return self.product.price * self.quantity

    @property
    def subtotal_tax(self) -> float:
        return self.product.tax_amount * self.quantity

    @property
    def subtotal_with_tax(self) -> float:
        return self.product.price_with_tax * self.quantity

    def to_dict(self) -> dict:
        return {
            "product_id": self.product.id,
            "name": self.product.name,
            "unit_price": self.product.price,
            "unit_price_with_tax": round(self.product.price_with_tax),
            "quantity": self.quantity,
            "subtotal": round(self.subtotal_with_tax),
            "tax_category": self.product.tax_category.value,
            "tax_label": self.product.tax_category.label,
        }


class Cart:
    def __init__(self) -> None:
        self.items: list[CartItem] = []
        self.discount_type: Optional[str]   = None  # "amount" | "percent"
        self.discount_value: float          = 0.0
        self.customer_id: Optional[int]     = None

    # ── 操作 ───────────────────────────────────────────
    def add(self, product: Product, quantity: int = 1) -> None:
        for item in self.items:
            if item.product.id == product.id:
                item.quantity += quantity
                return
        self.items.append(CartItem(product, quantity))

    def remove(self, product_id: str) -> None:
        self.items = [i for i in self.items if i.product.id != product_id]

    def update_quantity(self, product_id: str, quantity: int) -> None:
        for item in self.items:
            if item.product.id == product_id:
                if quantity <= 0:
                    self.remove(product_id)
                else:
                    item.quantity = quantity
                return

    def set_discount(self, discount_type: str, value: float) -> None:
        self.discount_type  = discount_type
        self.discount_value = value

    def clear_discount(self) -> None:
        self.discount_type  = None
        self.discount_value = 0.0

    def clear(self) -> None:
        self.items         = []
        self.discount_type  = None
        self.discount_value = 0.0
        self.customer_id   = None

    # ── 計算 ───────────────────────────────────────────
    @property
    def subtotal_ex_tax(self) -> float:
        return sum(i.subtotal_ex_tax for i in self.items)

    @property
    def total_tax(self) -> float:
        return sum(i.subtotal_tax for i in self.items)

    @property
    def subtotal_with_tax(self) -> float:
        return self.subtotal_ex_tax + self.total_tax

    @property
    def discount_amount(self) -> float:
        if not self.discount_type:
            return 0.0
        if self.discount_type == "amount":
            return min(self.discount_value, self.subtotal_with_tax)
        return self.subtotal_with_tax * (self.discount_value / 100)

    @property
    def total(self) -> float:
        return max(0.0, self.subtotal_with_tax - self.discount_amount)

    # ── シリアライズ ────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "discount_type":  self.discount_type,
            "discount_value": self.discount_value,
            "discount_amount": round(self.discount_amount),
            "subtotal_ex_tax": round(self.subtotal_ex_tax),
            "total_tax":       round(self.total_tax),
            "subtotal_with_tax": round(self.subtotal_with_tax),
            "total":           round(self.total),
            "customer_id":     self.customer_id,
        }

    @classmethod
    def from_dict(cls, data: dict, product_master: dict[str, Product]) -> "Cart":
        cart = cls()
        for item_data in data.get("items", []):
            pid = item_data["product_id"]
            if pid in product_master:
                cart.items.append(
                    CartItem(product_master[pid], item_data["quantity"])
                )
        cart.discount_type  = data.get("discount_type")
        cart.discount_value = data.get("discount_value", 0.0)
        cart.customer_id   = data.get("customer_id")
        return cart


# ── 商品マスタ ────────────────────────────────────────
PRODUCT_MASTER: dict[str, Product] = {
    "1": Product("1", "お茶（500ml）",  150, TaxCategory.REDUCED,  "🍵"),
    "2": Product("2", "おにぎり（鮭）", 180, TaxCategory.REDUCED,  "🍙"),
    "3": Product("3", "弁当（幕の内）", 580, TaxCategory.REDUCED,  "🍱"),
    "4": Product("4", "コーヒー（缶）", 130, TaxCategory.REDUCED,  "☕"),
    "5": Product("5", "ボールペン",     220, TaxCategory.STANDARD, "✏️"),
    "6": Product("6", "ノート（A5）",   350, TaxCategory.STANDARD, "📓"),
    "7": Product("7", "付箋セット",     480, TaxCategory.STANDARD, "📌"),
    "8": Product("8", "マグカップ",     980, TaxCategory.STANDARD, "🫖"),
}
