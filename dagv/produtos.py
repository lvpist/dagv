"""Produtos — the grife/estoque tools, kept deliberately tiny.

ERPNext can do far more than this, but a member selling camisetas at a festa
will not learn Stock Entries, UOMs and Delivery Notes. So the whole area is
three actions — **ver estoque, vender, repor** — on one page, writing real
ERPNext stock documents underneath so the reports and history stay honest.

Access is data-driven: anyone in an area whose ERP modules include Stock. That
survives the area being renamed, split or merged by a future leadership.
"""

import frappe

from dagv.approvals import APPROVED, is_user_manager

ITEM_GROUP = "Produtos DAGV"
STOCK_MODULE = "Stock"


def _company():
    return frappe.db.get_value("Company", {}, "name")


def _warehouse():
    """Where the grife lives. 'Lojas' is ERPNext's default store warehouse."""
    company = _company()
    abbr = frappe.db.get_value("Company", company, "abbr")
    for name in (f"Lojas - {abbr}", f"Stores - {abbr}"):
        if frappe.db.exists("Warehouse", name):
            return name
    return frappe.db.get_value("Warehouse", {"is_group": 0}, "name")


def _my_stock_areas(user=None):
    user = user or frappe.session.user
    areas = frappe.get_all(
        "DAGV Membership",
        filters={"member": user, "status": APPROVED},
        pluck="area",
    )
    return [
        a for a in areas
        if STOCK_MODULE in frappe.get_all(
            "DAGV Area Module", filters={"parent": a}, pluck="module"
        )
    ]


def can_use(user=None):
    return bool(is_user_manager(user) or _my_stock_areas(user))


def _guard():
    if not can_use():
        frappe.throw("Esta área é só para quem cuida dos produtos.")


def ensure_setup():
    """Create the item group the area's products live under."""
    if not frappe.db.exists("Item Group", ITEM_GROUP):
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": ITEM_GROUP,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    return {"item_group": ITEM_GROUP, "warehouse": _warehouse()}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_products():
    """Every product with what's left in stock and what it sells for."""
    _guard()
    warehouse = _warehouse()

    products = frappe.get_all(
        "Item",
        filters={"item_group": ITEM_GROUP, "disabled": 0},
        fields=["name", "item_name", "standard_rate", "image", "description"],
        order_by="item_name asc",
    )
    for p in products:
        p["qty"] = frappe.db.get_value(
            "Bin", {"item_code": p["name"], "warehouse": warehouse}, "actual_qty"
        ) or 0
    return {
        "products": products,
        "warehouse": warehouse,
        "currency": frappe.db.get_value("Company", _company(), "default_currency"),
        "can_manage": bool(is_user_manager()),
    }


# ---------------------------------------------------------------------------
# Writing — one Stock Entry per action, nothing fancier
# ---------------------------------------------------------------------------

def _movement(item, qty, kind, note=None):
    qty = float(qty or 0)
    if qty <= 0:
        frappe.throw("Informe uma quantidade maior que zero.")
    if not frappe.db.exists("Item", item):
        frappe.throw("Produto não encontrado.")

    warehouse = _warehouse()
    row = {"item_code": item, "qty": qty, "allow_zero_valuation_rate": 1}
    if kind == "Material Receipt":
        row["t_warehouse"] = warehouse
        row["basic_rate"] = frappe.db.get_value("Item", item, "valuation_rate") or 0
    else:
        row["s_warehouse"] = warehouse

    entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": kind,
            "company": _company(),
            "remarks": note or "",
            "items": [row],
        }
    )
    entry.flags.ignore_permissions = True
    entry.insert()
    entry.submit()
    frappe.db.commit()
    return entry.name


@frappe.whitelist(methods=["POST"])
def record_sale(item, qty, note=None):
    """Sold some — take it out of stock."""
    _guard()
    available = frappe.db.get_value(
        "Bin", {"item_code": item, "warehouse": _warehouse()}, "actual_qty"
    ) or 0
    if float(qty) > available:
        frappe.throw(f"Só há {int(available)} em estoque.")
    return {"ok": True, "entry": _movement(item, qty, "Material Issue", note or "Venda")}


@frappe.whitelist(methods=["POST"])
def record_restock(item, qty, note=None):
    """Received more — put it into stock."""
    _guard()
    return {
        "ok": True,
        "entry": _movement(item, qty, "Material Receipt", note or "Reposição"),
    }


@frappe.whitelist(methods=["POST"])
def create_product(item_name, price=0, cost=0):
    """Add a new product to the grife."""
    _guard()
    item_name = (item_name or "").strip()
    if not item_name:
        frappe.throw("Dê um nome ao produto.")
    if frappe.db.exists("Item", {"item_name": item_name, "item_group": ITEM_GROUP}):
        frappe.throw("Já existe um produto com esse nome.")

    ensure_setup()
    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_name,
            "item_name": item_name,
            "item_group": ITEM_GROUP,
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": float(price or 0),
            "valuation_rate": float(cost or 0),
            "include_item_in_manufacturing": 0,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()
    return {"ok": True, "item": doc.name}


@frappe.whitelist(methods=["POST"])
def set_price(item, price):
    """Change what a product sells for."""
    _guard()
    frappe.db.set_value("Item", item, "standard_rate", float(price or 0))
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def recent_movements(limit=15):
    """The last movements, so it's obvious what just happened."""
    _guard()
    rows = frappe.get_all(
        "Stock Entry",
        filters={"docstatus": 1, "stock_entry_type": ["in", ("Material Issue", "Material Receipt")]},
        fields=["name", "stock_entry_type", "posting_date", "posting_time", "remarks", "owner"],
        order_by="creation desc",
        limit=int(limit),
    )
    for r in rows:
        detail = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": r["name"]},
            fields=["item_code", "qty"],
            limit=1,
        )
        if detail:
            r.update(detail[0])
        r["who"] = frappe.db.get_value("User", r["owner"], "full_name") or r["owner"]
    return [r for r in rows if r.get("item_code")]
