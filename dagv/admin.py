"""The control panel API — the no-code surface future leaderships live in.

Everything a non-technical successor needs to reshape the DAGV each term:
create/rename/archive areas, move people between them, promote ranks, and hand
the user-management power to whichever diretoria plays the HR role that year.

Nothing here assumes the current 15 areas or the current org chart.
"""

import frappe

from dagv.approvals import APPROVED, LEAD_RANKS, MANAGER_ROLES, is_user_manager

BASE_ROLE = "DAGV Member"
MANAGER_ROLE = "DAGV User Manager"
RANKS = ("Membro", "Coordenador", "Diretor", "Vice-Diretor")


def _guard():
    if not is_user_manager():
        frappe.throw("Apenas o executivo (ou quem tem a gestão de usuários) pode fazer isso.")


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_areas():
    _guard()
    areas = frappe.get_all(
        "DAGV Area",
        fields=["name", "short_code", "category", "description", "required_course",
                "is_active", "sort_order", "raven_workspace", "erp_role"],
        order_by="sort_order asc, name asc",
    )
    # Counted in Python: Frappe rejects SQL functions written as select strings.
    counts = {}
    for area in frappe.get_all(
        "DAGV Membership", filters={"status": APPROVED}, pluck="area"
    ):
        counts[area] = counts.get(area, 0) + 1

    for a in areas:
        a["members"] = counts.get(a["name"], 0)
        a["modules"] = frappe.get_all(
            "DAGV Area Module", filters={"parent": a["name"]}, pluck="module"
        )
    return areas


@frappe.whitelist()
def list_modules():
    """ERPNext modules an area can be given, minus Frappe's internal plumbing."""
    _guard()
    hidden = {"Core", "Custom", "Desk", "Automation", "Contacts", "Email", "Geo",
              "Integrations", "Printing", "Utilities", "Workflow", "Communication",
              "Portal", "Regional", "Setup", "Telephony", "EDI", "Bulk Transaction",
              "ERPNext Integrations", "Raven"}
    return sorted(
        m for m in frappe.get_all("Module Def", pluck="name") if m not in hidden
    )


@frappe.whitelist(methods=["POST"])
def save_area(area=None, area_name=None, short_code=None, category=None,
              description=None, required_course=None, is_active=1, sort_order=None,
              modules=None):
    """Create a new area or update an existing one."""
    _guard()

    if area and frappe.db.exists("DAGV Area", area):
        doc = frappe.get_doc("DAGV Area", area)
    else:
        if not area_name:
            frappe.throw("Dê um nome à área.")
        if frappe.db.exists("DAGV Area", area_name):
            frappe.throw(f"Já existe uma área chamada {area_name}.")
        doc = frappe.new_doc("DAGV Area")
        doc.area_name = area_name

    doc.short_code = short_code
    doc.category = category or "Suplementar"
    doc.description = description
    doc.required_course = required_course or None
    doc.is_active = 1 if str(is_active) in ("1", "True", "true") else 0
    if sort_order not in (None, ""):
        doc.sort_order = int(sort_order)

    if modules is not None:
        if isinstance(modules, str):
            modules = frappe.parse_json(modules or "[]")
        doc.set("erp_modules", [])
        for module in modules or []:
            if frappe.db.exists("Module Def", module):
                doc.append("erp_modules", {"module": module})

    doc.flags.ignore_permissions = True
    doc.save() if doc.get("name") and not doc.is_new() else doc.insert()
    frappe.db.commit()

    # Members of this area see a different slice of the ERP now.
    from dagv.provisioning import sync_module_access
    for member in frappe.get_all(
        "DAGV Membership", filters={"area": doc.name, "status": APPROVED}, pluck="member"
    ):
        sync_module_access(member)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def rename_area(area, new_name):
    """Rename an area, keeping its memberships and history intact."""
    _guard()
    new_name = (new_name or "").strip()
    if not new_name:
        frappe.throw("Informe o novo nome.")
    if new_name == area:
        return {"ok": True, "name": area}
    if frappe.db.exists("DAGV Area", new_name):
        frappe.throw(f"Já existe uma área chamada {new_name}.")

    frappe.rename_doc("DAGV Area", area, new_name, force=True)
    frappe.db.set_value("DAGV Area", new_name, "area_name", new_name)
    frappe.db.commit()
    return {"ok": True, "name": new_name}


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_people(search=None):
    """Everyone in the DAGV, with the areas and ranks they hold."""
    _guard()

    filters = {"enabled": 1}
    users = frappe.get_all(
        "User",
        filters=filters,
        fields=["name", "full_name", "enabled"],
        order_by="full_name asc",
        limit_page_length=0,
    )
    members = {u["name"]: u for u in users if BASE_ROLE in frappe.get_roles(u["name"])}

    for m in frappe.get_all(
        "DAGV Membership",
        filters={"status": APPROVED},
        fields=["name", "member", "area", "rank"],
    ):
        holder = members.get(m["member"])
        if holder is not None:
            holder.setdefault("areas", []).append(m)

    rows = []
    term = (search or "").lower().strip()
    for u in members.values():
        u.setdefault("areas", [])
        u["is_manager"] = MANAGER_ROLE in frappe.get_roles(u["name"])
        reg = frappe.db.get_value(
            "DAGV Registration Request", u["name"], ["course", "semester"], as_dict=True
        )
        u.update(reg or {})
        if term and term not in (u["name"] + " " + (u.get("full_name") or "")).lower():
            continue
        rows.append(u)
    return rows


@frappe.whitelist(methods=["POST"])
def set_rank(membership, rank):
    """Promote or demote someone inside an area."""
    _guard()
    if rank not in RANKS:
        frappe.throw("Cargo inválido.")
    doc = frappe.get_doc("DAGV Membership", membership)
    doc.rank = rank
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def assign_area(member, area, rank="Membro"):
    """Put someone into an area directly (no request/approval round-trip)."""
    _guard()
    existing = frappe.db.exists("DAGV Membership", {"member": member, "area": area})
    if existing:
        doc = frappe.get_doc("DAGV Membership", existing)
        doc.status = APPROVED
        doc.rank = rank
    else:
        doc = frappe.get_doc(
            {
                "doctype": "DAGV Membership",
                "member": member,
                "area": area,
                "rank": rank,
                "status": APPROVED,
            }
        )
    doc.decided_on = frappe.utils.now_datetime()
    doc.decided_by = frappe.session.user
    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def remove_membership(membership):
    """Take someone out of an area (revokes its workspace + role)."""
    _guard()
    doc = frappe.get_doc("DAGV Membership", membership)
    doc.status = "Removed"
    doc.decided_on = frappe.utils.now_datetime()
    doc.decided_by = frappe.session.user
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def set_manager(member, enabled=1):
    """Hand (or take back) the user-management power.

    This is what keeps the system delegatable: Pessoas holds it today, but a
    future leadership can move it anywhere without touching code.
    """
    _guard()
    user = frappe.get_doc("User", member)
    if str(enabled) in ("1", "True", "true"):
        user.add_roles(MANAGER_ROLE)
    else:
        user.remove_roles(MANAGER_ROLE)
    frappe.clear_cache(user=member)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def offboard_preview():
    """Who currently holds a leadership rank — the end-of-term checklist."""
    _guard()
    return frappe.get_all(
        "DAGV Membership",
        filters={"status": APPROVED, "rank": ["in", LEAD_RANKS]},
        fields=["name", "member", "area", "rank"],
        order_by="area asc",
    )


@frappe.whitelist(methods=["POST"])
def offboard_all_leads():
    """End of term: drop every leadership rank back to plain member.

    Accounts and history are kept — people stay in their areas as members, so
    past work keeps its authorship. Nothing is deleted.
    """
    _guard()
    done = 0
    for m in frappe.get_all(
        "DAGV Membership",
        filters={"status": APPROVED, "rank": ["in", LEAD_RANKS]},
        pluck="name",
    ):
        frappe.db.set_value("DAGV Membership", m, "rank", "Membro")
        done += 1
    frappe.db.commit()
    return {"ok": True, "demoted": done}
