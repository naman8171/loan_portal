from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LoanPaymentRegister(models.TransientModel):
    _name = "loan.payment.register"
    _description = "Register Loan Payment"

    loan_id = fields.Many2one("loan.loan", required=True)
    installment_id = fields.Many2one("loan.installment", domain="[('loan_id', '=', loan_id), ('state', '!=', 'paid')]")
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    payment_mode = fields.Selection([("regular", "Regular"), ("advance", "Advance")], default="regular", required=True)
    percent = fields.Float(string="Percent", default=100.0)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="loan_id.currency_id")
    journal_id = fields.Many2one("account.journal", required=True, domain="[('type', 'in', ('bank', 'cash'))]")
    note = fields.Text()

    @api.onchange("percent", "payment_mode", "loan_id")
    def _onchange_percent(self):
        for rec in self:
            if rec.payment_mode == "advance" and rec.loan_id:
                rec.amount = (rec.loan_id.outstanding_amount * rec.percent) / 100

    def _allocate_components(self, installment, pay_amount):
        self.ensure_one()
        posted_for_line = self.env["loan.payment"].search([("installment_id", "=", installment.id)])
        remaining_penalty = max(installment.penalty_amount - sum(posted_for_line.mapped("penalty_component")), 0.0)
        remaining_fee = max(installment.fee_amount - sum(posted_for_line.mapped("fee_component")), 0.0)
        remaining_interest = max(installment.interest_amount - sum(posted_for_line.mapped("interest_component")), 0.0)
        remaining_principal = max(installment.principal_amount - sum(posted_for_line.mapped("principal_component")), 0.0)

        allocation = {"penalty_component": 0.0, "fee_component": 0.0, "interest_component": 0.0, "principal_component": 0.0}
        remaining = pay_amount
        for key, bucket in [
            ("penalty_component", remaining_penalty),
            ("fee_component", remaining_fee),
            ("interest_component", remaining_interest),
            ("principal_component", remaining_principal),
        ]:
            slice_amount = min(bucket, remaining)
            allocation[key] = slice_amount
            remaining -= slice_amount
            if remaining <= 0:
                break
        return allocation

    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Payment amount must be greater than zero."))
        if self.payment_date and self.loan_id.application_date and self.payment_date < self.loan_id.application_date:
            raise UserError(_("Payment date cannot be before application date."))

        if self.payment_mode == "advance":
            target_lines = self.loan_id.installment_ids.filtered(lambda l: l.state != "paid")
        else:
            target_lines = self.installment_id or self.loan_id.installment_ids.filtered(lambda l: l.state != "paid")[:1]

        if not target_lines:
            raise UserError(_("No unpaid installment found for this loan."))

        remaining = self.amount
        for line in target_lines:
            if remaining <= 0:
                break
            payable = line.amount_due - line.amount_paid
            pay = min(payable, remaining)
            if pay <= 0:
                continue
            line.apply_payment(pay, self.payment_date)
            allocation = self._allocate_components(line, pay)
            self.env["loan.payment"].create(
                {
                    "loan_id": self.loan_id.id,
                    "installment_id": line.id,
                    "payment_date": self.payment_date,
                    "journal_id": self.journal_id.id,
                    "amount": pay,
                    "principal_component": allocation["principal_component"],
                    "interest_component": allocation["interest_component"],
                    "fee_component": allocation["fee_component"],
                    "penalty_component": allocation["penalty_component"],
                    "note": self.note,
                }
            )
            remaining -= pay

        if remaining > 0.0001:
            raise UserError(
                _("Payment amount exceeds the total unpaid amount by %(extra).2f.")
                % {"extra": remaining}
            )

        if self.loan_id.installment_ids and all(line.state == "paid" for line in self.loan_id.installment_ids):
            self.loan_id.action_close()

        return {"type": "ir.actions.act_window_close"}
