// O seletor de módulos só mostra o que é mesmo uma app utilizável.
//
// Por omissão um Link para Module Def oferece os 39 módulos instalados,
// incluindo Bulk Transaction, EDI, Regional e Communication — encanamento do
// Frappe que não abre página nenhuma. Quem escolhe as ferramentas de uma área
// não tem como saber isso, e a lista fazia parecer que a configuração estava
// errada. A regra vive no servidor (dagv.homescreen.module_link_query), que é
// quem sabe que páginas existem.
frappe.ui.form.on("DAGV Area", {
	setup(frm) {
		frm.set_query("module", "erp_modules", () => ({
			query: "dagv.homescreen.module_link_query",
		}));
	},
});
