"""O site público: login e cadastro.

O desk é para quem já entrou. Isto é o que um caloiro vê antes de ter conta, e
por isso vive separado — o desk se configura com Workspace e Property Setter, e
o site com Website Script e Website Theme, que são coisas diferentes e não se
alcançam.

Tudo aqui é registro (`Website Script`, `Website Settings`), não código de app:
uma diretoria futura muda pela interface, em *Personalizar → Script de website*.
"""

import frappe

# Um cadastro que ninguém acha não serve de nada. A raiz do site é a tela de
# login, e ela não tinha nenhum caminho para o formulário de entrada: quem nunca
# teve conta chegava numa parede. O link é injetado por Website Script porque é
# assim que o Frappe deixa mexer nas páginas públicas sem forkar o template.
LOGIN_JOIN_LINK = r"""
// DAGV: quem ainda não é membro precisa achar o cadastro a partir do login.
(function () {
	if (!/^\/login/.test(window.location.pathname)) return;
	function add() {
		var box = document.querySelector(".for-login") || document.querySelector(".login-content");
		if (!box || document.getElementById("dagv-join-link")) return;
		var p = document.createElement("p");
		p.id = "dagv-join-link";
		p.style.cssText = "margin-top:16px;text-align:center;font-size:13px";
		p.innerHTML =
			'Ainda não faz parte do DAGV? <a href="/join" style="font-weight:600">Faça seu cadastro</a>';
		box.appendChild(p);
	}
	document.addEventListener("DOMContentLoaded", add);
	add();
	setTimeout(add, 600);
})();
"""


def link_join_from_login():
    doc = frappe.get_single("Website Script")
    doc.javascript = LOGIN_JOIN_LINK
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    frappe.clear_cache()
    return {"website_script": "login -> /join"}


def dagv_website_theme():
    """O tema do site público, na marca do DAGV.

    Deliberadamente contido: só cor primária, fonte e cantos. `/join` já tem um
    desenho próprio e conferido, e um tema que redefinisse tudo brigaria com ele
    — a lição de Bootstrap batendo com CSS da página já custou caro uma vez.
    O que muda aqui é o que o Frappe desenha sozinho: botões, links e o login.
    """
    name = "DAGV"
    doc = (
        frappe.get_doc("Website Theme", name)
        if frappe.db.exists("Website Theme", name)
        else frappe.new_doc("Website Theme")
    )
    doc.theme = name
    doc.google_font = "Inter"
    doc.button_rounded_corners = 1
    doc.button_shadows = 0
    doc.button_gradients = 0
    # Os campos de cor do Website Theme são Link para o doctype `Color`, não
    # texto: passar um hex ali dá LinkValidationError. A marca entra por SCSS,
    # que é onde o Frappe espera receber cor livre — e é editável em
    # Personalizar → Tema de website → Folha de estilo.
    doc.custom_scss = (
        "$primary: #9c8416;\n"
        "$body-color: #171717;\n"
        "$border-radius: 8px;\n"
    )
    doc.flags.ignore_permissions = True
    doc.save() if not doc.is_new() else doc.insert()

    ws = frappe.get_single("Website Settings")
    ws.website_theme = name
    ws.flags.ignore_permissions = True
    ws.save()

    frappe.db.commit()
    frappe.clear_cache()
    return {"website_theme": name}


def sync():
    return {
        "login_link": link_join_from_login(),
        "theme": dagv_website_theme(),
    }
