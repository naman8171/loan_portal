from odoo import _, fields, models
from odoo.exceptions import UserError


class LoanForecloseWizard(models.TransientModel):
    _name = "loan.foreclose.wizard"
    _description = "Loan Foreclosure"

    loan_id = fields.Many2one("loan.loan", required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    settlement_amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="loan_id.currency_id")
    note = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        if self.settlement_amount <= 0:
            raise UserError(_("Settlement amount must be greater than zero."))

        self.loan_id.write(
            {
                "state": "closed",
                "foreclosure_date": self.date,
                "settlement_amount": self.settlement_amount,
                "close_note": self.note,
            }
        )
        unpaid_lines = self.loan_id.installment_ids.filtered(lambda l: l.state != "paid")
        for line in unpaid_lines:
            line.write({"state": "paid", "amount_paid": line.amount_due, "paid_on": self.date})

        self.env["loan.payment"].create(
            {
                "loan_id": self.loan_id.id,
                "payment_date": self.date,
                "amount": self.settlement_amount,
                "principal_component": self.settlement_amount,
                "note": _("Foreclosure Settlement") + (f"\n{self.note}" if self.note else ""),
            }
        )
        return {"type": "ir.actions.act_window_close"}
