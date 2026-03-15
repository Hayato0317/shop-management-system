/* ══════════════════════════════════════════
   app.js — 商品計算システム + 顧客管理
   ══════════════════════════════════════════ */

const fmt = n => '¥' + Math.round(n).toLocaleString('ja-JP');

// ── API ヘルパー ──────────────────────────────────────
async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
}

/* ══════════════════════════════════════════
   POS 画面
   ══════════════════════════════════════════ */
function initPOS() {
  loadCustomerSelect();
  refreshCart();

  document.getElementById('customerSelect').addEventListener('change', async e => {
    const id = e.target.value ? parseInt(e.target.value) : null;
    await api('/api/cart/customer', 'POST', { customer_id: id });
    refreshCart();
  });
}

async function loadCustomerSelect() {
  const customers = await api('/api/customers');
  const sel = document.getElementById('customerSelect');
  customers.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = `${c.name}（${fmt(c.points)}pt）`;
    sel.appendChild(opt);
  });
  // カートの顧客を復元
  const cart = await api('/api/cart');
  if (cart.customer_id) sel.value = cart.customer_id;
}

function filterPOS(categoryId) {
  document.querySelectorAll('#posCategoryTabs .btn').forEach(b => {
    b.classList.remove('btn-primary');
    b.classList.add('btn-outline-primary');
  });
  const btn = categoryId ? document.getElementById(`poscat-${categoryId}`) : document.getElementById('poscat-all');
  if (btn) { btn.classList.remove('btn-outline-primary'); btn.classList.add('btn-primary'); }
  document.querySelectorAll('.product-col').forEach(col => {
    col.style.display = (!categoryId || col.dataset.categoryId == categoryId) ? '' : 'none';
  });
}

async function addToCart(productId) {
  const cart = await api('/api/cart/add', 'POST', { product_id: productId, quantity: 1 });
  renderCart(cart);

  // カードを一瞬ハイライト
  const card = document.querySelector(`[data-pid="${productId}"]`);
  if (card) {
    card.classList.add('border-primary');
    setTimeout(() => card.classList.remove('border-primary'), 300);
  }
}

async function refreshCart() {
  const cart = await api('/api/cart');
  renderCart(cart);
}

function renderCart(cart) {
  const container  = document.getElementById('cartItems');
  const btn        = document.getElementById('checkoutBtn');
  const discountRow = document.getElementById('discountRow');

  if (!cart.items || cart.items.length === 0) {
    container.innerHTML = `
      <div class="empty-cart">
        <i class="bi bi-cart-x"></i>
        <p class="mt-2 small">カートは空です</p>
      </div>`;
    btn.disabled = true;
  } else {
    container.innerHTML = cart.items.map(item => `
      <div class="cart-item">
        <div class="item-name">
          ${item.tax_category === 'reduced' ? '<span class="badge bg-success me-1" style="font-size:.6rem">軽減</span>' : ''}
          ${item.name}
        </div>
        <button class="qty-btn" onclick="changeQty('${item.product_id}', ${item.quantity - 1})">−</button>
        <span class="qty-display">${item.quantity}</span>
        <button class="qty-btn" onclick="changeQty('${item.product_id}', ${item.quantity + 1})">＋</button>
        <div class="item-price">${fmt(item.subtotal)}</div>
        <button class="btn btn-sm btn-link text-danger p-0 ms-1"
                onclick="removeFromCart('${item.product_id}')">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
    `).join('');
    btn.disabled = false;
  }

  document.getElementById('subtotalExTax').textContent = fmt(cart.subtotal_ex_tax);
  document.getElementById('totalTax').textContent      = fmt(cart.total_tax);
  document.getElementById('totalAmount').textContent   = fmt(cart.total);

  if (cart.discount_amount > 0) {
    const label = cart.discount_type === 'amount'
      ? `割引（${fmt(cart.discount_value)}円引き）`
      : `割引（${cart.discount_value}%引き）`;
    document.getElementById('discountLabel').textContent = label;
    document.getElementById('discountAmt').textContent   = `−${fmt(cart.discount_amount)}`;
    discountRow.classList.remove('d-none');
  } else {
    discountRow.classList.add('d-none');
  }
}

async function changeQty(productId, qty) {
  const cart = await api('/api/cart/quantity', 'POST', { product_id: productId, quantity: qty });
  renderCart(cart);
}

async function removeFromCart(productId) {
  const cart = await api('/api/cart/remove', 'POST', { product_id: productId });
  renderCart(cart);
}

async function clearCart() {
  // 全商品を削除
  let cart = await api('/api/cart');
  for (const item of cart.items) {
    cart = await api('/api/cart/remove', 'POST', { product_id: item.product_id });
  }
  cart = await api('/api/cart/discount', 'POST', { discount_type: null, value: 0 });
  renderCart(cart);
}

async function applyDiscount() {
  const value = parseFloat(document.getElementById('discountValue').value);
  const type  = document.getElementById('discountType').value;
  if (!value || value <= 0) return;
  const cart = await api('/api/cart/discount', 'POST', { discount_type: type, value });
  renderCart(cart);
}

async function clearDiscount() {
  const cart = await api('/api/cart/discount', 'POST', { discount_type: null, value: 0 });
  renderCart(cart);
}

async function checkout() {
  const result = await api('/api/checkout', 'POST');
  if (result.error) { alert(result.error); return; }

  renderReceipt(result);
  new bootstrap.Modal(document.getElementById('receiptModal')).show();
  renderCart({ items: [], subtotal_ex_tax: 0, total_tax: 0, total: 0, discount_amount: 0 });
}

function renderReceipt(data) {
  const now   = new Date();
  const stamp = `${now.getFullYear()}年${now.getMonth()+1}月${now.getDate()}日 ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const lines = [
    '══════════════════════════════',
    '         レ シ ー ト          ',
    `  ${stamp}`,
    '══════════════════════════════',
  ];

  data.items.forEach(i => {
    const mark = i.tax_category === 'reduced' ? '※' : '　';
    lines.push(`${mark}${i.name.padEnd(12)} x${i.quantity}   ${fmt(i.subtotal)}`);
  });

  lines.push('──────────────────────────────');
  lines.push(`  小計（税抜）      ${fmt(data.subtotal_ex_tax)}`);
  lines.push(`  消費税            ${fmt(data.total_tax)}`);

  if (data.discount_amount > 0) {
    lines.push(`  割引              −${fmt(data.discount_amount)}`);
  }

  lines.push('══════════════════════════════');
  lines.push(`  合　計            ${fmt(data.total)}`);
  lines.push('══════════════════════════════');

  if (data.customer_name) {
    lines.push(`  顧客: ${data.customer_name}`);
    lines.push(`  獲得ポイント: +${data.points_earned || 0}pt`);
  }

  lines.push('  ※ 軽減税率（8%）対象商品');
  lines.push('  ありがとうございました！');

  document.getElementById('receiptContent').textContent = lines.join('\n');
}

/* ══════════════════════════════════════════
   顧客管理画面
   ══════════════════════════════════════════ */
let allCustomers = [];

function initCustomers() {
  loadCustomers();
  document.getElementById('searchInput').addEventListener('input', filterCustomers);
}

async function loadCustomers() {
  allCustomers = await api('/api/customers');
  renderCustomers(allCustomers);
}

function renderCustomers(list) {
  const tbody = document.getElementById('customerTable');
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">顧客が登録されていません</td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(c => `
    <tr>
      <td>
        <a href="/customers/${c.id}" class="fw-semibold text-decoration-none">
          ${c.name}
        </a>
      </td>
      <td class="text-muted">${c.email || '—'}</td>
      <td class="text-muted">${c.phone || '—'}</td>
      <td class="text-center">
        <span class="badge bg-warning text-dark">
          <i class="bi bi-star-fill me-1"></i>${c.points.toLocaleString()}pt
        </span>
      </td>
      <td class="text-muted small">${(c.created_at || '').slice(0, 10)}</td>
      <td class="text-center">
        <button class="btn btn-sm btn-outline-primary me-1"
                onclick='openEdit(${JSON.stringify(c)})'>
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger"
                onclick="deleteCustomer(${c.id}, '${c.name}')">
          <i class="bi bi-trash3"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

function filterCustomers() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = allCustomers.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.email  || '').toLowerCase().includes(q) ||
    (c.phone  || '').includes(q)
  );
  renderCustomers(filtered);
}

async function createCustomer() {
  const body = {
    name:    document.getElementById('addName').value.trim(),
    email:   document.getElementById('addEmail').value.trim(),
    phone:   document.getElementById('addPhone').value.trim(),
    address: document.getElementById('addAddress').value.trim(),
  };
  const res = await api('/api/customers', 'POST', body);
  const errEl = document.getElementById('addError');
  if (res.error) {
    errEl.textContent = res.error;
    errEl.classList.remove('d-none');
    return;
  }
  bootstrap.Modal.getInstance(document.getElementById('addModal')).hide();
  ['addName','addEmail','addPhone','addAddress'].forEach(id => document.getElementById(id).value = '');
  errEl.classList.add('d-none');
  loadCustomers();
}

function openEdit(customer) {
  document.getElementById('editId').value      = customer.id;
  document.getElementById('editName').value    = customer.name;
  document.getElementById('editEmail').value   = customer.email    || '';
  document.getElementById('editPhone').value   = customer.phone    || '';
  document.getElementById('editAddress').value = customer.address  || '';
  document.getElementById('editError').classList.add('d-none');
  new bootstrap.Modal(document.getElementById('editModal')).show();
}

async function updateCustomer() {
  const id   = parseInt(document.getElementById('editId').value);
  const body = {
    name:    document.getElementById('editName').value.trim(),
    email:   document.getElementById('editEmail').value.trim(),
    phone:   document.getElementById('editPhone').value.trim(),
    address: document.getElementById('editAddress').value.trim(),
  };
  const res = await api(`/api/customers/${id}`, 'PUT', body);
  const errEl = document.getElementById('editError');
  if (res.error) {
    errEl.textContent = res.error;
    errEl.classList.remove('d-none');
    return;
  }
  bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
  errEl.classList.add('d-none');
  loadCustomers();
}

async function deleteCustomer(id, name) {
  if (!confirm(`「${name}」を削除してもよいですか？`)) return;
  await api(`/api/customers/${id}`, 'DELETE');
  loadCustomers();
}

/* ══════════════════════════════════════════
   商品管理画面
   ══════════════════════════════════════════ */
const TAX_RATE = { standard: 0.10, reduced: 0.08 };

let allProducts = [];
let allCategories = [];
let activeProductCategory = null;

async function initProducts() {
  await loadCategories();
  loadProducts();
}

// ── カテゴリー ────────────────────────────

async function loadCategories() {
  allCategories = await api('/api/categories');
  renderCategoryTabs();
  renderCategorySelects();
  renderCategoryList();
}

function renderCategoryTabs() {
  const tabs = document.getElementById('productCategoryTabs');
  if (!tabs) return;
  tabs.innerHTML = `<button class="btn btn-sm btn-primary" onclick="filterProducts(null)" id="pcat-all">すべて</button>`;
  allCategories.forEach(c => {
    tabs.innerHTML += ` <button class="btn btn-sm btn-outline-primary" onclick="filterProducts(${c.id})" id="pcat-${c.id}">${c.name}</button>`;
  });
}

function renderCategorySelects() {
  ['addPCategory', 'editPCategory'].forEach(selId => {
    const sel = document.getElementById(selId);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">未分類</option>';
    allCategories.forEach(c => {
      sel.innerHTML += `<option value="${c.id}">${c.name}</option>`;
    });
    sel.value = current;
  });
}

function renderCategoryList() {
  const list = document.getElementById('categoryList');
  if (!list) return;
  if (allCategories.length === 0) {
    list.innerHTML = '<li class="list-group-item text-muted text-center small">カテゴリーがありません</li>';
    return;
  }
  list.innerHTML = allCategories.map(c => `
    <li class="list-group-item d-flex justify-content-between align-items-center">
      <span>${c.name}</span>
      <button class="btn btn-sm btn-outline-danger" onclick="deleteCategory(${c.id}, '${c.name.replace(/'/g, "\\'")}')">
        <i class="bi bi-trash3"></i>
      </button>
    </li>
  `).join('');
}

function filterProducts(categoryId) {
  activeProductCategory = categoryId;
  document.querySelectorAll('#productCategoryTabs .btn').forEach(b => {
    b.classList.remove('btn-primary');
    b.classList.add('btn-outline-primary');
  });
  const btn = categoryId ? document.getElementById(`pcat-${categoryId}`) : document.getElementById('pcat-all');
  if (btn) { btn.classList.remove('btn-outline-primary'); btn.classList.add('btn-primary'); }
  const filtered = categoryId ? allProducts.filter(p => p.category_id == categoryId) : allProducts;
  renderProducts(filtered);
}

async function createCategory() {
  const name = document.getElementById('newCategoryName').value.trim();
  const errEl = document.getElementById('categoryError');
  if (!name) return;
  const res = await api('/api/categories', 'POST', { name });
  if (res.error) {
    errEl.textContent = res.error;
    errEl.classList.remove('d-none');
    return;
  }
  errEl.classList.add('d-none');
  document.getElementById('newCategoryName').value = '';
  await loadCategories();
}

async function deleteCategory(id, name) {
  if (!confirm(`「${name}」を削除してもよいですか？\n※ このカテゴリーの商品は「未分類」になります。`)) return;
  await api(`/api/categories/${id}`, 'DELETE');
  await loadCategories();
  loadProducts();
}

// ── 商品 ──────────────────────────────────

async function loadProducts() {
  allProducts = await api('/api/products');
  filterProducts(activeProductCategory);
}

function renderProducts(list) {
  const tbody = document.getElementById('productTable');
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">商品が登録されていません</td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(p => {
    const taxed = Math.round(p.price * (1 + TAX_RATE[p.tax_category]));
    return `
      <tr>
        <td class="text-muted small">${p.id}</td>
        <td class="text-center fs-5">${p.emoji || '—'}</td>
        <td class="fw-semibold">${p.name}</td>
        <td>
          ${p.category_name
            ? `<span class="badge bg-light text-dark border">${p.category_name}</span>`
            : '<span class="text-muted small">—</span>'}
        </td>
        <td class="text-end">¥${p.price.toLocaleString()}</td>
        <td class="text-end fw-bold text-primary">¥${taxed.toLocaleString()}</td>
        <td class="text-center">
          ${p.tax_category === 'reduced'
            ? '<span class="badge bg-success">軽減8%</span>'
            : '<span class="badge bg-secondary">標準10%</span>'}
        </td>
        <td class="text-center">
          <button class="btn btn-sm btn-outline-primary me-1"
                  onclick='openEditProduct(${JSON.stringify(p)})'>
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger"
                  onclick="deleteProduct(${p.id}, '${p.name.replace(/'/g, "\\'")}')">
            <i class="bi bi-trash3"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function createProduct() {
  const body = {
    name:         document.getElementById('addPName').value.trim(),
    price:        parseFloat(document.getElementById('addPPrice').value),
    tax_category: document.getElementById('addPTax').value,
    emoji:        document.getElementById('addPEmoji').value.trim(),
    category_id:  document.getElementById('addPCategory').value || null,
  };
  const res = await api('/api/products', 'POST', body);
  const errEl = document.getElementById('addProductError');
  if (res.error) {
    errEl.textContent = res.error;
    errEl.classList.remove('d-none');
    return;
  }
  bootstrap.Modal.getInstance(document.getElementById('addProductModal')).hide();
  ['addPName', 'addPPrice', 'addPEmoji'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('addPTax').value = 'standard';
  document.getElementById('addPCategory').value = '';
  errEl.classList.add('d-none');
  loadProducts();
}

function openEditProduct(p) {
  document.getElementById('editPId').value       = p.id;
  document.getElementById('editPName').value     = p.name;
  document.getElementById('editPPrice').value    = p.price;
  document.getElementById('editPTax').value      = p.tax_category;
  document.getElementById('editPEmoji').value    = p.emoji || '';
  document.getElementById('editPCategory').value = p.category_id || '';
  document.getElementById('editProductError').classList.add('d-none');
  new bootstrap.Modal(document.getElementById('editProductModal')).show();
}

async function updateProduct() {
  const id   = parseInt(document.getElementById('editPId').value);
  const body = {
    name:         document.getElementById('editPName').value.trim(),
    price:        parseFloat(document.getElementById('editPPrice').value),
    tax_category: document.getElementById('editPTax').value,
    emoji:        document.getElementById('editPEmoji').value.trim(),
    category_id:  document.getElementById('editPCategory').value || null,
  };
  const res = await api(`/api/products/${id}`, 'PUT', body);
  const errEl = document.getElementById('editProductError');
  if (res.error) {
    errEl.textContent = res.error;
    errEl.classList.remove('d-none');
    return;
  }
  bootstrap.Modal.getInstance(document.getElementById('editProductModal')).hide();
  errEl.classList.add('d-none');
  loadProducts();
}

async function deleteProduct(id, name) {
  if (!confirm(`「${name}」を削除してもよいですか？\n※ POSの商品一覧からも削除されます。`)) return;
  await api(`/api/products/${id}`, 'DELETE');
  loadProducts();
}

/* ══════════════════════════════════════════
   購入履歴画面
   ══════════════════════════════════════════ */
let allHistory = [];

function initHistory() {
  loadHistory();
  document.getElementById('historySearch').addEventListener('input', filterHistory);
  document.getElementById('dateFrom').addEventListener('change', filterHistory);
  document.getElementById('dateTo').addEventListener('change', filterHistory);
}

async function loadHistory() {
  allHistory = await api('/api/history');
  renderHistory(allHistory);
}

function renderHistory(list) {
  document.getElementById('totalBadge').textContent = `${list.length} 件`;

  const total   = list.reduce((s, p) => s + p.total, 0);
  const avg     = list.length ? total / list.length : 0;
  document.getElementById('sumCount').textContent   = list.length.toLocaleString();
  document.getElementById('sumRevenue').textContent = fmt(total);
  document.getElementById('sumAvg').textContent     = fmt(avg);

  const tbody = document.getElementById('historyTable');
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">履歴がありません</td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(p => `
    <tr>
      <td class="text-muted small">#${p.id}</td>
      <td class="small">${(p.created_at || '').slice(0, 16)}</td>
      <td>
        ${p.customer_id
          ? `<a href="/customers/${p.customer_id}" class="text-decoration-none">${p.customer_name || '—'}</a>`
          : '<span class="text-muted">ゲスト</span>'}
      </td>
      <td class="text-end fw-bold text-primary">${fmt(p.total)}</td>
      <td class="text-end text-danger small">
        ${p.discount_amount > 0 ? `−${fmt(p.discount_amount)}` : '—'}
      </td>
      <td class="text-center">
        <button class="btn btn-sm btn-outline-secondary"
                onclick="showDetail(${p.id})">
          <i class="bi bi-list-ul"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

function filterHistory() {
  const q    = document.getElementById('historySearch').value.toLowerCase();
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;

  const filtered = allHistory.filter(p => {
    const name = (p.customer_name || 'ゲスト').toLowerCase();
    const date = (p.created_at || '').slice(0, 10);
    return name.includes(q)
      && (!from || date >= from)
      && (!to   || date <= to);
  });
  renderHistory(filtered);
}

function resetFilter() {
  document.getElementById('historySearch').value = '';
  document.getElementById('dateFrom').value      = '';
  document.getElementById('dateTo').value        = '';
  renderHistory(allHistory);
}

async function showDetail(purchaseId) {
  const data = await api(`/api/history/${purchaseId}`);
  const rows = (data.items || []).map(i => `
    <tr>
      <td>${i.product_name}
        ${i.tax_category === 'reduced' ? '<span class="badge bg-success ms-1" style="font-size:.6rem">軽減8%</span>' : ''}
      </td>
      <td class="text-center">${i.quantity}</td>
      <td class="text-end">${fmt(i.unit_price)}</td>
      <td class="text-end fw-bold">${fmt(i.subtotal)}</td>
    </tr>
  `).join('');

  document.getElementById('detailBody').innerHTML = `
    <p class="text-muted small mb-2">購入日時: ${(data.created_at || '').slice(0,16)}</p>
    <table class="table table-sm">
      <thead class="table-light">
        <tr><th>商品名</th><th class="text-center">数量</th>
            <th class="text-end">単価（税抜）</th><th class="text-end">小計（税込）</th></tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot class="table-light fw-bold">
        <tr>
          <td colspan="3" class="text-end">
            ${data.discount_amount > 0 ? `割引: −${fmt(data.discount_amount)}<br>` : ''}合計
          </td>
          <td class="text-end text-primary">${fmt(data.total)}</td>
        </tr>
      </tfoot>
    </table>
  `;
  new bootstrap.Modal(document.getElementById('detailModal')).show();
}
