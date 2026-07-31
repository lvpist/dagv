"""DAGV provisioning logic (Phase 0).

Wired via ``doc_events`` in hooks.py. Real app code — reliable, no sandbox.

Phase 0 scope: a Registration Request, once its status becomes ``Approved``,
turns into a real system user with the base ``DAGV Member`` role, an enabled
Raven user, and membership in the org-wide ``Geral`` workspace.

Later phases (areas, ranks, per-area provisioning) build on the same module.
"""

import frappe

GERAL_WORKSPACE = "Geral"
BASE_ROLE = "DAGV Member"
FGV_DOMAIN = "@fgv.edu.br"


def validate_fgv_email(doc, method=None):
    """Reject any registration whose FGV email isn't @fgv.edu.br."""
    email = (doc.fgv_email or "").lower().strip()
    if email and not email.endswith(FGV_DOMAIN):
        frappe.throw(f"O cadastro exige um e-mail institucional {FGV_DOMAIN}")


def provision_on_approval(doc, method=None):
    """When a request is Approved, spin up the member's access.

    Idempotent: safe to run again on later saves.
    """
    if doc.status != "Approved":
        return

    email = (doc.fgv_email or "").lower().strip()
    if not email:
        return

    _ensure_user(doc, email)
    _ensure_raven_user(doc, email)
    _ensure_geral_member(email)


def _ensure_user(doc, email):
    """System user + base DAGV Member role."""
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": doc.full_name or email,
                "user_type": "System User",
                "send_welcome_email": 1,  # confirmation + set-password link (needs SMTP configured)
            }
        )
        user.append("roles", {"role": BASE_ROLE})
        user.insert(ignore_permissions=True)
    elif BASE_ROLE not in frappe.get_roles(email):
        frappe.get_doc("User", email).add_roles(BASE_ROLE)


def _ensure_raven_user(doc, email):
    """Raven user must exist AND be enabled (see the enabled=0 bug we hit)."""
    if not frappe.db.exists("Raven User", email):
        frappe.get_doc(
            {
                "doctype": "Raven User",
                "user": email,
                "full_name": doc.full_name or email,
                "type": "User",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Raven User", email, "enabled", 1)


def _ensure_geral_member(email):
    """Drop the member into the org-wide Geral workspace."""
    if not frappe.db.exists(
        "Raven Workspace Member", {"workspace": GERAL_WORKSPACE, "user": email}
    ):
        frappe.get_doc(
            {
                "doctype": "Raven Workspace Member",
                "workspace": GERAL_WORKSPACE,
                "user": email,
            }
        ).insert(ignore_permissions=True)
