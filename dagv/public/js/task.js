// Only offer the áreas the person is actually in.
//
// The rule is enforced on the server (dagv.work.guard_task_area) — this just
// stops someone picking an área that would then be rejected on save, which is
// a worse way to learn the rule than never being shown it.
frappe.ui.form.on("Task", {
	setup(frm) {
		frm.set_query("dagv_area", () => ({ query: "dagv.work.area_link_query" }));
	},
});
