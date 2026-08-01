"""Public (guest) API for the DAGV signup page."""

import re

import frappe

# The academic areas are not picked directly — members choose "Acadêmicos" and we
# route them to the VP of their own course.
COURSE_TO_ACADEMIC_AREA = {
    "Administração de Empresas": "VPAE",
    "Administração Pública": "VPAP",
    "Economia": "VPEcono",
}

ACADEMIC_CHIP = "Acadêmicos"

# Institutional pattern: C + 6 or 7 digits. Checked softly (warn, never block) —
# the domain is the hard gate, directors catch oddities at approval.
FGV_PATTERN = re.compile(r"^c\d{6,7}@fgv\.edu\.br$", re.IGNORECASE)


def resolve_areas(desired_areas, course):
    """Expand the "Acadêmicos" chip into the course's own VP area."""
    areas = [a.strip() for a in (desired_areas or "").split(",") if a.strip()]
    resolved = []
    for area in areas:
        if area == ACADEMIC_CHIP:
            mapped = COURSE_TO_ACADEMIC_AREA.get(course)
            if mapped and mapped not in resolved:
                resolved.append(mapped)
        elif area not in resolved:
            resolved.append(area)
    return resolved


@frappe.whitelist(allow_guest=True)
def submit_registration(
    full_name,
    fgv_email,
    course,
    personal_email,
    phone,
    semester=None,
    turma=None,
    desired_areas=None,
):
    """Create a pending DAGV Registration Request from the public signup page."""
    full_name = (full_name or "").strip()
    email = (fgv_email or "").lower().strip()
    personal_email = (personal_email or "").strip()
    phone = (phone or "").strip()

    if not full_name:
        frappe.throw("Informe seu nome completo.")
    if not email.endswith("@fgv.edu.br"):
        frappe.throw("O cadastro exige um e-mail institucional @fgv.edu.br.")
    if not personal_email or "@" not in personal_email:
        frappe.throw("Informe um e-mail pessoal válido.")
    if not phone:
        frappe.throw("Informe seu telefone.")
    if not course:
        frappe.throw("Selecione seu curso.")
    if course == "Administração de Empresas" and not (turma or "").strip():
        frappe.throw("Selecione sua turma.")
    if frappe.db.exists("DAGV Registration Request", email):
        frappe.throw("Já existe um cadastro com este e-mail — aguarde a confirmação.")

    areas = resolve_areas(desired_areas, course)

    doc = frappe.get_doc(
        {
            "doctype": "DAGV Registration Request",
            "full_name": full_name,
            "fgv_email": email,
            "personal_email": personal_email,
            "phone": phone,
            "semester": (semester or "").strip() or None,
            "course": course,
            "turma": (turma or "").strip() or None,
            "desired_areas": ", ".join(areas) or None,
            # Flagged for the approving director, never blocks the signup.
            "email_format_ok": 1 if FGV_PATTERN.match(email) else 0,
            "status": "Pending",
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
