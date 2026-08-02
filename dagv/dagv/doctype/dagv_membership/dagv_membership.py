import frappe
from frappe.model.document import Document

from dagv.provisioning import apply_membership


class DAGVMembership(Document):
	def before_insert(self):
		if not self.requested_on:
			self.requested_on = frappe.utils.now_datetime()

	def before_save(self):
		self.set_title()

	def set_title(self):
		"""Name the record after the person, not after a hash.

		The doctype is autonamed by hash, so every list, quick list and link
		read like `pn7qrfn801` — which makes "Aprovar pn7qrfn801" an impossible
		thing to ask a director to do. The title is what a human needs in order
		to decide: who, and for which área.
		"""
		full_name = frappe.db.get_value("User", self.member, "full_name") if self.member else None
		self.title = " · ".join([p for p in (full_name or self.member, self.area) if p])

	def on_update(self):
		apply_membership(self)
