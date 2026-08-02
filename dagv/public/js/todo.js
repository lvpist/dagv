// A ToDo is not a destination.
//
// Frappe writes a ToDo as the shadow record behind an assignment. Opening one
// shows a copy of the work — its own description, its own status, its own
// "Referência" block — and editing it moves nothing. So when a ToDo points at a
// real document, go straight there. The assignment list stays useful (it is the
// only list that is genuinely per-person) and clicking a row now lands on the
// task itself, where the sidebar has the real assignment, comments and history.
frappe.ui.form.on("ToDo", {
	onload(frm) {
		if (frm.is_new() || !frm.doc.reference_type || !frm.doc.reference_name) return;
		frappe.set_route("Form", frm.doc.reference_type, frm.doc.reference_name);
	},
});
