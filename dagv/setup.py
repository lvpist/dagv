"""Seed data for DAGV.

The 15 areas as of the Nexo term (2026.2–2027.1). This is a *starting point*,
not a fixed list: areas are ordinary records, so future leaderships add, rename,
merge or archive them from the panel without touching code.
"""

import frappe

# (area_name, short_code, category, required_course, description)
AREAS = [
    # Diretorias Mínimas
    ("VPAE", "VPAE", "Mínima", "Administração de Empresas",
     "Vice-Presidência Acadêmica de Administração de Empresas — representação e demandas do curso."),
    ("VPAP", "VPAP", "Mínima", "Administração Pública",
     "Vice-Presidência Acadêmica de Administração Pública — representação e demandas do curso."),
    ("VPEcono", "VPEcono", "Mínima", "Economia",
     "Vice-Presidência Acadêmica de Economia — representação e demandas do curso."),
    ("Cultural", "CULT", "Mínima", None,
     "Arte, pensamento crítico, extensão cultural e diálogo com coletivos."),
    ("Eventos", "EVEN", "Mínima", None,
     "Festas e entretenimento do calendário estudantil, da operação à porta e ao bar."),
    ("Financeiro", "FIN", "Mínima", None,
     "Prestação de contas, exigências da FGV e organização dos fluxos financeiros."),
    # Diretorias Suplementares
    ("Criativo", "CRIA", "Suplementar", None,
     "Imagem institucional, redes sociais, design e comunicação do DA."),
    ("Entidades", "LIDEN", "Suplementar", None,
     "Relação com as entidades estudantis (LIDEN), repasses e integração."),
    ("Institucional", "INST", "Suplementar", None,
     "Coletivos, rastreabilidade de demandas, permanência e inclusão."),
    ("Integração", "INTE", "Suplementar", None,
     "Acolhimento, trote, Dia do Bixo, GVDAY e senso de pertencimento."),
    ("Parcerias", "PARC", "Suplementar", None,
     "Parcerias com empresas e entidades, benefícios e descontos ao alunato."),
    ("Pessoas", "PESS", "Suplementar", None,
     "Recrutamento, desenvolvimento e reconhecimento de membros; cultura interna."),
    ("Planejamento", "PLAN", "Suplementar", None,
     "Planejamento estratégico, metas da Carta Proposta e suporte às demais áreas."),
    ("Produtos", "PROD", "Suplementar", None,
     "Grife, kit bixo, estoque, fornecedores e e-commerce."),
    ("Projetos", "PROJ", "Suplementar", None,
     "Projetos de suporte acadêmico e participação nos três cursos."),
]


def seed_areas():
    """Create any missing area. Never overwrites an existing record."""
    created, skipped = [], []
    for order, (name, code, category, course, description) in enumerate(AREAS, start=1):
        if frappe.db.exists("DAGV Area", name):
            skipped.append(name)
            continue
        doc = frappe.get_doc(
            {
                "doctype": "DAGV Area",
                "area_name": name,
                "short_code": code,
                "category": category,
                "required_course": course,
                "description": description,
                "sort_order": order,
                "is_active": 1,
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        created.append(name)

    frappe.db.commit()
    return {"created": created, "skipped": skipped}


# Which slice of ERPNext each area starts with. Deliberately lean: an area sees
# only what its work needs, and an admin can change any of it in the panel.
# Empty list = the area has no ERP tools yet (chat only).
DEFAULT_MODULES = {
    "Produtos": ["Stock", "Selling", "Buying"],   # estoque, grife, e-commerce
    "Financeiro": ["Accounts"],                   # prestação de contas, notas
    "Parcerias": ["CRM", "Selling"],              # empresas parceiras e benefícios
    "Eventos": ["Projects"],
    "Projetos": ["Projects"],
    "Planejamento": ["Projects"],
    "Integração": ["Projects"],
    "Cultural": ["Projects"],
    "Criativo": ["Projects"],
    "Entidades": ["Projects"],
    "Pessoas": ["Projects"],
    "Institucional": ["Support", "Projects"],     # demandas e ouvidoria
    "VPAE": ["Support"],
    "VPAP": ["Support"],
    "VPEcono": ["Support"],
}


def seed_area_modules(overwrite=False):
    """Give each area its starting ERP modules.

    Skips areas that already have modules set, so a leadership's own choices are
    never overwritten by a later run.
    """
    touched = []
    for area, modules in DEFAULT_MODULES.items():
        if not frappe.db.exists("DAGV Area", area):
            continue
        doc = frappe.get_doc("DAGV Area", area)
        if doc.erp_modules and not overwrite:
            continue
        doc.set("erp_modules", [])
        for module in modules:
            if frappe.db.exists("Module Def", module):
                doc.append("erp_modules", {"module": module})
        doc.flags.ignore_permissions = True
        doc.save()
        touched.append(area)

    frappe.db.commit()
    return {"updated": touched}


# ---------------------------------------------------------------------------
# Desk navigation
# ---------------------------------------------------------------------------
# Custom pages are only reachable if the desk knows about them. ERPNext's native
# mechanism is a Workspace record with URL shortcuts — that's how Raven shows up
# in the sidebar, so DAGV uses exactly the same pattern instead of asking people
# to type URLs.

DAGV_WORKSPACE = "DAGV"

DAGV_SHORTCUTS = [
    ("Meu painel", "/painel", "Blue"),
    ("Aprovações", "/aprovacoes", "Orange"),
    ("Gestão", "/gestao", "Grey"),
    ("Raven (chat)", "/raven", "Green"),
]


def setup_desk_navigation():
    """Put DAGV in the desk sidebar with links to its pages."""
    if not frappe.db.exists("Module Def", DAGV_WORKSPACE):
        frappe.get_doc(
            {
                "doctype": "Module Def",
                "module_name": DAGV_WORKSPACE,
                "app_name": "dagv",
                "custom": 0,
            }
        ).insert(ignore_permissions=True)

    doc = (
        frappe.get_doc("Workspace", DAGV_WORKSPACE)
        if frappe.db.exists("Workspace", DAGV_WORKSPACE)
        else frappe.new_doc("Workspace")
    )
    doc.name = DAGV_WORKSPACE
    doc.title = DAGV_WORKSPACE
    doc.label = DAGV_WORKSPACE
    doc.module = DAGV_WORKSPACE
    doc.public = 1
    doc.is_hidden = 0
    doc.icon = "users"
    doc.sequence_id = 0.5  # sits right at the top, before ERPNext's own

    doc.set("shortcuts", [])
    for label, url, color in DAGV_SHORTCUTS:
        doc.append("shortcuts", {"label": label, "type": "URL", "url": url, "color": color})

    content = [
        {
            "id": "dagvhdr001",
            "type": "header",
            "data": {"text": '<span class="h4"><b>DAGV</b></span>', "col": 12},
        }
    ]
    for i, (label, _url, _color) in enumerate(DAGV_SHORTCUTS):
        content.append(
            {"id": f"dagvsc{i:04d}", "type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
        )
    doc.content = frappe.as_json(content)

    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return {
        "workspace": doc.name,
        "shortcuts": [s.label for s in doc.shortcuts],
    }


HOME_PINS = [
    ("DAGV", "/desk/dagv", "Blue"),
    ("Raven", "/raven", "Green"),
]


def pin_to_home():
    """Put DAGV and Raven on ERPNext's Home page.

    Home is a standard workspace, so ERPNext rewrites it on every migrate and
    any manual edit disappears. Re-applied from the ``after_migrate`` hook so the
    icons survive deploys instead of quietly vanishing.
    """
    if not frappe.db.exists("Workspace", "Home"):
        return {"skipped": "no Home workspace"}

    doc = frappe.get_doc("Workspace", "Home")

    existing = {s.label for s in doc.shortcuts}
    for label, url, color in HOME_PINS:
        if label not in existing:
            doc.append("shortcuts", {"label": label, "type": "URL", "url": url, "color": color})

    content = frappe.parse_json(doc.content or "[]")
    have = {b.get("data", {}).get("shortcut_name") for b in content if b.get("type") == "shortcut"}
    blocks = []
    for i, (label, _u, _c) in enumerate(HOME_PINS):
        if label not in have:
            blocks.append(
                {"id": f"dagvpin{i:03d}", "type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
            )
    if blocks:
        header = {
            "id": "dagvpinhdr",
            "type": "header",
            "data": {"text": '<span class="h4"><b>DAGV</b></span>', "col": 12},
        }
        content = [header] + blocks + content
        doc.content = frappe.as_json(content)

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"pinned": [p[0] for p in HOME_PINS]}


def after_migrate():
    """Re-apply everything ERPNext's own migrations would wipe."""
    setup_desk_navigation()
    setup_sidebar()
    setup_desktop_icon()
    setup_aprovacoes_workspace()
    setup_dashboard()
    pin_to_home()


def setup_sidebar():
    """Add DAGV to the desk sidebar.

    The desk's left sidebar is driven by `Workspace Sidebar` records, not by
    Workspace records — that's why Raven (which has one) appeared and DAGV
    didn't. Registered under the erpnext app so it shows in the sidebar people
    actually use, rather than behind an app switch.
    """
    name = "DAGV"
    doc = (
        frappe.get_doc("Workspace Sidebar", name)
        if frappe.db.exists("Workspace Sidebar", name)
        else frappe.new_doc("Workspace Sidebar")
    )
    doc.name = name
    doc.title = name
    doc.module = "DAGV"
    doc.app = "erpnext"
    doc.standard = 0

    doc.set("items", [])
    doc.append("items", {"type": "Link", "label": "Painel do membro",
                         "link_type": "URL", "url": "/painel"})
    doc.append("items", {"type": "Link", "label": "Aprovações",
                         "link_type": "URL", "url": "/aprovacoes"})
    doc.append("items", {"type": "Link", "label": "Gestão",
                         "link_type": "URL", "url": "/gestao"})
    doc.append("items", {"type": "Link", "label": "Áreas",
                         "link_type": "DocType", "link_to": "DAGV Area"})
    doc.append("items", {"type": "Link", "label": "Membros",
                         "link_type": "DocType", "link_to": "DAGV Membership"})
    doc.append("items", {"type": "Link", "label": "Cadastros",
                         "link_type": "DocType", "link_to": "DAGV Registration Request"})

    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return {"sidebar": doc.name, "items": [i.label for i in doc.items]}


def setup_desktop_icon():
    """Put DAGV in the desk's top navigation strip.

    That strip is built from `Desktop Icon` records (see frappe desktop.js,
    which looks each one up by label) — NOT from Workspace or Workspace Sidebar
    records. Raven ships one, which is the only reason it appeared there while
    DAGV stayed invisible no matter how many workspaces existed.
    """
    name = "DAGV"
    if frappe.db.exists("Desktop Icon", name):
        doc = frappe.get_doc("Desktop Icon", name)
    else:
        doc = frappe.new_doc("Desktop Icon")
        doc.label = name

    doc.icon_type = "App"
    doc.link_type = "External"   # same shape Raven uses
    doc.link = "/desk/dagv"
    doc.app = "dagv"
    doc.standard = 0
    doc.hidden = 0
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True) if not doc.is_new() else doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"desktop_icon": doc.name}


def setup_aprovacoes_workspace():
    """Native replacement for the custom /aprovacoes page.

    Hierarchy comes from the counts: the three things that need a decision sit
    first and carry a live number, so the page answers "is there anything for me
    to do?" before you read a word. Settled records are one row further down.
    """
    # Name has no accent so the route stays /desk/aprovacoes; the label carries
    # the proper spelling for display.
    name = "Aprovacoes"
    doc = (
        frappe.get_doc("Workspace", name)
        if frappe.db.exists("Workspace", name)
        else frappe.new_doc("Workspace")
    )
    doc.name = name
    doc.title = "Aprovações"
    doc.label = "Aprovações"
    doc.module = "DAGV"
    doc.app = "dagv"
    doc.public = 1
    doc.is_hidden = 0
    doc.icon = "check"
    doc.sequence_id = 0.6

    # (label, doctype, filters, colour)
    queues = [
        ("Cadastros novos", "DAGV Registration Request", {"status": "Pending"}, "Orange"),
        ("Pedidos de entrada", "DAGV Membership", {"status": "Requested"}, "Orange"),
        ("Pedidos de saída", "DAGV Membership", {"status": "Leave Requested"}, "Red"),
        ("Membros ativos", "DAGV Membership", {"status": "Approved"}, "Green"),
    ]

    doc.set("shortcuts", [])
    for label, dt, filters, color in queues:
        doc.append(
            "shortcuts",
            {
                "label": label,
                "type": "DocType",
                "link_to": dt,
                "color": color,
                "stats_filter": frappe.as_json(filters),
                "doc_view": "List",
            },
        )

    content = [
        {"id": "aprhdr0001", "type": "header",
         "data": {"text": '<span class="h4"><b>Precisa de decisão</b></span>', "col": 12}},
        {"id": "aprsc00001", "type": "shortcut", "data": {"shortcut_name": "Cadastros novos", "col": 4}},
        {"id": "aprsc00002", "type": "shortcut", "data": {"shortcut_name": "Pedidos de entrada", "col": 4}},
        {"id": "aprsc00003", "type": "shortcut", "data": {"shortcut_name": "Pedidos de saída", "col": 4}},
        {"id": "aprhdr0002", "type": "header",
         "data": {"text": '<span class="h4"><b>Quadro atual</b></span>', "col": 12}},
        {"id": "aprsc00004", "type": "shortcut", "data": {"shortcut_name": "Membros ativos", "col": 4}},
    ]
    doc.content = frappe.as_json(content)

    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    frappe.db.commit()
    return {"workspace": doc.name, "queues": [q[0] for q in queues]}


def setup_dashboard():
    """Native Dashboard View for the membership list.

    Two number cards answer "is there anything for me to do?", and the chart
    answers the question a diretoria actually asks — which areas are staffed and
    which are empty. Everything here is a normal ERPNext record, so a future
    admin can add or change widgets from Customize without any code.
    """
    made = []

    cards = [
        ("Membros ativos", {"status": "Approved"}, "Green"),
        ("Aguardando decisão", {"status": ["in", ["Requested", "Leave Requested"]]}, "Orange"),
    ]
    for label, filters, color in cards:
        if frappe.db.exists("Number Card", label):
            doc = frappe.get_doc("Number Card", label)
        else:
            doc = frappe.new_doc("Number Card")
            doc.label = label
        doc.type = "Document Type"
        doc.document_type = "DAGV Membership"
        doc.function = "Count"
        doc.filters_json = frappe.as_json(filters)
        doc.is_public = 1
        doc.show_percentage_stats = 0
        doc.color = color
        doc.module = "DAGV"
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(doc.name)

    chart = "Membros por área"
    if frappe.db.exists("Dashboard Chart", chart):
        doc = frappe.get_doc("Dashboard Chart", chart)
    else:
        doc = frappe.new_doc("Dashboard Chart")
        doc.chart_name = chart
    doc.chart_type = "Group By"
    doc.document_type = "DAGV Membership"
    doc.group_by_type = "Count"
    doc.group_by_based_on = "area"
    doc.number_of_groups = 0          # every area, not a top-N slice
    doc.filters_json = frappe.as_json({"status": "Approved"})
    doc.type = "Bar"                  # comparing sizes across areas, not a trend
    doc.is_public = 1
    doc.module = "DAGV"
    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    made.append(doc.name)

    frappe.db.commit()
    return {"created": made}
