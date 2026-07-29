import frappe
from frappe.model.document import Document
from frappe.utils import flt

CATEGORIES = ["Labour", "Material", "Equipment", "Subcontract", "Other"]


class SiteActivity(Document):
    def validate(self):
        totals = {c: 0.0 for c in CATEGORIES}
        grand = 0.0
        for row in (self.resources or []):
            res = frappe.db.get_value(
                "Site Resource", row.resource, ["rate", "category"], as_dict=True
            )
            if not res:
                continue
            amt = flt(row.coefficient) * flt(res.rate)
            grand += amt
            if res.category in totals:
                totals[res.category] += amt
        self.unit_rate = grand
        self.labour_rate = totals["Labour"]
        self.material_rate = totals["Material"]
        self.equipment_rate = totals["Equipment"]
        self.subcontract_rate = totals["Subcontract"]
        self.other_rate = totals["Other"]
