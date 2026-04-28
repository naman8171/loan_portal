from odoo import api, fields, models


class LoanDisbursement(models.Model):
    _name = "loan.disbursement"
    _description = "Loan Disbursement"
    _order = "date desc, id desc"

    name = fields.Char(default="New", copy=False, readonly=True)
    loan_id = fields.Many2one("loan.loan", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="loan_id.partner_id", store=True)
    company_id = fields.Many2one(related="loan_id.company_id", store=True)
    currency_id = fields.Many2one(related="loan_id.currency_id", store=True)

    date = fields.Date(default=fields.Date.context_today, required=True)
    amount = fields.Monetary(required=True)
    journal_id = fields.Many2one("account.journal", required=True, domain="[('type', 'in', ('bank', 'cash'))]")
    reference = fields.Char()
    state = fields.Selection([("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")], default="draft")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("loan.disbursement") or "New"
        return super().create(vals_list)

    def action_post(self):
        self.write({"state": "posted"})

        template = self.env.ref(
            'loan_management_system.mail_template_disbursement',
            raise_if_not_found=False
        )

        for rec in self:
            if template and rec.partner_id.email:
                template.send_mail(rec.id, force_send=True)

    def action_cancel(self):
        self.write({"state": "cancel"})
        
    def action_print_disbursement(self):
        return self.env.ref(
            'loan_management_system.action_report_loan_disbursement'
        ).report_action(self)
