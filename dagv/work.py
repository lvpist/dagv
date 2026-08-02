"""The work spine: an área owns work, work is a Task, every área has a board.

Until now the only data in the system was membership records — which is why
every page could only ever be a list of people. A student union does not run on
a directory; it runs on **things that need doing, by someone, by a date**. That
is exactly what ERPNext's Task already is, so we adopt it instead of inventing
a parallel world: assignment, due dates, comments, notifications, the Kanban
board and the mobile app all come for free.

    DAGV Area  ──┐
                 ├─ Task.dagv_area   which área owns this piece of work
    Project    ──┘  (optional: a named initiative inside an área)

An área is the permanent org unit; a Project is an optional initiative inside it
("Calourada 2027"). Tagging the *área* rather than forcing a project keeps the
everyday case to one field, and lets the boards exist without anyone having to
set up projects first.

Nothing here is hard-coded per área: create an área record and its board,
shortcut and permissions appear on the next sync. That is the whole point — the
2028 leadership reorganises the DAGV from the interface, not from this file.
"""

import frappe
from frappe.utils import add_days, nowdate

AREA_FIELD = "dagv_area"

# Statuses that mean "still someone's problem". Task also has Template and
# Cancelled, which are deliberately not work.
OPEN_STATUSES = ["Open", "Working", "Pending Review", "Overdue"]

# Board columns, left to right. Overdue sits first on purpose: the leftmost
# column is what the eye lands on, and late work is the thing a board exists to
# make impossible to ignore. ERPNext moves tasks into Overdue by itself.
BOARD_COLUMNS = [
    ("Overdue", "Red"),
    ("Open", "Gray"),
    ("Working", "Blue"),
    ("Pending Review", "Orange"),
    ("Completed", "Green"),
]


# ---------------------------------------------------------------------------
# The field that ties work to an área
# ---------------------------------------------------------------------------

def ensure_area_field():
    """Put a `Área` link on Task and Project.

    A Custom Field rather than a fork of the doctype, so ERPNext keeps updating
    Task normally and this survives every upgrade.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {
            "Task": [
                {
                    "fieldname": AREA_FIELD,
                    "label": "Área",
                    "fieldtype": "Link",
                    "options": "DAGV Area",
                    "insert_after": "subject",
                    "in_standard_filter": 1,
                    "in_list_view": 1,
                    "reqd": 1,
                    "description": "De qual área é esse trabalho.",
                }
            ],
            "Project": [
                {
                    "fieldname": AREA_FIELD,
                    "label": "Área",
                    "fieldtype": "Link",
                    "options": "DAGV Area",
                    "insert_after": "project_name",
                    "in_standard_filter": 1,
                    "in_list_view": 1,
                }
            ],
        },
        ignore_validate=True,
    )
    frappe.db.commit()
    return {"field": AREA_FIELD}


# ---------------------------------------------------------------------------
# Who is in what
# ---------------------------------------------------------------------------

def my_areas(user=None):
    """Áreas the person actually belongs to. The unit of access in this system."""
    user = user or frappe.session.user
    return frappe.get_all(
        "DAGV Membership",
        filters={"member": user, "status": "Approved"},
        pluck="area",
    )


def active_areas():
    return frappe.get_all(
        "DAGV Area",
        filters={"is_active": 1},
        fields=["name", "area_name", "category", "sort_order"],
        order_by="sort_order asc, area_name asc",
    )


# ---------------------------------------------------------------------------
# One board per área
# ---------------------------------------------------------------------------

BOARD = "Quadro DAGV"


def ensure_board():
    """One board for the whole DAGV — which is not the same as one board for
    everyone.

    The obvious design was fifteen boards, one per área. It is the wrong one:
    it puts thirteen boards a person will never open in front of them, and it
    needs regenerating every time a leadership reorganises. Instead there is a
    single board and the *permission layer* filters it, so each person opens it
    and sees their áreas' work and nothing else. Narrowing to one área is the
    Área dropdown in the filter bar, which is there because the field is a
    standard filter.

    Public (private=0): a board only your own eyes can see is a to-do list.
    """
    doc = (
        frappe.get_doc("Kanban Board", BOARD)
        if frappe.db.exists("Kanban Board", BOARD)
        else frappe.new_doc("Kanban Board")
    )
    doc.kanban_board_name = BOARD
    doc.reference_doctype = "Task"
    doc.field_name = "status"
    doc.private = 0
    doc.show_labels = 1
    doc.filters = frappe.as_json([["Task", "status", "not in", ["Template", "Cancelled"]]])

    doc.set("columns", [])
    for column, indicator in BOARD_COLUMNS:
        doc.append("columns", {"column_name": column, "status": "Active",
                               "indicator": indicator})

    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return {"board": BOARD}


# ---------------------------------------------------------------------------
# Number cards — the personal ones
# ---------------------------------------------------------------------------
# A Number Card of type "Custom" calls a whitelisted method and uses both the
# value AND the route it returns. That is the only card type that can answer a
# question about *the person looking at it*, and clicking it lands on exactly
# those records instead of an unfiltered list.

def _mine(extra=None):
    user = frappe.session.user
    filters = {"_assign": ["like", f"%{user}%"], "status": ["in", OPEN_STATUSES]}
    if extra:
        filters.update(extra)
    return filters


def _card(filters):
    """The shape a Custom number card expects back.

    `fieldtype` is not decoration: the widget passes this whole dict to
    frappe.format() as if it were a docfield, and with no fieldtype it formats
    the count as **currency** — "R$ 3,00" open tasks. `route` and
    `route_options` are what make the number clickable, landing on exactly the
    records it counted instead of an unfiltered list.
    """
    return {
        "value": frappe.db.count("Task", filters),
        "fieldtype": "Int",
        "route": ["List", "Task"],
        "route_options": filters,
    }


@frappe.whitelist()
def card_my_tasks(filters=None):
    """Everything assigned to me that is not finished."""
    return _card(_mine())


@frappe.whitelist()
def card_my_week(filters=None):
    """Mine, due in the next seven days — the horizon a student plans on."""
    return _card(_mine({"exp_end_date": ["between", [nowdate(), add_days(nowdate(), 7)]]}))


@frappe.whitelist()
def card_my_late(filters=None):
    """Mine, past due. The number that should be zero."""
    return _card(_mine({"exp_end_date": ["<", nowdate()]}))


def _area_scope():
    """Which áreas this card should count.

    For the executive "minhas áreas" is the whole DAGV — they answer for all of
    it — so they get no área filter rather than the accident of which áreas they
    happen to hold a membership row in. Returns None for "no filter".
    """
    from dagv.permissions import is_unrestricted

    if is_unrestricted():
        return None
    return my_areas()


@frappe.whitelist()
def card_area_open(filters=None):
    """Open work across every área I am in — my team's load, not just mine."""
    areas = _area_scope()
    if areas == []:
        return {"value": 0, "route": ["List", "Task"], "route_options": {}}
    f = {"status": ["in", OPEN_STATUSES]}
    if areas:
        f[AREA_FIELD] = ["in", areas]
    return _card(f)


@frappe.whitelist()
def card_area_unowned(filters=None):
    """Work in my áreas with nobody assigned.

    The most useful number on the page: a task with no owner is the one that
    quietly never happens. Frappe leaves `_assign` as NULL or an empty JSON
    array depending on whether it was ever touched, so both count as nobody.
    """
    areas = _area_scope()
    if areas == []:
        return {"value": 0, "route": ["List", "Task"], "route_options": {}}
    f = {"status": ["in", OPEN_STATUSES], "_assign": ["in", ["", "[]", None]]}
    if areas:
        f[AREA_FIELD] = ["in", areas]
    return _card(f)


CARDS = [
    # (label, method, colour)
    ("Comigo agora", "dagv.work.card_my_tasks", "#4C6EF5"),
    ("Vence em 7 dias", "dagv.work.card_my_week", "#C2740E"),
    ("Atrasadas", "dagv.work.card_my_late", "#C0392B"),
    ("Abertas nas minhas áreas", "dagv.work.card_area_open", "#2F7D4F"),
    ("Sem responsável", "dagv.work.card_area_unowned", "#868E96"),
]


def ensure_cards():
    """Register the personal cards. `document_type` is still required on a Custom
    card — Frappe uses it for the read check that decides who may see the card."""
    made = []
    for label, method, color in CARDS:
        doc = (
            frappe.get_doc("Number Card", label)
            if frappe.db.exists("Number Card", label)
            else frappe.new_doc("Number Card")
        )
        doc.label = label
        doc.type = "Custom"
        doc.method = method
        doc.document_type = "Task"
        doc.is_public = 1
        doc.show_percentage_stats = 0
        doc.color = color
        doc.module = "DAGV"
        # Number Card defaults `currency` to the company's, and the widget then
        # formats ANY card as money — "R$ 3,00" open tasks. These count things,
        # never reais. Cleared explicitly, and shown in full so a count is the
        # exact number rather than a shortened "1 K".
        doc.currency = None
        doc.show_full_number = 1
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(doc.name)

    frappe.db.commit()
    return {"cards": made}


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def ensure_charts():
    """Two comparisons worth looking at: load per área, and work per status."""
    made = []

    specs = [
        ("Trabalho por área", "Group By", {"group_by_based_on": AREA_FIELD}, "#B69B1A", "Bar"),
        ("Trabalho por situação", "Group By", {"group_by_based_on": "status"}, "#4C6EF5", "Donut"),
    ]
    for name, chart_type, extra, color, viz in specs:
        doc = (
            frappe.get_doc("Dashboard Chart", name)
            if frappe.db.exists("Dashboard Chart", name)
            else frappe.new_doc("Dashboard Chart")
        )
        doc.chart_name = name
        doc.chart_type = chart_type
        doc.document_type = "Task"
        doc.group_by_type = "Count"
        doc.number_of_groups = 0
        # A LIST of conditions. A dict silently breaks the chart at render time.
        doc.filters_json = frappe.as_json([["Task", "status", "in", OPEN_STATUSES]])
        doc.type = viz
        doc.color = color
        doc.is_public = 1
        doc.module = "DAGV"
        for key, value in extra.items():
            setattr(doc, key, value)
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(doc.name)

    frappe.db.commit()
    return {"charts": made}


# ---------------------------------------------------------------------------
# Sensible defaults when someone creates work
# ---------------------------------------------------------------------------

def set_task_defaults(doc, method=None):
    """Fill the área in when it is not ambiguous, so the common case is one less
    field to think about. Someone in a single área never picks it at all."""
    if doc.get(AREA_FIELD):
        return
    areas = my_areas()
    if len(areas) == 1:
        doc.set(AREA_FIELD, areas[0])


def guard_task_area(doc, method=None):
    """You cannot file work into an área you are not in.

    The form only offers your áreas (see area_link_query), but a dropdown is a
    convenience, not a rule — the API is still open. Enforced here so the answer
    is the same however the record arrives.
    """
    from dagv.permissions import is_unrestricted

    if is_unrestricted() or not doc.get(AREA_FIELD):
        return
    if doc.get(AREA_FIELD) not in my_areas():
        frappe.throw(
            f"Você não faz parte da área {doc.get(AREA_FIELD)}, "
            "então não pode criar trabalho nela.",
            title="Área não permitida",
        )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def area_link_query(doctype, txt, searchfield, start, page_len, filters):
    """The Área dropdown on a Task offers only the áreas you are in."""
    from dagv.permissions import is_unrestricted

    conditions = {"is_active": 1}
    if not is_unrestricted():
        allowed = my_areas()
        if not allowed:
            return []
        conditions["name"] = ["in", allowed]
    if txt:
        conditions["area_name"] = ["like", f"%{txt}%"]

    return frappe.get_all(
        "DAGV Area",
        filters=conditions,
        fields=["name", "category"],
        order_by="sort_order asc, area_name asc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True,
    )


# ERPNext's pt-BR translation covers some Task statuses and not others, so the
# board came out reading "Aberto / Working / Pending Review / Concluído". These
# are the gaps, filled through Frappe's own Translation records — the same thing
# the interface would write, so nothing here is a fork.
TRANSLATIONS = {
    "Working": "Em andamento",
    "Pending Review": "Em revisão",
    "Overdue": "Atrasado",
    "Template": "Modelo",
}


def ensure_translations():
    lang = frappe.db.get_single_value("System Settings", "language") or "pt-BR"
    if not lang.lower().startswith("pt"):
        return {"skipped": lang}

    made = []
    for source, translated in TRANSLATIONS.items():
        existing = frappe.db.exists(
            "Translation", {"language": lang, "source_text": source}
        )
        doc = (
            frappe.get_doc("Translation", existing)
            if existing
            else frappe.new_doc("Translation")
        )
        doc.language = lang
        doc.source_text = source
        doc.translated_text = translated
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(source)

    frappe.cache().delete_keys("translations")
    frappe.db.commit()
    return {"language": lang, "translated": made}


def sync():
    """Everything in this module, in dependency order."""
    ensure_area_field()
    ensure_board()
    ensure_cards()
    ensure_charts()
    ensure_translations()
    return {"ok": True}
