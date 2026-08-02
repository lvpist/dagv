"""Who can see and change what.

The rule the whole system rests on: **your área is your boundary.** You see the
work of the áreas you belong to and the membership record that is yours; you do
not see, and cannot touch, everybody else's.

This is not a nicety. With ~80 members, a role that can write every record means
any one of them can rewrite the DAGV's books by opening a list and typing. The
previous version granted exactly that by accident, which is why permissions now
live in one reviewed file instead of being implied by whatever a page needed to
render.

Three layers, deliberately:

    DocType permission     may this role ever do this?      (coarse, in setup)
    permission_query_*     which rows appear in a list?     (here)
    has_permission         may this row be opened/changed?  (here)

The query condition and the row check must agree — Frappe uses the first for
lists and reports and the second for a single document. A rule enforced in only
one of them is a hole.
"""

import frappe

MEMBER_ROLE = "DAGV Member"
LEAD_ROLE = "DAGV Liderança"
BOARD_ROLE = "DAGV Diretoria"
MANAGER_ROLE = "DAGV User Manager"

# Ranks that make someone responsible for an área.
LEAD_RANKS = ("Coordenador", "Diretor", "Vice-Diretor")

# Whoever holds one of these sees the whole DAGV. Kept tiny on purpose.
UNRESTRICTED = {"Administrator", "System Manager", BOARD_ROLE, MANAGER_ROLE}


def is_unrestricted(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(UNRESTRICTED.intersection(frappe.get_roles(user)))


def areas_of(user=None, ranks=None):
    """Áreas the user belongs to, optionally only those they lead."""
    user = user or frappe.session.user
    filters = {"member": user, "status": "Approved"}
    if ranks:
        filters["rank"] = ["in", list(ranks)]
    return frappe.get_all("DAGV Membership", filters=filters, pluck="area")


def led_areas(user=None):
    return areas_of(user, ranks=LEAD_RANKS)


def _in_clause(values):
    return ", ".join(frappe.db.escape(v) for v in values)


# ---------------------------------------------------------------------------
# DAGV Membership — the record that says who you are in the DAGV
# ---------------------------------------------------------------------------

def membership_query(user):
    """A member sees their own memberships. A lead also sees their área's."""
    user = user or frappe.session.user
    if is_unrestricted(user):
        return ""

    clauses = [f"`tabDAGV Membership`.member = {frappe.db.escape(user)}"]
    led = led_areas(user)
    if led:
        clauses.append(f"`tabDAGV Membership`.area in ({_in_clause(led)})")
    return "(" + " or ".join(clauses) + ")"


def membership_permission(doc, user=None, permission_type=None):
    """Reading is yours-or-your-área. Deciding belongs to whoever leads the área.

    Nobody edits their own membership: rank and status are decisions other
    people make about you, and a member who can set their own rank is not a
    member, it is an administrator.
    """
    user = user or frappe.session.user
    if is_unrestricted(user):
        return True

    led = led_areas(user)

    if permission_type in (None, "read"):
        return doc.member == user or doc.area in led

    if permission_type == "create":
        # Guarded further in `guard_membership`: whatever is submitted, a plain
        # member can only ever create a pending request for themselves.
        return True

    # write / delete / submit / cancel / share / email
    return doc.area in led


def guard_membership(doc, method=None):
    """Force a self-service request to actually be one.

    Anyone may ask to join an área; nobody may quietly grant it to themselves.
    Leads keep the ability to add someone straight into the área they run.
    """
    user = frappe.session.user
    if is_unrestricted(user):
        return

    if doc.area in led_areas(user):
        # A lead adding somebody to their own área — legitimate, leave it alone.
        return

    doc.member = user
    doc.status = "Requested"
    doc.rank = "Membro"
    doc.decided_by = None
    doc.decided_on = None
    if not doc.requested_on:
        doc.requested_on = frappe.utils.now()


# ---------------------------------------------------------------------------
# Task / Project — the work itself
# ---------------------------------------------------------------------------

def _work_query(doctype, user):
    """Work is visible inside the áreas you belong to.

    Plus anything assigned to you or created by you, so a task can be handed
    across áreas without disappearing from the one person who has to do it.
    """
    user = user or frappe.session.user
    if is_unrestricted(user):
        return ""

    table = f"`tab{doctype}`"
    like = frappe.db.escape(f"%{user}%")
    clauses = [
        f"{table}.owner = {frappe.db.escape(user)}",
        f"{table}._assign like {like}",
    ]
    areas = areas_of(user)
    if areas:
        clauses.append(f"{table}.dagv_area in ({_in_clause(areas)})")
    return "(" + " or ".join(clauses) + ")"


def task_query(user):
    return _work_query("Task", user)


def project_query(user):
    return _work_query("Project", user)


def work_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if is_unrestricted(user):
        return True
    if doc.get("dagv_area") and doc.get("dagv_area") in areas_of(user):
        return True
    if doc.owner == user:
        return True
    return user in (doc.get("_assign") or "")
