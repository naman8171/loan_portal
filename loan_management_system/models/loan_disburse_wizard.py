from odoo import _, fields, models
from odoo.exceptions import UserError


class LoanDisburseWizard(models.TransientModel):
    _name = "loan.disburse.wizard"
    _description = "Register Loan Disbursement"

    loan_id = fields.Many2one("loan.loan", required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="loan_id.currency_id")
    journal_id = fields.Many2one("account.journal", required=True, domain="[('type', 'in', ('bank', 'cash'))]")
    reference = fields.Char()

    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Disbursement amount must be greater than zero."))
        if self.amount > self.loan_id.remaining_to_disburse:
            raise UserError(_("Disbursement amount cannot exceed pending amount."))

        disb = self.env["loan.disbursement"].create(
            {
                "loan_id": self.loan_id.id,
                "date": self.date,
                "amount": self.amount,
                "journal_id": self.journal_id.id,
                "reference": self.reference,
            }
        )
        disb.action_post()

        if self.loan_id.remaining_to_disburse - self.amount <= 0:
            self.loan_id.action_disburse()

        return {"type": "ir.actions.act_window_close"}
