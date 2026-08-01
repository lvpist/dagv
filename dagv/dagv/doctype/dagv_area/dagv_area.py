import frappe
from frappe.model.document import Document

from dagv.provisioning import ensure_area_backing


class DAGVArea(Document):
	def after_insert(self):
		"""A new area provisions its own Raven workspace and ERPNext role."""
		ensure_area_backing(self)
