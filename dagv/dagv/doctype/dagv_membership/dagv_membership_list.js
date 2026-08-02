// Colour the status so the queue is scannable without reading: what needs a
// decision is orange, settled things recede.
//
// And make deciding an *action*. Approving used to mean opening a record,
// finding a Select field and saving it — which is editing a spreadsheet, not
// approving someone. Select the rows, press Aprovar. The server still checks
// that you lead that área (dagv.approvals.decide), so the button is a shortcut
// through the same rules, never around them.
frappe.listview_settings["DAGV Membership"] = {
	add_fields: ["status", "rank", "area", "member"],

	get_indicator: function (doc) {
		const map = {
			Requested: ["Aguardando entrada", "orange", "status,=,Requested"],
			"Leave Requested": ["Aguardando saída", "red", "status,=,Leave Requested"],
			Approved: ["Ativo", "green", "status,=,Approved"],
			Rejected: ["Recusado", "gray", "status,=,Rejected"],
			Removed: ["Saiu", "gray", "status,=,Removed"],
		};
		return map[doc.status] || [doc.status, "gray", "status,=," + doc.status];
	},

	onload: function (listview) {
		const decide = (approve) => {
			const rows = listview.get_checked_items(true);
			if (!rows.length) return;

			const verb = approve ? "Aprovar" : "Recusar";
			frappe.confirm(
				`${verb} ${rows.length} ${rows.length === 1 ? "pedido" : "pedidos"}?`,
				() => {
					frappe.dom.freeze(`${verb}...`);
					Promise.all(
						rows.map((name) =>
							frappe
								.xcall("dagv.approvals.decide", {
									membership: name,
									approve: approve ? 1 : 0,
								})
								.catch((e) => e)
						)
					).then(() => {
						frappe.dom.unfreeze();
						listview.refresh();
						frappe.show_alert(
							{
								message: `${rows.length} atualizado(s)`,
								indicator: approve ? "green" : "orange",
							},
							4
						);
					});
				}
			);
		};

		listview.page.add_action_item(__("Aprovar"), () => decide(true));
		listview.page.add_action_item(__("Recusar"), () => decide(false));
	},
};
