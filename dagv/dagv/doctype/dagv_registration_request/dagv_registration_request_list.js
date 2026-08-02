// Pending sign-ups are the only ones that need action, so only they carry colour.
frappe.listview_settings["DAGV Registration Request"] = {
	add_fields: ["status", "course", "email_format_ok"],
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
};
