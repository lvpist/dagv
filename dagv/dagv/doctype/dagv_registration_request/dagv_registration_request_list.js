// Pending sign-ups are the only ones that need action, so only they carry colour.
//
// Approving a sign-up creates the account, the Raven user and the memberships,
// so it is a real operation — it belongs on a button that runs it, not on a
// status field somebody edits and hopes about.
frappe.listview_settings["DAGV Registration Request"] = {
	add_fields: ["status", "course", "email_format_ok", "full_name"],

	get_indicator: function (doc) {
		if (doc.status === "Pending") {
			return [
				doc.email_format_ok ? "Aguardando aprovação" : "Conferir e-mail",
				doc.email_format_ok ? "orange" : "red",
				"status,=,Pending",
			];
		}
		if (doc.status === "Approved") return ["Aprovado", "green", "status,=,Approved"];
		return ["Recusado", "gray", "status,=,Rejected"];
	},

	onload: function (listview) {
		const decide = (reject) => {
			const rows = listview.get_checked_items(true);
			if (!rows.length) return;

			const verb = reject ? "Recusar" : "Aprovar";
			frappe.confirm(
				`${verb} ${rows.length} ${rows.length === 1 ? "cadastro" : "cadastros"}?` +
					(reject ? "" : " As contas serão criadas."),
				() => {
					frappe.dom.freeze(`${verb}...`);
					Promise.all(
						rows.map((name) =>
							frappe
								.xcall("dagv.approvals.approve_registration", {
									registration: name,
									reject: reject ? 1 : 0,
								})
								.catch((e) => e)
						)
					).then(() => {
						frappe.dom.unfreeze();
						listview.refresh();
						frappe.show_alert(
							{
								message: `${rows.length} atualizado(s)`,
								indicator: reject ? "orange" : "green",
							},
							4
						);
					});
				}
			);
		};

		listview.page.add_action_item(__("Aprovar"), () => decide(false));
		listview.page.add_action_item(__("Recusar"), () => decide(true));
	},
};
