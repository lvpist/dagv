"""Enxugar as páginas do ERPNext que uma área abre.

Esconder páginas inteiras resolveu metade do problema: um membro já não vê
Manufatura nem Qualidade. Mas as que ficaram continuavam cruas — a página de
Estoque tem **72 links**, Vendas 57, Faturação 54. São páginas desenhadas para
uma empresa com departamento fiscal, não para um DA que vende moletom.

Aqui cada página fica com o punhado de coisas que a área usa mesmo. O critério
é sempre o mesmo: *alguém do DAGV abre isto para quê?* Se não há resposta, sai.

Não se apaga nada. Os links continuam no ERPNext e voltam editando o Workspace
pela interface; o que muda é o que está à frente da pessoa por omissão. E como
`bench migrate` reescreve as páginas padrão, isto corre outra vez no
`after_migrate` — senão a limpeza durava até ao próximo deploy.

As listas abaixo são a única parte com juízo meu. Ficam num sítio só, com o
porquê à frente, para uma diretoria futura discordar sem procurar.
"""

import frappe

# Página do ERPNext -> o que fica. Referenciado por `link_to`, que é estável
# (o rótulo muda com a tradução, o destino não).
KEEP = {
    # Financeiro: prestação de contas. Entra e sai dinheiro, e regista-se.
    "Invoicing": [
        "Sales Invoice",       # o que o DA recebeu
        "Purchase Invoice",    # o que o DA gastou
        "Payment Entry",       # o pagamento em si
        "Journal Entry",       # acerto manual, quando nada acima serve
    ],
    "Financial Reports": [
        "General Ledger",      # o extrato: tudo o que aconteceu
        "Trial Balance",       # fecho do período
    ],
    # Produtos: grife e kit bixo. Ter, mover, contar.
    "Stock": [
        "Item",                # o produto
        "Stock Entry",         # entrada e saída
        "Stock Reconciliation",  # contagem física
        "Warehouse",           # onde está guardado
    ],
    "Selling": [
        "Customer",            # quem compra
        "Sales Invoice",       # a venda
    ],
    "Buying": [
        "Supplier",            # o fornecedor
        "Purchase Invoice",    # a compra
    ],
    # Parcerias: empresas e contactos.
    "CRM": [
        "Lead",                # parceria em conversa
        "Contact",             # a pessoa do outro lado
    ],
    # VPs e Institucional: demandas de aluno.
    "Support": [
        "Issue",               # a demanda
    ],
}

TITULO = {
    "Invoicing": "Dinheiro",
    "Financial Reports": "Relatórios",
    "Stock": "Estoque",
    "Selling": "Vendas",
    "Buying": "Compras",
    "CRM": "Parcerias",
    "Support": "Demandas",
}


def _slug(text):
    import re

    return re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-")


def lean_workspace(name):
    """Uma página do ERPNext reduzida ao que a área usa."""
    if name not in KEEP or not frappe.db.exists("Workspace", name):
        return None

    doc = frappe.get_doc("Workspace", name)
    manter = KEEP[name]

    # Aproveitar o link existente quando há um (traz o tipo certo e a marca de
    # relatório), e criar quando não há. Só filtrar não chegava: a Faturação
    # ficava sem Nota de Venda e sem Nota de Compra, porque essas vivem nas
    # páginas de Vendas e Compras — e aí o Financeiro deixava de ver faturas.
    existentes = {}
    for link in doc.links:
        if link.type == "Link" and link.link_to and link.link_to not in existentes:
            existentes[link.link_to] = {
                "type": "Link",
                "label": link.label,
                "link_type": link.link_type,
                "link_to": link.link_to,
                "is_query_report": link.is_query_report,
                "report_ref_doctype": link.report_ref_doctype,
                "onboard": 0,
                "dependencies": link.dependencies,
            }

    # A ordem é a da lista acima, que é a ordem por que se usa — não a que o
    # ERPNext calhou de ter. E nunca repete: o Estoque trazia "Item" duas vezes.
    guardados = []
    for alvo in manter:
        if alvo in existentes:
            guardados.append(existentes[alvo])
        elif frappe.db.exists("DocType", alvo):
            guardados.append({
                "type": "Link", "label": alvo,
                "link_type": "DocType", "link_to": alvo,
                "is_query_report": 0, "onboard": 0,
            })

    if not guardados:
        return {"skipped": name, "motivo": "nenhum dos links esperados existe"}

    seccao = TITULO.get(name, name)
    doc.set("links", [])
    doc.append("links", {"type": "Card Break", "label": seccao,
                         "link_count": len(guardados)})
    for entrada in guardados:
        doc.append("links", entrada)

    # Fora os gráficos e números: são de contabilidade de empresa (valor de
    # stock, faturação a receber) e num DA aparecem sempre a zero, que é pior
    # do que não estar lá. Os números que importam estão na página da área.
    doc.set("charts", [])
    doc.set("number_cards", [])
    doc.set("shortcuts", [])

    # Só o cartão. O cabeçalho repetia o título do cartão, que por sua vez
    # repete o nome da página na migalha — a mesma palavra três vezes.
    tag = _slug(name)
    doc.content = frappe.as_json([
        {"id": f"{tag}-c", "type": "card",
         "data": {"card_name": seccao, "col": 4}},
    ])

    doc.flags.ignore_permissions = True
    doc.save()
    return {"pagina": name, "de": len(doc.links), "links": len(guardados)}


def sync():
    resultado = []
    antes = {}
    for name in KEEP:
        if frappe.db.exists("Workspace", name):
            antes[name] = frappe.db.count("Workspace Link", {"parent": name})
    for name in KEEP:
        r = lean_workspace(name)
        if r and "pagina" in r:
            r["antes"] = antes.get(name)
            resultado.append(r)
    frappe.db.commit()
    frappe.clear_cache()
    return resultado


# ---------------------------------------------------------------------------
# Os formulários
# ---------------------------------------------------------------------------
# Enxugar a página levou a pessoa até "Fatura de Venda" em dois cliques — e aí
# ela encontra o formulário de faturação de uma empresa: modelo de imposto,
# centro de custo, moeda, condições de pagamento, endereço de entrega. Um DA
# precisa de saber quem comprou, o quê, quanto e quando.
#
# A regra que torna isto seguro: **campo obrigatório nunca é escondido.** O
# Frappe valida obrigatórios mesmo invisíveis, então esconder um sem valor por
# omissão dá um formulário que não grava e não diz porquê. Aqui o obrigatório
# fica sempre, mesmo que não esteja na lista.
#
# Quebras de coluna também nunca: escondê-las não junta as colunas, órfã o que
# estava na segunda — já aconteceu na Tarefa, e o prazo desapareceu do ecrã.

FORMS = {
    # Financeiro
    "Sales Invoice": ["customer", "posting_date", "due_date", "items",
                      "grand_total", "outstanding_amount", "remarks"],
    "Purchase Invoice": ["supplier", "posting_date", "due_date", "items",
                         "grand_total", "outstanding_amount", "remarks"],
    "Payment Entry": ["payment_type", "party_type", "party", "posting_date",
                      "paid_amount", "mode_of_payment", "reference_no", "remarks"],
    "Journal Entry": ["voucher_type", "posting_date", "accounts", "user_remark"],
    # Produtos
    "Item": ["item_code", "item_name", "item_group", "stock_uom", "description",
             "image", "standard_rate", "is_stock_item", "opening_stock"],
    "Stock Entry": ["stock_entry_type", "posting_date", "items", "remarks"],
    "Stock Reconciliation": ["purpose", "posting_date", "items"],
    "Warehouse": ["warehouse_name", "parent_warehouse", "company"],
    # Quem compra e quem fornece
    "Customer": ["customer_name", "customer_group", "mobile_no", "email_id"],
    "Supplier": ["supplier_name", "supplier_group", "mobile_no", "email_id"],
    # Parcerias
    "Lead": ["lead_name", "company_name", "email_id", "mobile_no", "status"],
    "Contact": ["first_name", "last_name", "email_ids", "phone_nos", "company_name"],
    # Demandas
    "Issue": ["subject", "raised_by", "status", "priority", "description"],
}

# Nenhum campo de layout se esconde. Esconder uma Quebra de Coluna órfã o que
# estava na segunda coluna; esconder uma Quebra de Separador leva o separador
# inteiro — o formulário de Item ficou com 184 controlos e **nenhum visível**.
# O Frappe já recolhe sozinho a secção cujos campos estão todos escondidos, que
# é o efeito que se queria.
NUNCA_ESCONDER = {"Column Break", "Section Break", "Tab Break"}


def _repor_layout(doctype):
    """Desfazer o estrago da versão anterior, que escondia quebras de layout."""
    meta = frappe.get_meta(doctype)
    layout = {f.fieldname for f in meta.fields if f.fieldtype in NUNCA_ESCONDER}
    for ps in frappe.get_all(
        "Property Setter",
        filters={"doc_type": doctype, "property": "hidden", "field_name": ["in", list(layout)]},
        pluck="name",
    ):
        frappe.delete_doc("Property Setter", ps, force=1, ignore_permissions=True)


def lean_form(doctype):
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    if doctype not in FORMS or not frappe.db.exists("DocType", doctype):
        return None

    _repor_layout(doctype)
    frappe.clear_cache(doctype=doctype)

    manter = set(FORMS[doctype])
    meta = frappe.get_meta(doctype)
    encontrados = {f.fieldname for f in meta.fields}
    escondidos, obrigatorios_extra = [], []

    for field in meta.fields:
        if field.fieldname in manter or field.hidden:
            continue
        if field.fieldtype in NUNCA_ESCONDER:
            continue
        if field.reqd:
            # Obrigatório e **calculado** pode sair: o ERPNext preenche-o
            # sozinho e o utilizador nunca lhe toca (base_grand_total,
            # plc_conversion_rate). Obrigatório que a pessoa tem de preencher
            # fica, mesmo fora da lista — esconder um desses dá um formulário
            # que não grava e não explica porquê.
            if field.read_only:
                make_property_setter(doctype, field.fieldname, "hidden", 1, "Check",
                                     validate_fields_for_doctype=False)
                escondidos.append(field.fieldname)
            else:
                obrigatorios_extra.append(field.fieldname)
            continue
        make_property_setter(doctype, field.fieldname, "hidden", 1, "Check",
                             validate_fields_for_doctype=False)
        escondidos.append(field.fieldname)

    frappe.clear_cache(doctype=doctype)
    return {
        "doctype": doctype,
        "escondidos": len(escondidos),
        "visiveis": len(manter & encontrados) + len(obrigatorios_extra),
        "obrigatorios_mantidos": obrigatorios_extra,
        "nao_existem": sorted(manter - encontrados),
    }


def sync_forms():
    resultado = []
    for doctype in FORMS:
        r = lean_form(doctype)
        if r:
            resultado.append(r)
    frappe.db.commit()
    frappe.clear_cache()
    return resultado
