import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ProjectBOQ(Document):
    def validate(self):
        tot = {"amount": 0.0, "labour": 0.0, "material": 0.0,
               "equipment": 0.0, "subcontract": 0.0, "other": 0.0}
        for it in (self.items or []):
            act = frappe.db.get_value(
                "Site Activity", it.activity,
                ["output_unit", "unit_rate", "labour_rate", "material_rate",
                 "equipment_rate", "subcontract_rate", "other_rate"],
                as_dict=True)
            if not act:
                continue
            it.unit = it.unit or act.output_unit
            if not flt(it.rate):
                it.rate = flt(act.unit_rate)
            qty = flt(it.qty)
            # scale the split so it always sums to qty*rate even if rate edited
            base = flt(act.unit_rate)
            factor = (flt(it.rate) / base) if base else 0.0
            it.amount = qty * flt(it.rate)
            it.labour_amount = qty * flt(act.labour_rate) * factor
            it.material_amount = qty * flt(act.material_rate) * factor
            it.equipment_amount = qty * flt(act.equipment_rate) * factor
            it.subcontract_amount = qty * flt(act.subcontract_rate) * factor
            it.other_amount = qty * flt(act.other_rate) * factor
            tot["amount"] += it.amount
            tot["labour"] += it.labour_amount
            tot["material"] += it.material_amount
            tot["equipment"] += it.equipment_amount
            tot["subcontract"] += it.subcontract_amount
            tot["other"] += it.other_amount
        self.total_amount = tot["amount"]
        self.total_labour = tot["labour"]
        self.total_material = tot["material"]
        self.total_equipment = tot["equipment"]
        self.total_subcontract = tot["subcontract"]
        self.total_other = tot["other"]
