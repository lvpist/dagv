import frappe
from frappe.model.document import Document

from dagv.provisioning import apply_membership


class DAGVMembership(Document):
	def before_insert(self):
		if not self.requested_on:
			self.requested_on = frappe.utils.now_datetime()

	def on_update(self):
		apply_membership(self)
