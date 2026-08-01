"""DAGV provisioning — the engine that turns records into real access.

Two entry points, both wired through ``doc_events``/controllers:

* ``ensure_area_backing`` — an Area owns a private Raven workspace and an
  ERPNext role. Creating an Area creates both, so a future (non-technical)
  admin never has to touch Raven or Role settings by hand.
* ``apply_membership`` — an *Approved* membership grants that area's workspace
  and role; *Rejected*/*Removed* takes them away. Everything downstream of the
  areas system flows through here.

Registration approval (Phase 0) stays below: it creates the account itself.
"""

import frappe

GERAL_WORKSPACE = "Geral"
BASE_ROLE = "DAGV Member"
FGV_DOMAIN = "@fgv.edu.br"

APPROVED = "Approved"
REVOKED = ("Rejected", "Removed")


# ---------------------------------------------------------------------------
# Registration (Phase 0)
# ---------------------------------------------------------------------------

def validate_fgv_email(doc, method=None):
    """Reject any registration whose FGV email isn't @fgv.edu.br."""
    email = (doc.fgv_email or "").lower().strip()
    if email and not email.endswith(FGV_DOMAIN):
        frappe.throw(f"O cadastro exige um e-mail institucional {FGV_DOMAIN}")


def provision_on_approval(doc, method=None):
    """When a request is Approved, spin up the member's account.

    Idempotent: safe to run again on later saves.
    """
    if doc.status != APPROVED:
        return

    email = (doc.fgv_email or "").lower().strip()
    if not email:
        return

    _ensure_user(doc, email)
    _ensure_raven_user(email, doc.full_name)
    _add_to_workspace(GERAL_WORKSPACE, email)


def _ensure_user(doc, email):
    """System user + base DAGV Member role."""
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": doc.full_name or email,
                "user_type": "System User",
                "send_welcome_email": 1,
            }
        )
        user.append("roles", {"role": BASE_ROLE})
        user.insert(ignore_permissions=True)
    elif BASE_ROLE not in frappe.get_roles(email):
        frappe.get_doc("User", email).add_roles(BASE_ROLE)


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------

def ensure_area_backing(area):
    """Give an area its private Raven workspace and ERPNext role.

    Both fields are left editable — an admin can point an area at an existing
    workspace or role instead, and we won't clobber it.
    """
    changed = {}

    if not area.raven_workspace:
        name = _ensure_workspace(area.area_name)
        if name:
            changed["raven_workspace"] = name

    if not area.erp_role:
        role = f"DAGV {area.area_name}"
        if not frappe.db.exists("Role", role):
            frappe.get_doc(
                {"doctype": "Role", "role_name": role, "desk_access": 1}
            ).insert(ignore_permissions=True)
        changed["erp_role"] = role

    if changed:
        frappe.db.set_value("DAGV Area", area.name, changed, update_modified=False)
        area.update(changed)


def _ensure_workspace(title, public=False):
    """Create (or find) a Raven workspace by title, returning its name."""
    existing = frappe.get_all(
        "Raven Workspace", filters={"workspace_name": title}, pluck="name"
    )
    if existing:
        return existing[0]

    ws = frappe.get_doc(
        {
            "doctype": "Raven Workspace",
            "workspace_name": title,
            "type": "Public" if public else "Private",
        }
    )
    ws.flags.ignore_permissions = True
    ws.insert()
    return ws.name


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------

def apply_membership(membership):
    """Grant or revoke an area's access to match the membership's status."""
    email = membership.member
    if not email or not membership.area:
        return

    area = frappe.get_cached_doc("DAGV Area", membership.area)

    if membership.status == APPROVED:
        _ensure_raven_user(email, frappe.db.get_value("User", email, "full_name"))
        if area.raven_workspace:
            _add_to_workspace(area.raven_workspace, email)
        if area.erp_role and area.erp_role not in frappe.get_roles(email):
            frappe.get_doc("User", email).add_roles(area.erp_role)

    elif membership.status in REVOKED:
        if area.raven_workspace:
            _remove_from_workspace(area.raven_workspace, email)
        if area.erp_role:
            _remove_role(email, area.erp_role)


def _ensure_raven_user(email, full_name=None):
    """Raven user must exist AND be enabled — a disabled Raven User is filtered
    out of every channel member list, which looks like a broken membership."""
    if not frappe.db.exists("Raven User", email):
        frappe.get_doc(
            {
                "doctype": "Raven User",
                "user": email,
                "full_name": full_name or email,
                "type": "User",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Raven User", email, "enabled", 1)


def _add_to_workspace(workspace, email):
    if not frappe.db.exists("Raven Workspace", workspace):
        return
    if not frappe.db.exists(
        "Raven Workspace Member", {"workspace": workspace, "user": email}
    ):
        frappe.get_doc(
            {
                "doctype": "Raven Workspace Member",
                "workspace": workspace,
                "user": email,
            }
        ).insert(ignore_permissions=True)


def _remove_from_workspace(workspace, email):
    name = frappe.db.exists(
        "Raven Workspace Member", {"workspace": workspace, "user": email}
    )
    if name:
        frappe.delete_doc(
            "Raven Workspace Member", name, force=1, ignore_permissions=True
        )


def _remove_role(email, role):
    """Drop a role, but never one another approved area still depends on."""
    still_needed = frappe.db.exists(
        "DAGV Membership",
        {"member": email, "status": APPROVED, "area": ["!=", ""]},
    )
    if still_needed:
        shared = frappe.get_all(
            "DAGV Membership",
            filters={"member": email, "status": APPROVED},
            pluck="area",
        )
        roles_in_use = {
            frappe.db.get_value("DAGV Area", a, "erp_role") for a in shared
        }
        if role in roles_in_use:
            return

    name = frappe.db.exists("Has Role", {"parent": email, "role": role})
    if name:
        frappe.delete_doc("Has Role", name, force=1, ignore_permissions=True)
