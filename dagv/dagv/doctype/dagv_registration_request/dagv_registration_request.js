// Invite links expire and people lose them, so re-issuing one has to be a
// button rather than a support request. Same mechanism as approval — Frappe's
// own single-use reset link — just handed over again.
frappe.ui.form.on("DAGV Registration Request", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Approved") return;

		if (frm.doc.invite_link) {
			frm.add_custom_button(__("Copiar link de acesso"), () => {
				frappe.utils.copy_to_clipboard(frm.doc.invite_link);
			});
		}

		frm.add_custom_button(__("Gerar novo link"), () => {
			frappe
				.xcall("dagv.approvals.invite_for", { email: frm.doc.fgv_email })
				.then((res) => {
					frm.reload_doc();
					frappe.msgprint({
						title: __("Novo link de acesso"),
						indicator: "green",
						message: `<p>Vale uma vez só. Mande para ${frappe.utils.escape_html(
							frm.doc.full_name || res.email
						)}:</p><pre style="white-space:pre-wrap;word-break:break-all">${frappe.utils.escape_html(
							res.invite
						)}</pre>`,
					});
				});
		});
	},
});
