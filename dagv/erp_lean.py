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
