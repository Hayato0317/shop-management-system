"""
app.py — Flask エントリーポイント
商品計算システム + 顧客管理 Web アプリ
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import database as db
from models import Cart, Product, TaxCategory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-freee-2024")

# ── 起動時に DB 初期化 ────────────────────────────────
db.init_db()


# ── ヘルパー ──────────────────────────────────────────
def build_product_master() -> dict[str, Product]:
    rows = db.get_all_products()
    return {
        str(r["id"]): Product(
            id=str(r["id"]),
            name=r["name"],
            price=r["price"],
            tax_category=TaxCategory(r["tax_category"]),
            emoji=r["emoji"] or "",
            category_id=r.get("category_id"),
            category_name=r.get("category_name") or "",
        )
        for r in rows
    }


def get_cart() -> Cart:
    data = session.get("cart", {"items": []})
    return Cart.from_dict(data, build_product_master())


def save_cart(cart: Cart) -> None:
    session["cart"] = cart.to_dict()
    session.modified = True


# ══════════════════════════════════════════════════════
#  画面ルート
# ══════════════════════════════════════════════════════

@app.route("/")
def pos():
    products = build_product_master()
    categories = db.get_all_categories()
    return render_template("pos.html", products=products, categories=categories)


@app.route("/products")
def products_page():
    return render_template("products.html")


@app.route("/customers")
def customers():
    return render_template("customers.html")


@app.route("/customers/<int:customer_id>")
def customer_detail(customer_id: int):
    customer = db.get_customer(customer_id)
    if not customer:
        return redirect(url_for("customers"))
    purchases     = db.get_customer_purchases(customer_id)
    total_spent   = sum(p["total"] for p in purchases)
    product_stats = db.get_customer_product_stats(customer_id)
    return render_template(
        "customer_detail.html",
        customer=customer,
        purchases=purchases,
        total_spent=total_spent,
        product_stats=product_stats,
    )


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/analytics")
def analytics():
    ranking = db.get_product_sales_ranking()
    max_qty  = ranking[0]["total_qty"] if ranking else 1
    return render_template("analytics.html", ranking=ranking, max_qty=max_qty)


# ══════════════════════════════════════════════════════
#  API — カート
# ══════════════════════════════════════════════════════

@app.get("/api/products")
def api_products():
    return jsonify([p.to_dict() for p in build_product_master().values()])


@app.post("/api/products")
def api_product_create():
    data        = request.get_json(force=True)
    name        = data.get("name", "").strip()
    price       = data.get("price")
    tax         = data.get("tax_category", "standard")
    emoji       = data.get("emoji", "").strip()
    category_id = data.get("category_id")
    if not name or price is None:
        return jsonify({"error": "商品名と価格は必須です"}), 400
    if tax not in ("standard", "reduced"):
        return jsonify({"error": "税区分が不正です"}), 400
    try:
        pid = db.create_product(
            name, float(price), tax, emoji,
            int(category_id) if category_id else None,
        )
        return jsonify({"id": pid, "message": "登録しました"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.put("/api/products/<int:product_id>")
def api_product_update(product_id: int):
    data        = request.get_json(force=True)
    name        = data.get("name", "").strip()
    price       = data.get("price")
    tax         = data.get("tax_category", "standard")
    emoji       = data.get("emoji", "").strip()
    category_id = data.get("category_id")
    if not name or price is None:
        return jsonify({"error": "商品名と価格は必須です"}), 400
    db.update_product(
        product_id, name, float(price), tax, emoji,
        int(category_id) if category_id else None,
    )
    return jsonify({"message": "更新しました"})


@app.delete("/api/products/<int:product_id>")
def api_product_delete(product_id: int):
    db.delete_product(product_id)
    return jsonify({"message": "削除しました"})


@app.get("/api/categories")
def api_categories():
    return jsonify(db.get_all_categories())


@app.post("/api/categories")
def api_category_create():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "カテゴリー名は必須です"}), 400
    try:
        cid = db.create_category(name)
        return jsonify({"id": cid, "message": "登録しました"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.put("/api/categories/<int:category_id>")
def api_category_update(category_id: int):
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "カテゴリー名は必須です"}), 400
    try:
        db.update_category(category_id, name)
        return jsonify({"message": "更新しました"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/categories/<int:category_id>")
def api_category_delete(category_id: int):
    db.delete_category(category_id)
    return jsonify({"message": "削除しました"})


@app.get("/api/cart")
def api_cart():
    return jsonify(get_cart().to_dict())


@app.post("/api/cart/add")
def api_cart_add():
    data = request.get_json(force=True)
    pid  = str(data.get("product_id", ""))
    qty  = int(data.get("quantity", 1))
    master = build_product_master()
    if pid not in master or qty < 1:
        return jsonify({"error": "invalid"}), 400
    cart = get_cart()
    cart.add(master[pid], qty)
    save_cart(cart)
    return jsonify(cart.to_dict())


@app.post("/api/cart/remove")
def api_cart_remove():
    data = request.get_json(force=True)
    pid  = str(data.get("product_id", ""))
    cart = get_cart()
    cart.remove(pid)
    save_cart(cart)
    return jsonify(cart.to_dict())


@app.post("/api/cart/quantity")
def api_cart_quantity():
    data = request.get_json(force=True)
    pid  = str(data.get("product_id", ""))
    qty  = int(data.get("quantity", 1))
    cart = get_cart()
    cart.update_quantity(pid, qty)
    save_cart(cart)
    return jsonify(cart.to_dict())


@app.post("/api/cart/discount")
def api_cart_discount():
    data = request.get_json(force=True)
    dtype = data.get("discount_type")
    value = float(data.get("value", 0))
    cart  = get_cart()
    if dtype in ("amount", "percent") and value > 0:
        cart.set_discount(dtype, value)
    else:
        cart.clear_discount()
    save_cart(cart)
    return jsonify(cart.to_dict())


@app.post("/api/cart/customer")
def api_cart_customer():
    data        = request.get_json(force=True)
    customer_id = data.get("customer_id")
    cart        = get_cart()
    cart.customer_id = int(customer_id) if customer_id else None
    save_cart(cart)
    return jsonify(cart.to_dict())


@app.post("/api/checkout")
def api_checkout():
    cart = get_cart()
    if not cart.items:
        return jsonify({"error": "カートが空です"}), 400

    items_data = [
        {
            "name":         i.product.name,
            "unit_price":   i.product.price,
            "quantity":     i.quantity,
            "subtotal":     round(i.subtotal_with_tax),
            "tax_category": i.product.tax_category.value,
        }
        for i in cart.items
    ]

    purchase_id = db.save_purchase(
        items=items_data,
        total=round(cart.total),
        discount_amount=round(cart.discount_amount),
        customer_id=cart.customer_id,
    )

    receipt = cart.to_dict()
    receipt["purchase_id"] = purchase_id

    # 顧客名を付加
    if cart.customer_id:
        c = db.get_customer(cart.customer_id)
        receipt["customer_name"] = c["name"] if c else None

    cart.clear()
    save_cart(cart)
    return jsonify(receipt)


# ══════════════════════════════════════════════════════
#  API — 顧客
# ══════════════════════════════════════════════════════

@app.get("/api/customers")
def api_customers():
    return jsonify(db.get_all_customers())


@app.post("/api/customers")
def api_customer_create():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "名前は必須です"}), 400
    try:
        cid = db.create_customer(
            name=name,
            email=data.get("email", "").strip(),
            phone=data.get("phone", "").strip(),
            address=data.get("address", "").strip(),
        )
        return jsonify({"id": cid, "message": "登録しました"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.put("/api/customers/<int:customer_id>")
def api_customer_update(customer_id: int):
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "名前は必須です"}), 400
    db.update_customer(
        customer_id,
        name=name,
        email=data.get("email", "").strip(),
        phone=data.get("phone", "").strip(),
        address=data.get("address", "").strip(),
    )
    return jsonify({"message": "更新しました"})


@app.delete("/api/customers/<int:customer_id>")
def api_customer_delete(customer_id: int):
    db.delete_customer(customer_id)
    return jsonify({"message": "削除しました"})


@app.get("/api/customers/<int:customer_id>")
def api_customer_get(customer_id: int):
    c = db.get_customer(customer_id)
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify(c)


# ══════════════════════════════════════════════════════
#  API — 購入履歴
# ══════════════════════════════════════════════════════

@app.get("/api/history")
def api_history():
    return jsonify(db.get_all_purchases())


@app.get("/api/history/<int:purchase_id>")
def api_history_detail(purchase_id: int):
    purchase = db.get_purchase_with_items(purchase_id)
    if not purchase:
        return jsonify({"error": "not found"}), 404
    return jsonify(purchase)


# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)
