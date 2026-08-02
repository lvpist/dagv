// Colour the status so the queue is scannable without reading: what needs a
// decision is orange, settled things recede.
frappe.listview_settings["DAGV Membership"] = {
	add_fields: ["status", "rank", "area"],
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
};
