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
