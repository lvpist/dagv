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
					).then((results) => {
						frappe.dom.unfreeze();
						listview.refresh();
						frappe.show_alert(
							{
								message: `${rows.length} atualizado(s)`,
								indicator: reject ? "orange" : "green",
							},
							4
						);

						// Approving creates the accounts but cannot mail anybody:
						// the site has no outgoing e-mail. Hand the approver the
						// links so the people they just let in can actually get in.
						const invites = (results || []).filter((r) => r && r.invite);
						if (!reject && invites.length) show_invites(invites);
					});
				}
			);
		};

		listview.page.add_action_item(__("Aprovar"), () => decide(false));
		listview.page.add_action_item(__("Recusar"), () => decide(true));
	},
};

// Until SMTP exists, the invite is delivered by a human. Make that one click:
// one block of text, ready to paste into the group chat.
function show_invites(invites) {
	const lines = invites.map((i) => `${i.full_name || i.email}: ${i.invite}`).join("\n");
	const d = new frappe.ui.Dialog({
		title: __("Links de acesso"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted" style="margin-bottom:8px">
					Ainda não há e-mail configurado no site, então estes links não foram
					enviados. Cada um serve uma vez e é onde a pessoa cria a senha dela.
					Mande no WhatsApp ou no Raven.</p>`,
			},
			{ fieldtype: "Code", fieldname: "links", label: __("Copie e envie"), default: lines },
		],
		primary_action_label: __("Copiar tudo"),
		primary_action() {
			frappe.utils.copy_to_clipboard(lines);
			d.hide();
		},
	});
	d.show();
}
