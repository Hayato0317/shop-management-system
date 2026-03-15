"""
商品計算システム - Product Calculator
フリー株式会社 面接作品

機能:
  - 商品の登録・管理
  - 消費税計算（標準税率10% / 軽減税率8%）
  - 割引処理（金額・パーセント）
  - レシート出力
  - 購入履歴の保存（JSON）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── 定数 ──────────────────────────────────────────────
STANDARD_TAX_RATE = 0.10   # 標準税率
REDUCED_TAX_RATE  = 0.08   # 軽減税率（食料品など）
HISTORY_FILE      = "purchase_history.json"


# ── 列挙型 ────────────────────────────────────────────
class TaxCategory(Enum):
    STANDARD = "標準税率（10%）"
    REDUCED  = "軽減税率（8%）"


class DiscountType(Enum):
    AMOUNT  = "金額割引"
    PERCENT = "パーセント割引"


# ── データクラス ──────────────────────────────────────
@dataclass
class Product:
    """商品を表すクラス"""
    name: str
    price: float                          # 税抜価格
    tax_category: TaxCategory = TaxCategory.STANDARD

    @property
    def tax_rate(self) -> float:
        return STANDARD_TAX_RATE if self.tax_category == TaxCategory.STANDARD else REDUCED_TAX_RATE

    @property
    def tax_amount(self) -> float:
        return self.price * self.tax_rate

    @property
    def price_with_tax(self) -> float:
        return self.price + self.tax_amount

    def __str__(self) -> str:
        return (
            f"{self.name}  "
            f"¥{self.price:,.0f}（税込 ¥{self.price_with_tax:,.0f}）"
            f"  [{self.tax_category.value}]"
        )


@dataclass
class CartItem:
    """カート内の商品（商品＋数量）"""
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


@dataclass
class Discount:
    """割引情報"""
    discount_type: DiscountType
    value: float                          # 金額 or パーセント

    def apply(self, total: float) -> float:
        """割引後の金額を返す（0円未満にはならない）"""
        if self.discount_type == DiscountType.AMOUNT:
            return max(0.0, total - self.value)
        else:  # PERCENT
            return max(0.0, total * (1 - self.value / 100))

    def __str__(self) -> str:
        if self.discount_type == DiscountType.AMOUNT:
            return f"割引: -¥{self.value:,.0f}"
        return f"割引: -{self.value:.1f}%"


# ── ショッピングカート ─────────────────────────────────
class ShoppingCart:
    """商品の追加・計算・レシート出力を管理するカート"""

    def __init__(self) -> None:
        self.items: list[CartItem] = []
        self.discount: Optional[Discount] = None

    # ── カート操作 ──────────────────────────────────
    def add(self, product: Product, quantity: int = 1) -> None:
        for item in self.items:
            if item.product.name == product.name:
                item.quantity += quantity
                return
        self.items.append(CartItem(product, quantity))

    def remove(self, product_name: str) -> bool:
        for i, item in enumerate(self.items):
            if item.product.name == product_name:
                self.items.pop(i)
                return True
        return False

    def set_discount(self, discount: Discount) -> None:
        self.discount = discount

    def clear(self) -> None:
        self.items.clear()
        self.discount = None

    # ── 合計計算 ────────────────────────────────────
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
    def total(self) -> float:
        if self.discount:
            return self.discount.apply(self.subtotal_with_tax)
        return self.subtotal_with_tax

    @property
    def discount_amount(self) -> float:
        return self.subtotal_with_tax - self.total

    # ── レシート出力 ────────────────────────────────
    def receipt(self) -> str:
        width = 44
        sep   = "─" * width
        lines = [
            "=" * width,
            "　　　　　　 レシート".center(width),
            f"　　{datetime.now().strftime('%Y年%m月%d日  %H:%M:%S')}",
            "=" * width,
        ]

        for item in self.items:
            tax_mark = "※" if item.product.tax_category == TaxCategory.REDUCED else "　"
            lines.append(
                f"{tax_mark}{item.product.name[:14]:<14} "
                f"{item.quantity:>2}個  ¥{item.subtotal_with_tax:>8,.0f}"
            )

        lines += [
            sep,
            f"　小計（税抜）           ¥{self.subtotal_ex_tax:>8,.0f}",
            f"　消費税                 ¥{self.total_tax:>8,.0f}",
        ]

        if self.discount and self.discount_amount > 0:
            lines.append(f"　{self.discount}  -¥{self.discount_amount:>7,.0f}")

        lines += [
            "=" * width,
            f"　合　計                 ¥{self.total:>8,.0f}",
            "=" * width,
            "　※ 軽減税率（8%）対象商品",
            "",
        ]
        return "\n".join(lines)

    # ── 履歴保存 ────────────────────────────────────
    def save_history(self) -> None:
        record = {
            "datetime": datetime.now().isoformat(),
            "items": [
                {
                    "name": i.product.name,
                    "unit_price": i.product.price,
                    "quantity": i.quantity,
                    "subtotal": i.subtotal_with_tax,
                }
                for i in self.items
            ],
            "total": self.total,
        }

        history: list[dict] = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, encoding="utf-8") as f:
                history = json.load(f)

        history.append(record)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


# ── 商品マスタ ────────────────────────────────────────
PRODUCT_MASTER: dict[str, Product] = {
    "1": Product("お茶（500ml）",   150, TaxCategory.REDUCED),
    "2": Product("おにぎり（鮭）",   180, TaxCategory.REDUCED),
    "3": Product("弁当（幕の内）",   580, TaxCategory.REDUCED),
    "4": Product("コーヒー（缶）",   130, TaxCategory.REDUCED),
    "5": Product("ボールペン",        220, TaxCategory.STANDARD),
    "6": Product("ノート（A5）",     350, TaxCategory.STANDARD),
    "7": Product("付箋セット",        480, TaxCategory.STANDARD),
    "8": Product("マグカップ",        980, TaxCategory.STANDARD),
}


# ── CLI インターフェース ───────────────────────────────
def show_products() -> None:
    print("\n── 商品一覧 ──────────────────────────────")
    for code, p in PRODUCT_MASTER.items():
        print(f"  [{code}] {p}")
    print()


def input_int(prompt: str, min_val: int = 1, max_val: int = 99) -> int:
    while True:
        try:
            v = int(input(prompt))
            if min_val <= v <= max_val:
                return v
            print(f"  ※ {min_val}〜{max_val} の範囲で入力してください。")
        except ValueError:
            print("  ※ 数値を入力してください。")


def show_cart(cart: ShoppingCart) -> None:
    if not cart.items:
        print("\n  カートは空です。\n")
        return
    print("\n── カート内容 ────────────────────────────")
    for item in cart.items:
        print(
            f"  {item.product.name}  x{item.quantity}  "
            f"¥{item.subtotal_with_tax:,.0f}（税込）"
        )
    print(f"  ─────────────────────────────────────")
    print(f"  合計（税込）: ¥{cart.subtotal_with_tax:,.0f}")
    if cart.discount:
        print(f"  {cart.discount}  → ¥{cart.total:,.0f}")
    print()


def add_discount_menu(cart: ShoppingCart) -> None:
    print("\n割引タイプを選択してください:")
    print("  [1] 金額割引")
    print("  [2] パーセント割引")
    choice = input("選択 > ").strip()
    if choice == "1":
        amount = input_int("割引金額（円）を入力 > ", min_val=1, max_val=100_000)
        cart.set_discount(Discount(DiscountType.AMOUNT, float(amount)))
    elif choice == "2":
        pct = input_int("割引率（%）を入力 > ", min_val=1, max_val=100)
        cart.set_discount(Discount(DiscountType.PERCENT, float(pct)))
    else:
        print("  キャンセルしました。")


def main() -> None:
    cart = ShoppingCart()
    print("\n" + "=" * 44)
    print("　　　商品計算システム".center(44))
    print("=" * 44)

    while True:
        print("── メニュー ──────────────────────────────")
        print("  [1] 商品を追加")
        print("  [2] カートを確認")
        print("  [3] 商品を削除")
        print("  [4] 割引を設定")
        print("  [5] 精算（レシート出力）")
        print("  [0] 終了")
        choice = input("選択 > ").strip()

        if choice == "1":
            show_products()
            code = input("商品番号 > ").strip()
            if code not in PRODUCT_MASTER:
                print("  ※ 該当する商品がありません。")
                continue
            qty = input_int("数量 > ")
            cart.add(PRODUCT_MASTER[code], qty)
            print(f"  ✓ {PRODUCT_MASTER[code].name} を {qty}個 追加しました。")

        elif choice == "2":
            show_cart(cart)

        elif choice == "3":
            show_cart(cart)
            name = input("削除する商品名を入力 > ").strip()
            if cart.remove(name):
                print(f"  ✓ 「{name}」を削除しました。")
            else:
                print("  ※ 該当する商品がカートにありません。")

        elif choice == "4":
            add_discount_menu(cart)

        elif choice == "5":
            if not cart.items:
                print("  ※ カートが空です。")
                continue
            receipt_text = cart.receipt()
            print("\n" + receipt_text)
            cart.save_history()
            print(f"  履歴を {HISTORY_FILE} に保存しました。")

            again = input("続けて購入しますか？ (y/n) > ").strip().lower()
            if again == "y":
                cart.clear()
            else:
                print("\nご利用ありがとうございました。\n")
                break

        elif choice == "0":
            print("\nシステムを終了します。\n")
            break
        else:
            print("  ※ 正しい番号を入力してください。")


if __name__ == "__main__":
    main()
