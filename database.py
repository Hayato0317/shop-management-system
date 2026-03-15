"""
database.py — SQLite 初期化・CRUD ユーティリティ
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

DB_PATH = "shop.db"


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SEED_PRODUCTS = [
    ("お茶（500ml）",  150, "reduced",  "🍵"),
    ("おにぎり（鮭）", 180, "reduced",  "🍙"),
    ("弁当（幕の内）", 580, "reduced",  "🍱"),
    ("コーヒー（缶）", 130, "reduced",  "☕"),
    ("ボールペン",     220, "standard", "✏️"),
    ("ノート（A5）",   350, "standard", "📓"),
    ("付箋セット",     480, "standard", "📌"),
    ("マグカップ",     980, "standard", "🫖"),
]


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                price        REAL NOT NULL,
                tax_category TEXT NOT NULL DEFAULT 'standard',
                emoji        TEXT DEFAULT '',
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT UNIQUE,
                phone      TEXT,
                address    TEXT,
                points     INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id     INTEGER REFERENCES customers(id) ON DELETE SET NULL,
                total           REAL NOT NULL,
                discount_amount REAL DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS purchase_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id  INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
                product_name TEXT NOT NULL,
                unit_price   REAL NOT NULL,
                quantity     INTEGER NOT NULL,
                subtotal     REAL NOT NULL,
                tax_category TEXT NOT NULL
            );
        """)
        # 商品が0件のときだけシードデータを投入
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO products (name, price, tax_category, emoji) VALUES (?,?,?,?)",
                SEED_PRODUCTS,
            )


# ── 商品 CRUD ─────────────────────────────────────────

def get_all_products() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def create_product(name: str, price: float, tax_category: str, emoji: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, price, tax_category, emoji) VALUES (?,?,?,?)",
            (name, price, tax_category, emoji),
        )
        return cur.lastrowid


def update_product(product_id: int, name: str, price: float, tax_category: str, emoji: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET name=?, price=?, tax_category=?, emoji=? WHERE id=?",
            (name, price, tax_category, emoji, product_id),
        )


def delete_product(product_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ── 顧客 CRUD ─────────────────────────────────────────

def get_all_customers() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM customers ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_customer(customer_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None


def create_customer(name: str, email: str, phone: str, address: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)",
            (name, email or None, phone, address),
        )
        return cur.lastrowid


def update_customer(customer_id: int, name: str, email: str, phone: str, address: str) -> bool:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET name=?, email=?, phone=?, address=? WHERE id=?",
            (name, email or None, phone, address, customer_id),
        )
        return True


def delete_customer(customer_id: int) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        return True


def add_points(customer_id: int, points: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET points = points + ? WHERE id = ?",
            (points, customer_id),
        )


# ── 購入履歴 CRUD ────────────────────────────────────

def save_purchase(
    items: list[dict],
    total: float,
    discount_amount: float,
    customer_id: int | None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO purchases (customer_id, total, discount_amount) VALUES (?, ?, ?)",
            (customer_id, total, discount_amount),
        )
        purchase_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO purchase_items
               (purchase_id, product_name, unit_price, quantity, subtotal, tax_category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    purchase_id,
                    item["name"],
                    item["unit_price"],
                    item["quantity"],
                    item["subtotal"],
                    item["tax_category"],
                )
                for item in items
            ],
        )
        # ポイント付与（合計の1%）
        if customer_id:
            add_points(customer_id, int(total // 100))
        return purchase_id


def get_all_purchases() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.*, c.name AS customer_name
            FROM purchases p
            LEFT JOIN customers c ON p.customer_id = c.id
            ORDER BY p.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_purchase_with_items(purchase_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
        ).fetchone()
        if not row:
            return None
        purchase = dict(row)
        items = conn.execute(
            "SELECT * FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
        ).fetchall()
        purchase["items"] = [dict(i) for i in items]
        return purchase


def get_customer_purchases(customer_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM purchases WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
        result = []
        for row in rows:
            purchase = dict(row)
            items = conn.execute(
                "SELECT * FROM purchase_items WHERE purchase_id = ?", (row["id"],)
            ).fetchall()
            purchase["items"] = [dict(i) for i in items]
            result.append(purchase)
        return result
