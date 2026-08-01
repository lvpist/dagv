"""Approval APIs — the pipeline that turns requests into access.

Two audiences:

* **Executive / user managers** approve the *account* (a Registration Request)
  and assign the person's starting areas in the same action.
* **Directors** approve *area joins* for their own area only — the ongoing
  hopping between areas that members do from their dashboard.

Who may approve is deliberately data-driven, never hardcoded: a person can act
on an area if they hold Diretor/Vice-Diretor/Coordenador rank in it, or if they
carry one of the org-wide manager roles below. That keeps the power delegatable
when Pessoas (HR) is renamed, merged or dissolved by a future leadership.
"""

import frappe

MANAGER_ROLES = ("System Manager", "DAGV User Manager")
LEAD_RANKS = ("Diretor", "Vice-Diretor", "Coordenador")

APPROVED = "Approved"
REJECTED = "Rejected"
REQUESTED = "Requested"


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def is_user_manager(user=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return bool(roles.intersection(MANAGER_ROLES))


def led_areas(user=None):
    """Areas this person leads (and may therefore approve joins for)."""
    user = user or frappe.session.user
    if is_user_manager(user):
        return frappe.get_all("DAGV Area", filters={"is_active": 1}, pluck="name")
    return frappe.get_all(
        "DAGV Membership",
        filters={"member": user, "status": APPROVED, "rank": ["in", LEAD_RANKS]},
        pluck="area",
    )


def _guard(area):
    if area not in led_areas():
        frappe.throw("Você não tem permissão para decidir sobre esta área.")


# ---------------------------------------------------------------------------
# Director-facing: pending area joins
# ---------------------------------------------------------------------------

@frappe.whitelist()
def pending_requests():
    """Area-join requests waiting on the current user, newest first."""
    areas = led_areas()
    if not areas:
        return []

    rows = frappe.get_all(
        "DAGV Membership",
        filters={"status": REQUESTED, "area": ["in", areas]},
        fields=["name", "member", "area", "rank", "requested_on"],
        order_by="requested_on desc",
    )
    for row in rows:
        row["member_name"] = frappe.db.get_value("User", row["member"], "full_name")
        reg = frappe.db.get_value(
            "DAGV Registration Request",
            row["member"],
            ["course", "semester", "turma"],
            as_dict=True,
        )
        row.update(reg or {})
    return rows


@frappe.whitelist(methods=["POST"])
def decide(membership, approve, notes=None):
    """Approve or reject a single area-join request."""
    doc = frappe.get_doc("DAGV Membership", membership)
    _guard(doc.area)

    approve = approve in (True, 1, "1", "true", "True")
    doc.status = APPROVED if approve else REJECTED
    doc.decided_on = frappe.utils.now_datetime()
    doc.decided_by = frappe.session.user
    if notes:
        doc.notes = notes
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "status": doc.status}


# ---------------------------------------------------------------------------
# Executive-facing: account approval + starting areas
# ---------------------------------------------------------------------------

@frappe.whitelist()
def pending_registrations():
    """Sign-ups waiting for an account decision."""
    if not is_user_manager():
        frappe.throw("Apenas o executivo pode aprovar cadastros.")

    return frappe.get_all(
        "DAGV Registration Request",
        filters={"status": "Pending"},
        fields=[
            "name", "full_name", "fgv_email", "personal_email", "phone",
            "course", "turma", "semester", "desired_areas", "email_format_ok",
            "creation",
        ],
        order_by="creation desc",
    )


@frappe.whitelist()
def areas_for_picker():
    """Active areas, flagged with the course they're restricted to (if any)."""
    return frappe.get_all(
        "DAGV Area",
        filters={"is_active": 1},
        fields=["name", "short_code", "category", "required_course"],
        order_by="sort_order",
    )


@frappe.whitelist(methods=["POST"])
def approve_registration(registration, areas=None, reject=False):
    """Approve a sign-up and grant the areas the approver assigned.

    Assigned areas are created as *Approved* memberships straight away — the
    executive decides the starting areas, so they don't go back through the
    directors.
    """
    if not is_user_manager():
        frappe.throw("Apenas o executivo pode aprovar cadastros.")

    doc = frappe.get_doc("DAGV Registration Request", registration)

    if reject in (True, 1, "1", "true", "True"):
        doc.status = "Rejected"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"ok": True, "status": "Rejected"}

    if isinstance(areas, str):
        areas = frappe.parse_json(areas or "[]")
    areas = areas or []

    # Creates the account, base role and Geral workspace via doc_events.
    doc.status = APPROVED
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    email = (doc.fgv_email or "").lower().strip()
    granted = []
    for area in areas:
        if not frappe.db.exists("DAGV Area", area):
            continue
        required = frappe.db.get_value("DAGV Area", area, "required_course")
        if required and required != doc.course:
            continue  # academic VPs only take their own course
        if frappe.db.exists("DAGV Membership", {"member": email, "area": area}):
            continue
        frappe.get_doc(
            {
                "doctype": "DAGV Membership",
                "member": email,
                "area": area,
                "rank": "Membro",
                "status": APPROVED,
                "decided_on": frappe.utils.now_datetime(),
                "decided_by": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
        granted.append(area)

    frappe.db.commit()
    return {"ok": True, "status": APPROVED, "granted": granted}


# ---------------------------------------------------------------------------
# Member-facing: request an area from the dashboard
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def request_area(area):
    """A logged-in member asks to join an area."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Faça login para solicitar entrada em uma área.")
    if not frappe.db.exists("DAGV Area", area):
        frappe.throw("Área inexistente.")

    existing = frappe.db.exists("DAGV Membership", {"member": user, "area": area})
    if existing:
        doc = frappe.get_doc("DAGV Membership", existing)
        if doc.status in (APPROVED, REQUESTED):
            frappe.throw("Você já faz parte ou já solicitou esta área.")
        doc.status = REQUESTED
        doc.requested_on = frappe.utils.now_datetime()
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "DAGV Membership",
                "member": user,
                "area": area,
                "rank": "Membro",
                "status": REQUESTED,
            }
        ).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"ok": True}
