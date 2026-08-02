// Afordâncias de edição não são para quem só usa.
//
// A sidebar oferece "Add Sidebar Item" a todo mundo, inclusive a um membro que
// não pode — e não deveria querer — remontar a navegação do DAGV. Não dá para
// resolver só com CSS porque a folha de estilo não sabe quem está olhando, e
// esconder no servidor exigiria forkar o componente do Frappe. Cinco linhas
// aqui, revertidas sozinhas se o Frappe algum dia respeitar o papel.
frappe.after_ajax(() => {
	if (frappe.user.has_role("System Manager")) return;
	document.documentElement.classList.add("dagv-plain-user");
});
