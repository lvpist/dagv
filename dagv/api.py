"""Public (guest) API for the DAGV signup page."""

import frappe

# Canonical area codes (the 15 areas). Labels live in the frontend.
AREAS = [
    "VPAE", "VPAP", "VPEcono", "Cultural", "Eventos", "Financeiro",
    "Criativo", "Entidades", "Institucional", "Integração",
    "Parcerias", "Pessoas", "Planejamento", "Produtos", "Projetos",
]


@frappe.whitelist(allow_guest=True)
def submit_registration(
    full_name,
    fgv_email,
    course,
    personal_email=None,
    phone=None,
    semester=None,
    desired_areas=None,
):
    """Create a pending DAGV Registration Request from the public signup page."""
    full_name = (full_name or "").strip()
    email = (fgv_email or "").lower().strip()

    if not full_name:
        frappe.throw("Informe seu nome completo.")
    if not email.endswith("@fgv.edu.br"):
        frappe.throw("O cadastro exige um e-mail institucional @fgv.edu.br.")
    if not course:
        frappe.throw("Selecione seu curso.")
    if frappe.db.exists("DAGV Registration Request", email):
        frappe.throw("Já existe um cadastro com este e-mail — aguarde a confirmação.")

    doc = frappe.get_doc(
        {
            "doctype": "DAGV Registration Request",
            "full_name": full_name,
            "fgv_email": email,
            "personal_email": (personal_email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "semester": semester or None,
            "course": course,
            "desired_areas": (desired_areas or "").strip() or None,
            "status": "Pending",
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
