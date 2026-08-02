"""The desk index — every page, who sees it, and what they came to do.

One place that builds the whole information architecture, so it is reproducible
and survives migrations. See DAGV_arquitetura.md for the reasoning.

The rule these pages are built to, learned the hard way: **a link to a list is
not a feature.** A list view is an administrative artefact — a file browser over
a table. If a page cannot answer its question before you click anything, it is
plumbing, not a product. So every section here either shows the answer (a number
that means something, the actual rows) or offers a specific action ("Nova
tarefa"), and never a door labelled with a table name.

    Meu DAGV    todo membro   "o que depende de mim?"
    Aprovações  liderança     "o que espera decisão minha?"
    Gestão      executivo     "como está o DAGV?"

Access has three layers: the page (Workspace.roles) hides itself entirely, the
module list declutters the sidebar, and DocType permissions guard the records —
row by row, in dagv/permissions.py. Number Cards have no role field of their
own, so anything sensitive belongs on a page that is already restricted.
"""

import frappe

from dagv.permissions import BOARD_ROLE, LEAD_ROLE, MANAGER_ROLE, MEMBER_ROLE
from dagv.work import AREA_FIELD, BOARD, OPEN_STATUSES

# rank in an area -> role that unlocks the leadership page
LEAD_RANKS = ("Coordenador", "Diretor", "Vice-Diretor")


def ensure_roles():
    for role in (MEMBER_ROLE, LEAD_ROLE, BOARD_ROLE, MANAGER_ROLE):
        if not frappe.db.exists("Role", role):
            frappe.get_doc(
                {"doctype": "Role", "role_name": role, "desk_access": 1}
            ).insert(ignore_permissions=True)
    frappe.db.commit()
    return [MEMBER_ROLE, LEAD_ROLE, BOARD_ROLE, MANAGER_ROLE]


def _workspace(name, title, icon, sequence, roles, content, shortcuts=None,
               cards=None, charts=None, links=None, quick_lists=None):
    """Create or update one page, replacing its widgets wholesale."""
    doc = (
        frappe.get_doc("Workspace", name)
        if frappe.db.exists("Workspace", name)
        else frappe.new_doc("Workspace")
    )
    doc.name = name
    doc.title = title
    doc.label = title
    doc.module = "DAGV"
    doc.app = "dagv"
    doc.public = 1
    doc.is_hidden = 0
    doc.icon = icon
    doc.sequence_id = sequence
    # Must be "" and not NULL: Frappe filters these with an empty-string
    # comparison, and NULL never matches, so the page silently disappears from
    # everyone's sidebar. Every stock workspace stores "" here.
    doc.for_user = ""
    doc.parent_page = ""

    doc.set("roles", [])
    for role in roles:
        doc.append("roles", {"role": role})

    doc.set("shortcuts", [])
    for s in shortcuts or []:
        doc.append("shortcuts", s)

    # Cards, charts and quick lists must be declared here as well as referenced
    # in content, or the page renders the headers and nothing else.
    doc.set("number_cards", [])
    for c in cards or []:
        doc.append("number_cards", {"number_card_name": c, "label": c})

    doc.set("charts", [])
    for c in charts or []:
        doc.append("charts", {"chart_name": c, "label": c})

    doc.set("quick_lists", [])
    for q in quick_lists or []:
        doc.append("quick_lists", q)

    doc.set("links", [])
    for l in links or []:
        doc.append("links", l)

    doc.content = frappe.as_json(content)
    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return doc.name


def _header(idx, text):
    return {"id": f"h{idx}", "type": "header",
            "data": {"text": f'<span class="h4"><b>{text}</b></span>', "col": 12}}


def _card(idx, name, col=4):
    return {"id": f"nc{idx}", "type": "number_card",
            "data": {"number_card_name": name, "col": col}}


def _list(idx, name, col=6):
    return {"id": f"ql{idx}", "type": "quick_list",
            "data": {"quick_list_name": name, "col": col}}


def _short(idx, name, col=3):
    return {"id": f"sc{idx}", "type": "shortcut",
            "data": {"shortcut_name": name, "col": col}}


# Only 3, 4, 6 and 12 map to responsive Bootstrap classes. Anything else (col 8
# becomes a bare `col-xs-8`) keeps its width on a phone instead of going
# full-width, so the block ends up two-thirds of a narrow screen. Use these.
SPANS = (3, 4, 6, 12)


def _chart(idx, name, col=12):
    assert col in SPANS, f"col {col} has no responsive class"
    return {"id": f"ch{idx}", "type": "chart",
            "data": {"chart_name": name, "col": col}}


# ---------------------------------------------------------------------------
# Meu DAGV — the page a member actually opens
# ---------------------------------------------------------------------------

def build_meu_dagv():
    """Answers "o que depende de mim?" before a single click.

    Three numbers about *you* (not about the DAGV), then the actual rows of the
    work you owe, then your área's load, then the two things you might come here
    to do: create work, or open the board. The membership records that used to
    be the whole page are now one modest link at the bottom, which is roughly
    their real importance in someone's week.
    """
    shortcuts = [
        {"label": "Nova tarefa", "type": "DocType", "link_to": "Task",
         "doc_view": "New", "color": "#2F7D4F"},
        {"label": "Abrir o quadro", "type": "DocType", "link_to": "Task",
         "doc_view": "Kanban", "kanban_board": BOARD, "color": "#4C6EF5"},
        {"label": "Abrir o chat", "type": "URL", "url": "/raven", "color": "#B69B1A"},
        {"label": "Minhas áreas e cargos", "type": "DocType",
         "link_to": "DAGV Membership", "doc_view": "List", "color": "#868E96",
         "stats_filter": frappe.as_json({"status": "Approved"})},
    ]

    quick_lists = [
        # ToDo restricts itself to the logged-in person at the database level,
        # so this list is genuinely personal on a page everybody shares.
        {"label": "Atribuídas a mim", "document_type": "ToDo",
         "quick_list_filter": frappe.as_json({"status": "Open"})},
        # Task rows are scoped to the viewer's áreas by permissions.task_query,
        # so "das minhas áreas" is enforced, not just a label.
        {"label": "Nas minhas áreas", "document_type": "Task",
         "quick_list_filter": frappe.as_json({"status": ["in", OPEN_STATUSES]})},
    ]

    content = [
        _header("md1", "O que depende de mim"),
        _card("md1", "Comigo agora"),
        _card("md2", "Vence em 7 dias"),
        _card("md3", "Atrasadas"),
        _list("md1", "Atribuídas a mim"),
        _list("md2", "Nas minhas áreas"),
        _header("md2", "Minhas áreas"),
        _card("md4", "Abertas nas minhas áreas"),
        _card("md5", "Sem responsável"),
        _short("md1", "Abrir o quadro", col=4),
        _header("md3", "Atalhos"),
        _short("md2", "Nova tarefa"),
        _short("md3", "Abrir o chat"),
        _short("md4", "Minhas áreas e cargos"),
    ]

    # Deliberately unrestricted: this page is for everyone who can log in, and a
    # role gate here only risks locking members out of their own landing page.
    return _workspace("Meu DAGV", "Meu DAGV", "getting-started", 0.4, [], content,
                      shortcuts=shortcuts, quick_lists=quick_lists,
                      cards=["Comigo agora", "Vence em 7 dias", "Atrasadas",
                             "Abertas nas minhas áreas", "Sem responsável"])


# ---------------------------------------------------------------------------
# Aprovações — the leadership queue
# ---------------------------------------------------------------------------

def build_aprovacoes():
    """Answers "tem alguém esperando decisão minha?" — with the people on the
    page, not behind a link.

    The queues are the point, so they are quick lists: you read the actual names
    waiting, and clicking one opens the record where you decide. The rows are
    already restricted to the áreas you lead, so a coordinator of Eventos never
    sees Financeiro's queue.
    """
    quick_lists = [
        {"label": "Cadastros novos", "document_type": "DAGV Registration Request",
         "quick_list_filter": frappe.as_json({"status": "Pending"})},
        {"label": "Pedidos de entrada", "document_type": "DAGV Membership",
         "quick_list_filter": frappe.as_json({"status": "Requested"})},
        {"label": "Pedidos de saída", "document_type": "DAGV Membership",
         "quick_list_filter": frappe.as_json({"status": "Leave Requested"})},
        {"label": "Time da minha área", "document_type": "DAGV Membership",
         "quick_list_filter": frappe.as_json({"status": "Approved"})},
    ]

    shortcuts = [
        {"label": "Ver todos os cadastros", "type": "DocType",
         "link_to": "DAGV Registration Request", "doc_view": "List", "color": "#C2740E"},
        {"label": "Quadro da área", "type": "DocType", "link_to": "Task",
         "doc_view": "Kanban", "kanban_board": BOARD, "color": "#4C6EF5"},
    ]

    content = [
        _header("ap1", "Precisa de decisão"),
        _card("ap1", "Cadastros pendentes"),
        _card("ap2", "Pedidos de entrada"),
        _card("ap3", "Pedidos de saída"),
        _list("ap1", "Cadastros novos"),
        _list("ap2", "Pedidos de entrada"),
        _header("ap2", "Minha área"),
        _list("ap3", "Time da minha área"),
        _list("ap4", "Pedidos de saída"),
        _header("ap3", "Atalhos"),
        _short("ap1", "Quadro da área", col=4),
        _short("ap2", "Ver todos os cadastros", col=4),
    ]

    return _workspace("Aprovações", "Aprovações", "check", 0.6,
                      [LEAD_ROLE, BOARD_ROLE, MANAGER_ROLE], content,
                      shortcuts=shortcuts, quick_lists=quick_lists,
                      cards=["Cadastros pendentes", "Pedidos de entrada",
                             "Pedidos de saída"])


# ---------------------------------------------------------------------------
# Gestão — the executive read
# ---------------------------------------------------------------------------

def build_gestao():
    """Answers "como está o DAGV?" — staffing and workload side by side.

    The whole page is restricted, which is what makes it the right home for
    org-wide numbers: a section cannot carry its own roles, so anything not
    everyone should see has to live on a page not everyone can open.
    """
    shortcuts = [
        {"label": "Áreas", "type": "DocType", "link_to": "DAGV Area",
         "color": "#B69B1A", "doc_view": "List"},
        {"label": "Membros", "type": "DocType", "link_to": "DAGV Membership",
         "color": "#2F7D4F", "doc_view": "List",
         "stats_filter": frappe.as_json({"status": "Approved"})},
        {"label": "Usuários", "type": "DocType", "link_to": "User",
         "color": "#868E96", "doc_view": "List"},
    ]

    content = [
        _header("g1", "Pessoas"),
        _card("g1", "Membros ativos"),
        _card("g2", "Aguardando decisão"),
        _card("g3", "Áreas ativas"),
        _chart("g1", "Membros por área"),
        _header("g2", "Trabalho"),
        _chart("g2", "Trabalho por área", col=6),
        _chart("g3", "Trabalho por situação", col=6),
        _header("g3", "Estrutura"),
        _short("g1", "Áreas", col=4),
        _short("g2", "Membros", col=4),
        _short("g3", "Usuários", col=4),
    ]

    return _workspace(
        "Gestão", "Gestão", "setting", 0.7,
        [BOARD_ROLE, MANAGER_ROLE], content,
        shortcuts=shortcuts,
        cards=["Membros ativos", "Aguardando decisão", "Áreas ativas"],
        charts=["Membros por área", "Trabalho por área", "Trabalho por situação"],
    )


# ---------------------------------------------------------------------------
# Decision cards
# ---------------------------------------------------------------------------

def ensure_decision_cards():
    """One card per queue. "Aguardando decisão" used to merge entradas and
    saídas, which meant the number could never tell you what to do about it."""
    specs = [
        ("Cadastros pendentes", "DAGV Registration Request", {"status": "Pending"}, "#C2740E"),
        ("Pedidos de entrada", "DAGV Membership", {"status": "Requested"}, "#2F7D4F"),
        ("Pedidos de saída", "DAGV Membership", {"status": "Leave Requested"}, "#C0392B"),
    ]
    made = []
    for label, doctype, filters, color in specs:
        doc = (
            frappe.get_doc("Number Card", label)
            if frappe.db.exists("Number Card", label)
            else frappe.new_doc("Number Card")
        )
        doc.label = label
        doc.type = "Document Type"
        doc.document_type = doctype
        doc.function = "Count"
        doc.filters_json = frappe.as_json(filters)
        doc.is_public = 1
        doc.show_percentage_stats = 0
        doc.color = color
        doc.module = "DAGV"
        # See dagv.work.ensure_cards: an unset currency is not "no currency",
        # it is the company's, and the widget renders every count as money.
        doc.currency = None
        doc.show_full_number = 1
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(doc.name)
    frappe.db.commit()
    return {"cards": made}


# ---------------------------------------------------------------------------
# Roles, landing, permissions
# ---------------------------------------------------------------------------

def sync_rank_roles(email):
    """Give someone the page-level role their rank earns, and take it back when
    they step down. Ranks live in memberships, so this stays data-driven."""
    leads = frappe.get_all(
        "DAGV Membership",
        filters={"member": email, "status": "Approved", "rank": ["in", LEAD_RANKS]},
        limit=1,
    )
    has = LEAD_ROLE in frappe.get_roles(email)
    if leads and not has:
        frappe.get_doc("User", email).add_roles(LEAD_ROLE)
        frappe.clear_cache(user=email)
    elif not leads and has:
        frappe.get_doc("User", email).remove_roles(LEAD_ROLE)
        frappe.clear_cache(user=email)


def set_landing(email):
    """Everybody lands on Meu DAGV.

    Leads and the executive have their own pages, but their day starts with
    their own work like everyone else's — sending them straight to a queue of
    other people's requests puts the DAGV's admin ahead of its actual work.
    Their pages are one click away in the sidebar.
    """
    if frappe.db.exists("Workspace", "Meu DAGV"):
        frappe.db.set_value("User", email, "default_workspace", "Meu DAGV",
                            update_modified=False)
    return "Meu DAGV"


def ensure_permissions():
    """Exactly the access each role needs, and not one grant more.

    Read this as the security model, because it is: `DAGV Member` previously
    held unscoped **write** on DAGV Membership, which let any of ~80 members
    edit anybody's rank and status. Members now read (their own rows, per
    permissions.membership_query) and create (forced into a pending request for
    themselves, per permissions.guard_membership). Deciding is a lead's job.

    Work is the opposite shape: members genuinely collaborate on tasks, so they
    read and write Task — but only inside the áreas they belong to, which
    permissions.task_query enforces on every list, report and board.
    """
    from frappe.permissions import add_permission, update_permission_property

    def grant(doctype, role, **props):
        if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role}) \
                and not frappe.db.exists("DocPerm", {"parent": doctype, "role": role}):
            add_permission(doctype, role, 0)
        for prop, value in props.items():
            update_permission_property(doctype, role, 0, prop, value)

    # --- the desk itself -----------------------------------------------------
    grant("Workspace", MEMBER_ROLE, read=1)
    grant("Kanban Board", MEMBER_ROLE, read=1, write=1, create=1)
    grant("DAGV Area", MEMBER_ROLE, read=1)

    # --- membership: read your own, ask to join, never decide ----------------
    grant("DAGV Membership", MEMBER_ROLE,
          read=1, create=1, write=0, delete=0, report=1, export=0, share=0)
    # Leads decide, inside their own área (enforced row-by-row).
    grant("DAGV Membership", LEAD_ROLE,
          read=1, create=1, write=1, delete=0, report=1, export=1)
    grant("DAGV Registration Request", LEAD_ROLE,
          read=1, write=1, create=0, delete=0, report=1, export=1)

    # --- work: collaborate freely, inside your áreas -------------------------
    for role in (MEMBER_ROLE, LEAD_ROLE):
        grant("Task", role, read=1, write=1, create=1, delete=0, report=1, export=0)
        grant("Project", role, read=1, report=1)
    grant("Task", LEAD_ROLE, delete=1)

    frappe.clear_cache()
    frappe.db.commit()
    return {"ok": True}


def declutter_sidebar():
    """Keep the Projects module usable without putting it in everyone's face.

    Task lives in the Projects module, so blocking that module for members
    would break the very pages we just built. Instead the module stays open and
    the *workspace* is role-gated: people whose área actually uses Projects (and
    so hold Projects User) see it; everybody else gets a clean sidebar.
    """
    gated = []
    for workspace, role in (("Projects", "Projects User"),):
        if not frappe.db.exists("Workspace", workspace) or not frappe.db.exists("Role", role):
            continue
        doc = frappe.get_doc("Workspace", workspace)
        if not any(r.role == role for r in doc.roles):
            doc.append("roles", {"role": role})
            doc.flags.ignore_permissions = True
            doc.save()
            gated.append(workspace)
    frappe.db.commit()
    return {"gated": gated}


def build_index():
    """Build the whole index in one go."""
    from dagv.forms import sync as sync_forms
    from dagv.work import sync as sync_work

    ensure_roles()
    ensure_permissions()
    sync_work()
    sync_forms()
    ensure_decision_cards()
    made = {
        "meu_dagv": build_meu_dagv(),
        "aprovacoes": build_aprovacoes(),
        "gestao": build_gestao(),
        "sidebar": declutter_sidebar(),
    }
    frappe.clear_cache()
    return made
