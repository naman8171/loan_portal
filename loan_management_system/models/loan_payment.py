from odoo import api, fields, models


class LoanPayment(models.Model):
    _name = "loan.payment"
    _description = "Loan Payment"
    _order = "payment_date desc, id desc"

    name = fields.Char(required=True, default="New", copy=False)
    loan_id = fields.Many2one("loan.loan", required=True, ondelete="cascade")
    installment_id = fields.Many2one("loan.installment", ondelete="set null")
    partner_id = fields.Many2one(related="loan_id.partner_id", store=True)
    company_id = fields.Many2one(related="loan_id.company_id", store=True)
    currency_id = fields.Many2one(related="loan_id.currency_id", store=True)

    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        "account.journal", domain="[('type', 'in', ('bank', 'cash'))]"
    )
    payment_method = fields.Selection(
        [
            ("bank_transfer", "Bank Transfer"),
            ("cash",          "Cash"),
            ("cheque",        "Cheque"),
            ("online",        "Online / UPI"),
        ],
        string="Payment Method",
        default="bank_transfer",
    )
    transaction_ref = fields.Char(string="Transaction / Reference No.")
    amount = fields.Monetary(required=True)
    principal_component = fields.Monetary()
    interest_component  = fields.Monetary()
    fee_component       = fields.Monetary()
    penalty_component   = fields.Monetary()
    note = fields.Text()

    # Source flag for portal payments
    source = fields.Selection(
        [("backend", "Backend"), ("portal", "Customer Portal")],
        default="backend",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("loan.payment") or "New"
                )
        return super().create(vals_list)
