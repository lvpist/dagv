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

# Nada de mapa escrito à mão aqui. O que entra numa pasta são **as páginas dos
# módulos que a própria área destrava** (`DAGV Area.erp_modules`), descobertas
# no momento: `Workspace.module` já diz a que módulo cada página pertence.
# A versão anterior tinha um mapa "módulo -> estes doctypes" inventado por mim,
# e era isso que fazia o conteúdo parecer aleatório.

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
        for ws in frappe.get_all(
            "Workspace",
            filters={"module": module, "public": 1},
            fields=["name", "title"],
            order_by="sequence_id asc",
        ):
            doc.append("shortcuts", {
                "label": ws.title or ws.name, "type": "URL",
                "url": f"/desk/{_route(ws.name)}", "color": "#868E96",
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


def _route(text):
    """Rota do desk: minúsculas, espaços viram hífen. 'Área Financeiro' -> area-financeiro."""
    import re
    import unicodedata

    slug = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")


def _icon(label, **values):
    doc = (
        frappe.get_doc("Desktop Icon", label)
        if frappe.db.exists("Desktop Icon", label)
        else frappe.new_doc("Desktop Icon")
    )
    doc.label = label
    for key, value in values.items():
        setattr(doc, key, value)
    doc.standard = 0
    doc.hidden = 0
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True) if not doc.is_new() else doc.insert(ignore_permissions=True)
    return doc


def ensure_area_icon(area):
    """Uma pasta de verdade no ecrã inicial, com os ícones da área lá dentro.

    O Frappe tem mesmo pastas: `Desktop Icon` com `icon_type = "Folder"`, e os
    filhos apontam para ela por `parent_icon`. Foi por aqui que se devia ter
    começado — a primeira tentativa pendurou o ícone numa `Workspace Sidebar`,
    que dá um atalho solto e não uma pasta.

    O gate é a tabela `roles` do próprio ícone: a pasta de Financeiro só existe
    para quem tem o papel de Financeiro. Os filhos herdam — o Frappe descarta
    qualquer filho cujo pai não passou (`parent_icon in permitted_parent_labels`).

    E como cada filho é o seu próprio registo, **o mesmo destino pode estar em
    várias pastas**: "Itens" aparece em Produtos e em Financeiro sem conflito,
    que era exatamente o ponto.
    """
    role = _area_role(area)
    if not frappe.db.exists("Role", role):
        return None

    pasta = _icon(
        area,
        icon_type="Folder",
        parent_icon=None,
        sidebar=None,
        link_type=None,
        link=None,
        icon="folder-normal",
    )
    pasta.set("roles", [])
    pasta.append("roles", {"role": role})
    pasta.flags.ignore_permissions = True
    pasta.save(ignore_permissions=True)

    # Filhos: `App` porque o Frappe só faz a verificação de sidebar no tipo
    # `Link`, e aqui quem manda na visibilidade é o pai.
    filhos = [(f"{area} · Painel", f"/desk/{_route('Área ' + area)}")]
    for module in _area_modules(area):
        for ws in frappe.get_all(
            "Workspace",
            filters={"module": module, "public": 1},
            fields=["name", "title"],
            order_by="sequence_id asc",
        ):
            filhos.append((f"{area} · {ws.title or ws.name}", f"/desk/{_route(ws.name)}"))

    for i, (label, url) in enumerate(filhos):
        _icon(label, icon_type="App", app="erpnext", parent_icon=area,
              link_type="External", link=url, idx=i, sidebar=None)

    # Tirar um módulo da área tem de tirar o ícone: sem isto o ecrã guardava
    # atalhos para ferramentas que a área já não usa.
    validos = {label for label, _ in filhos}
    for antigo in frappe.get_all(
        "Desktop Icon", filters={"parent_icon": area}, pluck="name"
    ):
        if antigo not in validos:
            frappe.delete_doc("Desktop Icon", antigo, force=1, ignore_permissions=True)

    return area


def hide_other_icons():
    """No ecrã ficam DAGV, Raven e as pastas das áreas. Mais nada.

    As pastas das áreas escondem-se sozinhas pelo papel, mas os ícones que vêm
    de origem — ERPNext, Accounting — não têm papel nenhum e apareciam a toda a
    gente. `hidden` é o interruptor do próprio Frappe: some do ecrã e volta
    desmarcando a caixa, sem apagar nada.
    """
    areas = set(frappe.get_all("DAGV Area", pluck="name"))
    manter = {"DAGV", "Raven"} | areas

    escondidos = []
    for icon in frappe.get_all("Desktop Icon", fields=["name", "label", "parent_icon", "hidden"]):
        if icon.label in manter or icon.parent_icon in areas:
            continue
        if icon.hidden:
            continue
        # `hidden` não chega para os ícones `standard` que o ERPNext traz: a
        # consulta do boot inclui `standard == 1` sempre e nunca filtra por
        # `hidden`, então "Accounting" e "ERPNext" continuavam no ecrã mesmo
        # marcados. Para esses, o registo sai — e volta a sair no próximo sync
        # se o migrate os recriar.
        if frappe.db.get_value("Desktop Icon", icon.name, "standard"):
            frappe.delete_doc("Desktop Icon", icon.name, force=1, ignore_permissions=True)
        else:
            frappe.db.set_value("Desktop Icon", icon.name, "hidden", 1, update_modified=False)
        escondidos.append(icon.label)

    frappe.cache.delete_key("desktop_icons")
    # Sem commit aqui: isto também corre dentro de eventos de documento, e o
    # Frappe ignora (com aviso) commits nesse contexto. Quem chama é que fecha.
    return escondidos


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
    return limpos


def on_area_change(doc, method=None):
    """Mexer numa área reflecte-se no ecrã na hora, não só no próximo migrate."""
    if doc.is_active:
        ensure_area_folder(doc.name)
        ensure_area_icon(doc.name)
    else:
        on_area_removed(doc)
    hide_other_icons()
    frappe.cache.delete_key("desktop_icons")
    frappe.clear_cache()


def on_area_removed(doc, method=None):
    """Apagar ou desactivar uma área leva a pasta, os ícones e a página dela."""
    area = doc.name if hasattr(doc, "name") else doc
    for child in frappe.get_all("Desktop Icon", filters={"parent_icon": area}, pluck="name"):
        frappe.delete_doc("Desktop Icon", child, force=1, ignore_permissions=True)
    for name, doctype in ((area, "Desktop Icon"), (area, "Workspace Sidebar"),
                          (f"Área {area}", "Workspace")):
        if frappe.db.exists(doctype, name):
            frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
    frappe.cache.delete_key("desktop_icons")
    frappe.clear_cache()


def sync():
    made = []
    for area in frappe.get_all("DAGV Area", filters={"is_active": 1}, pluck="name"):
        f = ensure_area_folder(area)
        if f:
            ensure_area_icon(area)
            made.append(f)
    hidden = suppress_other_sidebars()
    icones = hide_other_icons()
    limpos = reconcile_area_roles()
    frappe.db.commit()
    frappe.clear_cache()
    return {"pastas": made, "suprimidas": len(hidden), "icones_escondidos": len(icones), "papeis_limpos": limpos}
