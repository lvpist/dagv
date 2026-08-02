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


def sync():
    return {"login_link": link_join_from_login()}
