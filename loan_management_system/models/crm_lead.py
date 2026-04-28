from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    loan_type_id = fields.Many2one("loan.type", string="Loan Type")
    loan_amount = fields.Monetary(string="Loan Amount", currency_field="currency_id")
    loan_term_months = fields.Integer(string="Loan Term (Months)", default=12)
    loan_request_count = fields.Integer(compute="_compute_loan_request_count")

    def _compute_loan_request_count(self):
        grouped = self.env["loan.loan"].read_group(
            [("lead_id", "in", self.ids)],
            ["lead_id"],
            ["lead_id"],
        )
        data = {g["lead_id"][0]: g["lead_id_count"] for g in grouped if g.get("lead_id")}
        for rec in self:
            rec.loan_request_count = data.get(rec.id, 0)

    def action_create_loan_request(self):
        self.ensure_one()
        partner = self.partner_id or self.env.user.partner_id
        loan_vals = {
            "partner_id": partner.id,
            "loan_type_id": self.loan_type_id.id,
            "principal_amount": self.loan_amount or 0.0,
            "term_months": self.loan_term_months or 12,
            "first_due_date": fields.Date.context_today(self),
            "purpose": self.name,
            "lead_id": self.id,
            "state": "draft",
        }
        loan = self.env["loan.loan"].create(loan_vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "loan.loan",
            "view_mode": "form",
            "res_id": loan.id,
        }

    def action_view_loan_requests(self):
        self.ensure_one()
        return {
            "name": "Loan Requests",
            "type": "ir.actions.act_window",
            "res_model": "loan.loan",
            "view_mode": "list,form",
            "domain": [("lead_id", "=", self.id)],
            "context": {"default_lead_id": self.id, "default_partner_id": self.partner_id.id},
        }
