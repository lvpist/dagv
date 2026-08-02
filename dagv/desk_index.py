"""The desk index — every page, who sees it, and where people land.

One place that builds the whole information architecture, so it is reproducible
and survives migrations. See DAGV_arquitetura.md for the reasoning.

Three apps in the strip (DAGV / ERPNext / Raven) and four pages inside DAGV,
each aimed at exactly one audience:

    Meu DAGV    todo membro      "de que eu faço parte?"
    Aprovações  liderança        "o que espera decisão minha?"
    Gestão      executivo        "como está a estrutura?" (+ seção Diretoria)

Access has three layers: the page (Workspace.roles) hides itself entirely, the
module list declutters the sidebar, and DocType permissions guard the records.
Number Cards have no role field, so anything sensitive belongs on a page that is
already restricted — never on Meu DAGV.
"""

import frappe

MEMBER_ROLE = "DAGV Member"
LEAD_ROLE = "DAGV Liderança"
BOARD_ROLE = "DAGV Diretoria"
MANAGER_ROLE = "DAGV User Manager"

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
               cards=None, charts=None, links=None):
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

    # Cards and charts must be declared here as well as referenced in content,
    # or the page renders the headers and nothing else.
    doc.set("number_cards", [])
    for c in cards or []:
        doc.append("number_cards", {"number_card_name": c, "label": c})

    doc.set("charts", [])
    for c in charts or []:
        doc.append("charts", {"chart_name": c, "label": c})

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


def build_meu_dagv():
    """Landing for every member: what am I part of, and what can I do next."""
    shortcuts = [
        {"label": "Minhas áreas", "type": "DocType", "link_to": "DAGV Membership",
         "color": "#B69B1A", "doc_view": "List",
         "stats_filter": frappe.as_json({"status": "Approved"})},
        {"label": "Entrar em uma área", "type": "DocType", "link_to": "DAGV Membership",
         "color": "#2F7D4F", "doc_view": "New"},
        {"label": "Abrir o chat", "type": "URL", "url": "/raven", "color": "#4C6EF5"},
        {"label": "Áreas do DAGV", "type": "DocType", "link_to": "DAGV Area",
         "color": "#868E96", "doc_view": "List"},
    ]
    content = [
        _header("md1", "Meu DAGV"),
        {"id": "mds1", "type": "shortcut", "data": {"shortcut_name": "Minhas áreas", "col": 3}},
        {"id": "mds2", "type": "shortcut", "data": {"shortcut_name": "Entrar em uma área", "col": 3}},
        {"id": "mds3", "type": "shortcut", "data": {"shortcut_name": "Abrir o chat", "col": 3}},
        {"id": "mds4", "type": "shortcut", "data": {"shortcut_name": "Áreas do DAGV", "col": 3}},
    ]
    # Deliberately unrestricted: this page is for everyone who can log in, and a
    # role gate here only risks locking members out of their own landing page.
    # The DAGV module is always visible, so only members reach it anyway.
    return _workspace("Meu DAGV", "Meu DAGV", "users", 0.4,
                      [], content, shortcuts=shortcuts)


def build_gestao():
    """Executive page: the structure, plus the Diretoria overview inside it.

    The whole page is restricted, which is what makes the Diretoria section
    private — a section cannot carry its own roles.
    """
    shortcuts = [
        {"label": "Áreas", "type": "DocType", "link_to": "DAGV Area",
         "color": "#B69B1A", "doc_view": "List"},
        {"label": "Membros", "type": "DocType", "link_to": "DAGV Membership",
         "color": "#2F7D4F", "doc_view": "List",
         "stats_filter": frappe.as_json({"status": "Approved"})},
        {"label": "Cadastros", "type": "DocType", "link_to": "DAGV Registration Request",
         "color": "#C2740E", "doc_view": "List",
         "stats_filter": frappe.as_json({"status": "Pending"})},
        {"label": "Usuários", "type": "DocType", "link_to": "User",
         "color": "#868E96", "doc_view": "List"},
    ]
    content = [
        _header("g1", "Estrutura"),
        {"id": "gs1", "type": "shortcut", "data": {"shortcut_name": "Áreas", "col": 3}},
        {"id": "gs2", "type": "shortcut", "data": {"shortcut_name": "Membros", "col": 3}},
        {"id": "gs3", "type": "shortcut", "data": {"shortcut_name": "Cadastros", "col": 3}},
        {"id": "gs4", "type": "shortcut", "data": {"shortcut_name": "Usuários", "col": 3}},
        # ---- Diretoria: the executive read on how the DAGV is doing ----
        _header("g2", "Diretoria"),
        {"id": "gn1", "type": "number_card",
         "data": {"number_card_name": "Membros ativos", "col": 4}},
        {"id": "gn2", "type": "number_card",
         "data": {"number_card_name": "Aguardando decisão", "col": 4}},
        {"id": "gn3", "type": "number_card",
         "data": {"number_card_name": "Áreas ativas", "col": 4}},
        {"id": "gc1", "type": "chart",
         "data": {"chart_name": "Membros por área", "col": 12}},
    ]
    return _workspace(
        "Gestão", "Gestão", "setting", 0.7,
        [BOARD_ROLE, MANAGER_ROLE], content,
        shortcuts=shortcuts,
        cards=["Membros ativos", "Aguardando decisão", "Áreas ativas"],
        charts=["Membros por área"],
    )


def restrict_aprovacoes():
    """Approvals belong to whoever leads an area, plus the user managers."""
    if not frappe.db.exists("Workspace", "Aprovações"):
        return None
    doc = frappe.get_doc("Workspace", "Aprovações")
    doc.set("roles", [])
    for role in (LEAD_ROLE, BOARD_ROLE, MANAGER_ROLE):
        doc.append("roles", {"role": role})
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return doc.name


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
    """Put people on the page that matches what they do, so nobody has to
    navigate to find their own work."""
    roles = set(frappe.get_roles(email))
    if roles.intersection({BOARD_ROLE, MANAGER_ROLE, "System Manager"}):
        target = "Gestão"
    elif LEAD_ROLE in roles:
        target = "Aprovações"
    else:
        target = "Meu DAGV"

    if frappe.db.exists("Workspace", target):
        frappe.db.set_value("User", email, "default_workspace", target, update_modified=False)
    return target


def build_index():
    """Build the whole index in one go."""
    ensure_roles()
    ensure_permissions()
    made = {
        "meu_dagv": build_meu_dagv(),
        "gestao": build_gestao(),
        "aprovacoes": restrict_aprovacoes(),
    }
    frappe.clear_cache()
    return made


def ensure_permissions():
    """Give the member role the reads it needs to see its own pages.

    A role with desk access but no DocType permissions can log in and then see
    nothing: the desk cannot even read the Workspace record, so every page
    disappears with no visible error. Granted explicitly here rather than left
    to inherited defaults.
    """
    from frappe.permissions import add_permission, update_permission_property

    grants = [
        # (doctype, role, {property: value})
        ("Workspace", MEMBER_ROLE, {"read": 1}),
        ("DAGV Area", MEMBER_ROLE, {"read": 1}),
        # Members read their memberships and create one to ask to join an area.
        ("DAGV Membership", MEMBER_ROLE, {"read": 1, "create": 1, "write": 1}),
    ]

    for doctype, role, props in grants:
        if not frappe.db.exists("DocPerm", {"parent": doctype, "role": role}):
            add_permission(doctype, role, 0)
        for prop, value in props.items():
            update_permission_property(doctype, role, 0, prop, value)

    frappe.clear_cache()
    frappe.db.commit()
    return {"granted": [f"{d}:{r}" for d, r, _ in grants]}
