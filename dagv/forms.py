"""Lean forms.

ERPNext's Task is built for a consultancy that bills hours: it carries costing,
timesheets, dependency graphs, templates, milestones, weights, departments and
companies. A student union needs six fields. Everything else is noise a
19-year-old has to read past to find the due date, and noise is what makes
people stop using a tool.

Every change here is a **Property Setter** — exactly what the *Customizar
Formulário* screen writes. So a future diretoria can reveal any of these again
by clicking, without a developer. Nothing is forked, nothing is deleted.

    Task   ->  Assunto · Área · Situação · Prioridade · Vencimento · Descrição
    ToDo   ->  not a destination at all (see public/js/todo.js)

Assignment deliberately does NOT get a field. Frappe already puts it in the
form sidebar as avatars with a searchable picker — the affordance exists and is
better than any field we would add; the old screen only looked bad because it
was showing the raw ToDo record instead of the Task.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

# What survives: what, whose, where it stands, how urgent, by when, details.
TASK_KEEP = {"subject", "dagv_area", "status", "priority", "exp_end_date",
             "description", "column_break0", "sb_details"}

# Everything an ERP needs and a DA does not. Grouped by why it goes.
TASK_HIDE = [
    # belongs to project accounting, not to us
    "project", "issue", "type", "department", "company",
    # tree/dependency machinery
    "is_group", "parent_task", "sb_depends_on", "depends_on", "depends_on_tasks",
    "dependencies_tab",
    # timesheet-derived, and we have no timesheets
    "sb_actual", "act_start_date", "actual_time", "act_end_date", "column_break_15",
    "sb_costing", "total_costing_amount", "total_billing_amount", "column_break_20",
    # planning detail nobody in a DA will fill in
    "exp_start_date", "expected_time", "task_weight", "progress", "is_milestone",
    "review_date", "closing_date", "completed_by", "completed_on",
    "is_template", "start", "duration", "template_task",
    # the leftover containers of everything above
    "sb_more_info", "column_break_22", "more_info_tab",
    "section_break_dafi", "column_break_vvfp",
    # Colour is not a priority — it was the second most prominent control on the
    # old screen, above the due date. It is decoration; the board already
    # colours by status.
    "color",
]

# NOT hidden, deliberately: `column_break_11`. Hiding a Column Break does not
# merge its columns, it orphans everything that lived in the second one — the
# due date vanished from the form entirely while still reporting hidden=0.
# Frappe drops an empty column on its own once its fields are hidden.
TASK_KEEP_LAYOUT = ["column_break_11"]


def lean_task():
    made = []

    for fieldname in TASK_HIDE:
        make_property_setter("Task", fieldname, "hidden", 1, "Check",
                             validate_fields_for_doctype=False)
        made.append(fieldname)

    for fieldname in TASK_KEEP_LAYOUT:
        make_property_setter("Task", fieldname, "hidden", 0, "Check",
                             validate_fields_for_doctype=False)

    # The two surviving section headers say nothing ("Timeline", "Details") —
    # unlabelled, they read as plain dividers instead of chapters.
    for fieldname in ("sb_timeline", "sb_details"):
        make_property_setter("Task", fieldname, "label", "", "Data",
                             validate_fields_for_doctype=False)

    # A full rich-text editor — two toolbar rows, tables, code blocks — to write
    # "ligar para o fornecedor". A plain box is the honest size of the job.
    #
    # "Text", not "Small Text": Frappe's ALLOWED_FIELDTYPE_CHANGE only groups
    # Text Editor with ("Text", "Code", "Signature", "HTML Editor"). Both render
    # the same plain textarea, but only this one is a change the platform
    # supports, so it survives upgrades instead of being a private fork.
    make_property_setter("Task", "description", "fieldtype", "Text", "Data",
                         validate_fields_for_doctype=False)

    # Say what the date means. "Expected End Date" is a project-management term;
    # people miss deadlines they had to translate first.
    make_property_setter("Task", "exp_end_date", "label", "Vencimento", "Data",
                         validate_fields_for_doctype=False)
    make_property_setter("Task", "subject", "label", "O que precisa ser feito", "Data",
                         validate_fields_for_doctype=False)
    # ERPNext ships this one as "Task Description", which pt-BR does not cover.
    make_property_setter("Task", "description", "label", "Detalhes", "Data",
                         validate_fields_for_doctype=False)
    make_property_setter("Task", "description", "description",
                         "Opcional. Links, contatos, o que já foi tentado.", "Text",
                         validate_fields_for_doctype=False)

    # The list should answer the same questions as the form, at a glance.
    for fieldname in ("dagv_area", "status", "exp_end_date"):
        make_property_setter("Task", fieldname, "in_list_view", 1, "Check",
                             validate_fields_for_doctype=False)
    for fieldname in ("status", "priority", "dagv_area"):
        make_property_setter("Task", fieldname, "in_standard_filter", 1, "Check",
                             validate_fields_for_doctype=False)

    frappe.clear_cache(doctype="Task")
    frappe.db.commit()
    return {"hidden": len(made)}


# ---------------------------------------------------------------------------
# ToDo — plumbing, not a page
# ---------------------------------------------------------------------------
# A ToDo is the shadow record Frappe writes when work is assigned. It is not the
# work. Landing on it means editing a copy: change the description here and the
# task does not move. public/js/todo.js sends people to the real document; this
# only tidies what is left for the rare ToDo with nothing behind it.

TODO_HIDE = [
    "color",
    "section_break_6", "reference_type", "reference_name", "column_break_10",
    "role", "assigned_by", "assigned_by_full_name", "assignment_rule",
]


def lean_todo():
    for fieldname in TODO_HIDE:
        make_property_setter("ToDo", fieldname, "hidden", 1, "Check",
                             validate_fields_for_doctype=False)
    make_property_setter("ToDo", "description", "fieldtype", "Text", "Data",
                         validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="ToDo")
    frappe.db.commit()
    return {"hidden": len(TODO_HIDE)}


# ---------------------------------------------------------------------------
# The board's cards
# ---------------------------------------------------------------------------

def lean_board():
    """Put on each card what you need to triage without opening it.

    A card showing only a title makes you click every one to find out whose it
    is and when it is due — which is the same failure as a page of list links,
    one level down.
    """
    from dagv.work import BOARD

    if not frappe.db.exists("Kanban Board", BOARD):
        return {"skipped": BOARD}

    doc = frappe.get_doc("Kanban Board", BOARD)
    doc.fields = frappe.as_json(["dagv_area", "exp_end_date", "priority"])
    doc.show_labels = 1
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"board": BOARD}


def people_have_names():
    """Show people by name everywhere, not by e-mail.

    Searching already matched on the full name — typing "eu" found "eu teste" —
    but every dropdown led with `c123232@fgv.edu.br` and put the name in small
    grey text underneath. So it read as though you had to know somebody's
    matrícula to assign them anything, and you could not tell whether you had
    picked the right person.

    `show_title_field_in_link` makes User links render their title (full_name)
    first, with the e-mail as the secondary line. One switch, and it applies to
    every user reference in the system — assignment, mentions, approvals.
    """
    make_property_setter("User", None, "show_title_field_in_link", 1, "Check",
                         for_doctype=True, validate_fields_for_doctype=False)
    # Membership rows point at a person too; same treatment.
    make_property_setter("DAGV Membership", None, "show_title_field_in_link", 1,
                         "Check", for_doctype=True, validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="User")
    frappe.db.commit()
    return {"ok": True}


def lean_area():
    """Tirar do formulário de Área o que ninguém preenche.

    "Curso obrigatório" só faz sentido nas três VPs académicas, e essas já estão
    definidas desde o início. Aparecia nas quinze e não era para ser mexido em
    nenhuma. Escondido, não apagado: o valor das três continua lá e continua a
    ser respeitado na aprovação — muda apenas deixar de pedir uma decisão que
    não existe. Volta em Personalizar Formulário desmarcando a caixa.
    """
    # `hidden` não serve aqui: o Frappe continua a desenhar campos escondidos
    # para quem é System Manager, que é justamente quem edita áreas. `depends_on`
    # é avaliado sempre — e "só aparece se já tiver curso" resolve sem escrever
    # VPAE/VPAP/VPEcono no código: as três têm valor, as outras doze não.
    make_property_setter("DAGV Area", "required_course", "hidden", 0, "Check",
                         validate_fields_for_doctype=False)
    # `Code`, não `Data`: o `property_type` tem de bater com o tipo real do campo
    # em DocField, senão o Frappe grava o Property Setter e ignora-o em silêncio.
    # Foi por isso que o campo continuou à vista mesmo com a meta a dizer o
    # contrário.
    make_property_setter("DAGV Area", "required_course", "depends_on",
                         "eval:doc.required_course", "Code",
                         validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="DAGV Area")
    frappe.db.commit()
    return {"ok": True}


def list_defaults():
    """Cada lista já abre útil, sem ninguém precisar configurar nada.

    Uma lista que abre pela ordem de criação obriga a pessoa a ordenar toda vez
    para descobrir o que vence primeiro — e quem não sabe que dá para ordenar
    simplesmente não vê o prazo. Trabalho com prazo se lê por vencimento.
    """
    # Tarefa: o que vence antes aparece antes.
    make_property_setter("Task", None, "sort_field", "exp_end_date", "Data",
                         for_doctype=True, validate_fields_for_doctype=False)
    make_property_setter("Task", None, "sort_order", "ASC", "Data",
                         for_doctype=True, validate_fields_for_doctype=False)

    # Área: a lista mostrava o ID; agora mostra o nome, e dá para filtrar pelo
    # que de facto distingue uma área das outras.
    make_property_setter("DAGV Area", None, "title_field", "area_name", "Data",
                         for_doctype=True, validate_fields_for_doctype=False)
    make_property_setter("DAGV Area", None, "show_title_field_in_link", 1, "Check",
                         for_doctype=True, validate_fields_for_doctype=False)
    for fieldname in ("category", "is_active"):
        make_property_setter("DAGV Area", fieldname, "in_standard_filter", 1, "Check",
                             validate_fields_for_doctype=False)

    # Filiação: quem decide quer ver primeiro quem está esperando.
    make_property_setter("DAGV Membership", None, "sort_field", "modified", "Data",
                         for_doctype=True, validate_fields_for_doctype=False)

    frappe.clear_cache()
    frappe.db.commit()
    return {"ok": True}


# Filtros que valem para todo mundo. Nenhum depende de quem está olhando — um
# filtro salvo é um registro compartilhado, então "minhas tarefas" não cabe aqui
# (isso é o cartão "Comigo agora", que sabe quem abriu a página).
SAVED_FILTERS = [
    ("Task", "Atrasadas", [["Task", "exp_end_date", "<", "Today"],
                           ["Task", "status", "in", ["Open", "Working", "Pending Review", "Overdue"]]]),
    ("Task", "Sem responsável", [["Task", "_assign", "is", "not set"],
                                 ["Task", "status", "in", ["Open", "Working", "Pending Review", "Overdue"]]]),
    ("Task", "Concluídas", [["Task", "status", "=", "Completed"]]),
    ("DAGV Membership", "Esperando decisão",
     [["DAGV Membership", "status", "in", ["Requested", "Leave Requested"]]]),
    ("DAGV Registration Request", "A aprovar",
     [["DAGV Registration Request", "status", "=", "Pending"]]),
]


def saved_filters():
    made = []
    for doctype, label, filters in SAVED_FILTERS:
        existing = frappe.db.exists(
            "List Filter", {"reference_doctype": doctype, "filter_name": label}
        )
        doc = (
            frappe.get_doc("List Filter", existing)
            if existing
            else frappe.new_doc("List Filter")
        )
        doc.reference_doctype = doctype
        doc.filter_name = label
        doc.for_user = ""      # vazio = de todo mundo, não meu
        doc.filters = frappe.as_json(filters)
        doc.flags.ignore_permissions = True
        doc.save() if not doc.is_new() else doc.insert()
        made.append(f"{doctype}: {label}")
    frappe.db.commit()
    return {"filters": made}


def sync():
    lean_task()
    lean_todo()
    lean_board()
    people_have_names()
    lean_area()
    list_defaults()
    saved_filters()
    return {"ok": True}
