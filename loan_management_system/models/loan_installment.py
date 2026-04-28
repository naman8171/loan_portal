from datetime import date

from odoo import api, fields, models


class LoanInstallment(models.Model):
    _name = "loan.installment"
    _description = "Loan Installment"
    _order = "loan_id, sequence"

    loan_id = fields.Many2one("loan.loan", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="loan_id.company_id", store=True)
    currency_id = fields.Many2one(related="loan_id.currency_id", store=True)

    sequence = fields.Integer(required=True)
    due_date = fields.Date(required=True)
    opening_balance = fields.Monetary(required=True)
    principal_amount = fields.Monetary(required=True)
    interest_amount = fields.Monetary(required=True)
    fee_amount = fields.Monetary(default=0.0)
    penalty_amount = fields.Monetary(default=0.0)
    amount_due = fields.Monetary(required=True)
    amount_paid = fields.Monetary(default=0.0)
    balance_amount = fields.Monetary(required=True)

    state = fields.Selection(
        [("unpaid", "Unpaid"), ("partial", "Partially Paid"), ("paid", "Paid")],
        default="unpaid",
    )
    paid_on = fields.Date()
    late_days = fields.Integer(compute="_compute_late_days", store=True)
    paid_principal = fields.Monetary(compute="_compute_paid_breakdown", store=True)
    paid_interest = fields.Monetary(compute="_compute_paid_breakdown", store=True)
    paid_fee = fields.Monetary(compute="_compute_paid_breakdown", store=True)
    paid_penalty = fields.Monetary(compute="_compute_paid_breakdown", store=True)

    _sql_constraints = [
        ("loan_sequence_unique", "unique(loan_id, sequence)", "Installment sequence must be unique per loan."),
    ]

    @api.depends("due_date", "state")
    def _compute_late_days(self):
        today = date.today()
        for rec in self:
            if rec.state == "paid" or not rec.due_date:
                rec.late_days = 0
            else:
                rec.late_days = max((today - rec.due_date).days, 0)

    @api.depends(
        "loan_id.payment_ids.amount",
        "loan_id.payment_ids.principal_component",
        "loan_id.payment_ids.interest_component",
        "loan_id.payment_ids.fee_component",
        "loan_id.payment_ids.penalty_component",
        "loan_id.payment_ids.installment_id",
    )
    def _compute_paid_breakdown(self):
        for rec in self:
            payments = rec.loan_id.payment_ids.filtered(lambda p: p.installment_id == rec)
            rec.paid_principal = sum(payments.mapped("principal_component"))
            rec.paid_interest = sum(payments.mapped("interest_component"))
            rec.paid_fee = sum(payments.mapped("fee_component"))
            rec.paid_penalty = sum(payments.mapped("penalty_component"))

    def apply_payment(self, amount, payment_date):
        for rec in self:
            new_paid = min(rec.amount_paid + amount, rec.amount_due)
            vals = {"amount_paid": new_paid, "paid_on": payment_date}
            if new_paid >= rec.amount_due:
                vals["state"] = "paid"
            elif new_paid > 0:
                vals["state"] = "partial"
            rec.write(vals)

    def action_mark_paid(self):
        for rec in self:
            rec.write({"state": "paid", "amount_paid": rec.amount_due, "paid_on": fields.Date.context_today(self)})

    def action_mark_unpaid(self):
        self.write({"state": "unpaid", "amount_paid": 0.0, "paid_on": False})

    def action_register_payment(self):
        self.ensure_one()
        return {
            "name": "Register Payment",
            "type": "ir.actions.act_window",
            "res_model": "loan.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_loan_id": self.loan_id.id,
                "default_installment_id": self.id,
                "default_payment_mode": "regular",
                "default_amount": self.amount_due - self.amount_paid,
                "default_journal_id": self.loan_id.loan_type_id.journal_id.id,
            },
        }
    
    @api.model
    def create(self, vals):
        record = super().create(vals)

        template = self.env.ref(
            'loan_management_system.mail_template_installment_created',
            raise_if_not_found=False
        )

        if template and record.loan_id.partner_id.email:
            template.send_mail(record.id, force_send=True)

        return record
    

