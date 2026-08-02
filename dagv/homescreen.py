"""O ecrã inicial: DAGV, Raven e uma pasta por área. Mais nada.

O `/desk` do ERPNext vinha com 56 grupos — Contabilidade, Compras, Vendas,
Qualidade, Geo, Manutenção — e um membro sem área nenhuma via 32 deles. Isto
reduz o ecrã ao que o DAGV usa: o app do DAGV, o chat, e as pastas **das áreas
em que a pessoa está**.

## Como uma pasta sabe a quem pertence

Não sabe, e é isso que a torna simples. O Frappe desenha uma pasta **só se a
pessoa conseguir abrir pelo menos um item lá dentro** (`frappe/boot.py`, em
`get_sidebar_items`). Então basta que tudo dentro da pasta *Financeiro* exija o
papel que a área Financeiro concede: quem não é de Financeiro não consegue abrir
nada ali, e a pasta não chega a ser desenhada.

Daí a regra que rege este ficheiro:

> **nenhum item de uma pasta de área pode ser aberto por qualquer membro.**

Um atalho para Tarefa, por exemplo, está fora — todo membro lê Tarefa, e bastaria
isso para a pasta de Financeiro aparecer para o pessoal de Eventos. O trabalho da
área vive *dentro* da página da área, que é gated, e não solto na pasta.

## Porquê não uma pasta por pessoa

O campo `for_user` não esconde nada: uma pasta chamada `Financeiro-<email>` é só
*renomeada* para o dono, e toda a gente continua a vê-la com o e-mail lá no nome.
Testado. Uma pasta por área resolve o mesmo com 15 registos em vez de 240, e é
de facto privada.
"""

import frappe

# O que cada módulo põe na pasta da área. Deliberadamente curto: duas ou três
# entradas que alguém abre mesmo, não o menu inteiro do ERPNext.
# Cada uma exige o papel que o módulo concede — é isso que fecha a pasta.
MODULE_TOOLS = {
    "Stock": [("Itens", "Item"), ("Movimentos de estoque", "Stock Entry")],
    "Selling": [("Clientes", "Customer"), ("Vendas", "Sales Invoice")],
    "Buying": [("Fornecedores", "Supplier"), ("Compras", "Purchase Invoice")],
    "Accounts": [("Pagamentos", "Payment Entry"), ("Lançamentos", "Journal Entry")],
    "Support": [("Demandas", "Issue")],
    "CRM": [("Contactos", "Contact")],
    # Projects não entra: Tarefa é de todos os membros, e um atalho para ela numa
    # pasta de área faria essa pasta aparecer para toda a gente.
    "Projects": [],
}

# O que fica no ecrã, além das pastas das áreas.
KEEP_SIDEBARS = {"dagv", "raven", "my workspaces"}


def _area_role(area):
    return frappe.db.get_value("DAGV Area", area, "erp_role") or f"DAGV {area}"


def _area_modules(area):
    return frappe.get_all(
        "DAGV Area Module", filters={"parent": area}, pluck="module"
    )


# ---------------------------------------------------------------------------
# A página da área — é ela que fecha a pasta
# ---------------------------------------------------------------------------

def ensure_area_workspace(area):
    """Uma página por área, presa ao papel da área.

    Serve duas coisas ao mesmo tempo: é onde o trabalho da área aparece, e é o
    item gated que faz a pasta existir só para quem é da área.
    """
    role = _area_role(area)
    if not frappe.db.exists("Role", role):
        return None

    name = f"Área {area}"
    doc = (
        frappe.get_doc("Workspace", name)
        if frappe.db.exists("Workspace", name)
        else frappe.new_doc("Workspace")
    )
    doc.name = name
    doc.title = name
    doc.label = name
    doc.module = "DAGV"
    doc.app = "dagv"
    doc.public = 1
    doc.is_hidden = 0
    doc.icon = "folder-normal"
    doc.sequence_id = 5
    doc.for_user = ""
    doc.parent_page = ""

    doc.set("roles", [])
    doc.append("roles", {"role": role})

    label = f"Trabalho de {area}"
    doc.set("quick_lists", [])
    doc.append("quick_lists", {
        "label": label,
        "document_type": "Task",
        "quick_list_filter": frappe.as_json({
            "dagv_area": area,
            "status": ["in", ["Open", "Working", "Pending Review", "Overdue"]],
        }),
    })

    doc.set("shortcuts", [])
    doc.append("shortcuts", {
        "label": "Nova tarefa", "type": "DocType", "link_to": "Task",
        "doc_view": "New", "color": "#2F7D4F",
    })
    doc.append("shortcuts", {
        "label": f"Quadro de {area}", "type": "DocType", "link_to": "Task",
        "doc_view": "Kanban", "kanban_board": "Quadro DAGV", "color": "#4C6EF5",
    })
    # As ferramentas do módulo vivem aqui, e não na pasta. Na pasta elas
    # acendiam-na para fora da área: `Issue` abre-se com `Support Team`, que
    # VPAE também concede, então a pasta de Institucional aparecia a quem é de
    # VPAE. O papel da área é o único gate que não é partilhado.
    for module in _area_modules(area):
        for label, doctype in MODULE_TOOLS.get(module, []):
            if frappe.db.exists("DocType", doctype):
                doc.append("shortcuts", {
                    "label": label, "type": "DocType",
                    "link_to": doctype, "doc_view": "List", "color": "#868E96",
                })

    doc.set("number_cards", [])
    doc.set("charts", [])
    doc.content = frappe.as_json([
        {"id": f"a{abs(hash(area)) % 9999}h", "type": "header",
         "data": {"text": f'<span class="h4"><b>{area}</b></span>', "col": 12}},
        {"id": f"a{abs(hash(area)) % 9999}p", "type": "paragraph",
         "data": {"text": '<span class="text-muted">O trabalho aberto desta área. '
                          'O quadro mostra tudo o que você pode ver.</span>', "col": 12}},
        {"id": f"a{abs(hash(area)) % 9999}q", "type": "quick_list",
         "data": {"quick_list_name": label, "col": 6}},
        {"id": f"a{abs(hash(area)) % 9999}s", "type": "shortcut",
         "data": {"shortcut_name": "Nova tarefa", "col": 3}},
        {"id": f"a{abs(hash(area)) % 9999}k", "type": "shortcut",
         "data": {"shortcut_name": f"Quadro de {area}", "col": 3}},
    ])
    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    return name


# ---------------------------------------------------------------------------
# A pasta
# ---------------------------------------------------------------------------

def ensure_area_folder(area):
    workspace = ensure_area_workspace(area)
    if not workspace:
        return None

    doc = (
        frappe.get_doc("Workspace Sidebar", area)
        if frappe.db.exists("Workspace Sidebar", area)
        else frappe.new_doc("Workspace Sidebar")
    )
    doc.title = area
    doc.app = "erpnext"
    doc.module = "DAGV"
    doc.header_icon = "folder-normal"
    doc.standard = 0
    doc.for_user = None

    # UM item, e de propósito: a página da área, presa ao papel da área. É o
    # único gate que não é partilhado com outra área, e a pasta só aparece se
    # este item abrir. Qualquer atalho de ferramenta aqui fura isso — as
    # ferramentas estão dentro da página.
    doc.set("items", [])
    doc.append("items", {
        "type": "Link", "label": "Painel da área",
        "link_type": "Workspace", "link_to": workspace,
    })

    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()
    return doc.name


# ---------------------------------------------------------------------------
# Tirar todo o resto
# ---------------------------------------------------------------------------

def suppress_other_sidebars():
    """Só DAGV, Raven e as pastas das áreas ficam no ecrã.

    O Frappe **auto-gera** uma pasta por Module Def sempre que não existe um
    registo `Workspace Sidebar` com aquele nome — é daí que vinham Contabilidade,
    Compras, Vendas, Geo. Criando o registo, mandamos nele; e um registo cujo
    único item é um Section Break é **saltado por completo** na montagem do ecrã.
    Nada é apagado: é o mesmo mecanismo do próprio Frappe, e uma diretoria futura
    devolve qualquer uma editando o registo.

    "My Workspaces" não é suprimível — o Frappe isenta-a explicitamente.
    """
    areas = {a.lower() for a in frappe.get_all("DAGV Area", pluck="name")}
    keep = KEEP_SIDEBARS | areas

    suppressed = []
    for module in frappe.get_all("Module Def", pluck="name"):
        if module.lower() in keep:
            continue
        doc = (
            frappe.get_doc("Workspace Sidebar", module)
            if frappe.db.exists("Workspace Sidebar", module)
            else frappe.new_doc("Workspace Sidebar")
        )
        doc.title = module
        doc.module = module
        doc.standard = 0
        doc.set("items", [])
        doc.append("items", {"type": "Section Break", "label": ""})
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        suppressed.append(module)

    # As que já existiam como registo real e não são nossas.
    for existing in frappe.get_all("Workspace Sidebar", pluck="name"):
        if existing.lower() in keep or existing in suppressed:
            continue
        if "-" in existing and "@" in existing:   # cópias pessoais do Frappe
            continue
        doc = frappe.get_doc("Workspace Sidebar", existing)
        if any(i.type != "Section Break" for i in doc.items):
            doc.set("items", [])
            doc.append("items", {"type": "Section Break", "label": ""})
            doc.flags.ignore_permissions = True
            doc.save()
            suppressed.append(existing)

    return suppressed


def reconcile_area_roles():
    """Tira papéis de área a quem já não tem filiação aprovada nela.

    Apareceu ao testar as pastas: um membro sem área nenhuma continuava a ver a
    pasta de Cultural, porque ainda carregava o papel `DAGV Cultural` de uma
    filiação antiga. A pasta estava certa — o papel é que estava a mais, e papel
    a mais é acesso a mais. Sair de uma área revoga; apagar a filiação à mão,
    que foi o que aconteceu aqui, não passava por revogação nenhuma.
    """
    area_roles = {
        a.erp_role: a.name
        for a in frappe.get_all("DAGV Area", fields=["name", "erp_role"])
        if a.erp_role
    }
    limpos = []
    for user in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
        if user in ("Administrator", "Guest"):
            continue
        aprovadas = set(frappe.get_all(
            "DAGV Membership",
            filters={"member": user, "status": "Approved"}, pluck="area"))
        for role in frappe.get_roles(user):
            area = area_roles.get(role)
            if area and area not in aprovadas:
                frappe.get_doc("User", user).remove_roles(role)
                limpos.append(f"{user}: -{role}")
        frappe.clear_cache(user=user)
    frappe.db.commit()
    return limpos


def sync():
    made = []
    for area in frappe.get_all("DAGV Area", filters={"is_active": 1}, pluck="name"):
        f = ensure_area_folder(area)
        if f:
            made.append(f)
    hidden = suppress_other_sidebars()
    limpos = reconcile_area_roles()
    frappe.db.commit()
    frappe.clear_cache()
    return {"pastas": made, "suprimidas": len(hidden), "papeis_limpos": limpos}
