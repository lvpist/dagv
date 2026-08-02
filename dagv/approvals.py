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
LEAVE_REQUESTED = "Leave Requested"

# Purpose-built pages that stand in for a whole ERPNext module. Raw ERPNext is
# too much for most members, so where we've built a simple page for a module,
# that's what they get pointed at.
MODULE_TOOLS = {
    "Stock": {"label": "Produtos", "url": "/produtos"},
}


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
        filters={"status": ["in", (REQUESTED, LEAVE_REQUESTED)], "area": ["in", areas]},
        fields=["name", "member", "area", "rank", "status", "requested_on"],
        order_by="requested_on desc",
    )
    for row in rows:
        row["kind"] = "leave" if row["status"] == LEAVE_REQUESTED else "join"
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
    if doc.status == LEAVE_REQUESTED:
        # Approving a leave takes them out; rejecting keeps them in the area.
        doc.status = "Removed" if approve else APPROVED
    else:
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

    invite = issue_invite(email)
    doc.db_set("invite_link", invite, update_modified=False)

    frappe.db.commit()
    return {
        "ok": True,
        "status": APPROVED,
        "granted": granted,
        "invite": invite,
        "full_name": doc.full_name,
        "email": email,
    }


def issue_invite(email):
    """A one-time link the approver hands over, because e-mail does not work yet.

    Approving somebody creates their account but never gives them a password —
    Frappe's answer is to e-mail a "set your password" link, and this site has
    no outgoing mail account, so an approved member had literally no way in.
    Nobody noticed because the two accounts that exist were only ever reached
    through server-side sessions.

    So the link is generated here and shown to whoever approved: they paste it
    into WhatsApp or Raven. It is Frappe's own reset mechanism, single use and
    time-limited, so it stays a real invite rather than a shared password. The
    moment SMTP exists this keeps working and the e-mail simply arrives too.
    """
    if not frappe.db.exists("User", email):
        return None
    user = frappe.get_doc("User", email)
    # `_reset_password` in this Frappe version — the public `reset_password`
    # helper is a whitelisted endpoint that *sends* mail, which is exactly the
    # step that does not work here. This generates the key and returns the URL.
    return user._reset_password(send_email=False)


INVITE_VALID_FOR = 7 * 24 * 60 * 60  # seconds


def configure_invites():
    """Give an invite long enough to survive being sent by a person.

    Frappe's default reset link lasts 20 minutes, which is right for "I forgot
    my password" and wrong for "a diretor approved you and will paste this into
    the group chat tonight". A week matches how the DAGV actually onboards, and
    the link is still single-use.
    """
    current = frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration")
    if current == INVITE_VALID_FOR:
        return {"unchanged": current}
    frappe.db.set_single_value(
        "System Settings", "reset_password_link_expiry_duration", INVITE_VALID_FOR
    )
    frappe.db.commit()
    return {"was": current, "now": INVITE_VALID_FOR}


@frappe.whitelist()
def invite_for(email):
    """Re-issue an invite — links expire, and people lose them."""
    if not is_user_manager():
        frappe.throw("Apenas o executivo pode gerar links de acesso.")
    link = issue_invite(email)
    if not link:
        frappe.throw(f"Não existe conta para {email}.")
    frappe.db.commit()
    return {"invite": link, "email": email}


# ---------------------------------------------------------------------------
# Member-facing: request an area from the dashboard
# ---------------------------------------------------------------------------

@frappe.whitelist()
def my_dashboard():
    """Everything the member's own panel needs, in one round-trip."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Faça login para ver seu painel.")

    mine = {
        m["area"]: m
        for m in frappe.get_all(
            "DAGV Membership",
            filters={"member": user, "status": ["in", (APPROVED, REQUESTED, LEAVE_REQUESTED)]},
            fields=["name", "area", "rank", "status"],
        )
    }

    areas = []
    for a in frappe.get_all(
        "DAGV Area",
        filters={"is_active": 1},
        fields=["name", "short_code", "category", "description",
                "required_course", "raven_workspace"],
        order_by="sort_order",
    ):
        held = mine.get(a["name"])
        a["membership"] = held["name"] if held else None
        a["state"] = held["status"] if held else None
        a["rank"] = held["rank"] if held else None
        areas.append(a)

    # Purpose-built pages the member's areas unlock, so the panel can link to
    # them without anyone hunting through the ERP.
    tools = []
    for name, held in mine.items():
        if held["status"] != APPROVED:
            continue
        for module in frappe.get_all(
            "DAGV Area Module", filters={"parent": name}, pluck="module"
        ):
            tool = MODULE_TOOLS.get(module)
            if tool and tool not in tools:
                tools.append(tool)

    course = frappe.db.get_value("DAGV Registration Request", user, "course")
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name") or user,
        "course": course,
        "areas": areas,
        "tools": tools,
        "can_approve": bool(led_areas()),
    }


@frappe.whitelist(methods=["POST"])
def leave_area(area):
    """Ask to leave an area.

    Leaving is a request, not an instant exit, so the area's diretoria finds out
    someone is stepping away instead of noticing a silent disappearance. Access
    stays until they decide.
    """
    user = frappe.session.user
    name = frappe.db.exists(
        "DAGV Membership", {"member": user, "area": area, "status": APPROVED}
    )
    if not name:
        frappe.throw("Você não faz parte desta área.")

    doc = frappe.get_doc("DAGV Membership", name)
    doc.status = LEAVE_REQUESTED
    doc.requested_on = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def cancel_request(area):
    """Undo a pending join or leave request."""
    user = frappe.session.user
    name = frappe.db.exists(
        "DAGV Membership",
        {"member": user, "area": area, "status": ["in", (REQUESTED, LEAVE_REQUESTED)]},
    )
    if not name:
        frappe.throw("Não há solicitação pendente para esta área.")

    doc = frappe.get_doc("DAGV Membership", name)
    # A pending leave means they're still in; a pending join means they never were.
    doc.status = APPROVED if doc.status == LEAVE_REQUESTED else "Rejected"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


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
