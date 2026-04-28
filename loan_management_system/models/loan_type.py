from odoo import fields, models, api
from odoo.exceptions import ValidationError


class LoanType(models.Model):
    _name = "loan.type"
    _description = "Loan Type"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)

    min_amount = fields.Monetary()
    max_amount = fields.Monetary()
    default_interest_rate = fields.Float()
    default_term_months = fields.Integer(default=12)
    processing_fee_percent = fields.Float()

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True
    )

    # Accounting
    journal_id = fields.Many2one("account.journal")
    income_account_id = fields.Many2one("account.account")
    receivable_account_id = fields.Many2one("account.account")

    borrower_category_ids = fields.Many2many(
        "loan.borrower.category", string="Borrower Category"
    )

    document_ids = fields.Many2many(
        "loan.required.document", string="Required Documents"
    )

    eligibility_criteria_ids = fields.Many2many(
        "loan.eligibility.criteria", string="Eligibility Criteria"
    )

    processing_fee_text = fields.Char("Processing Fees")

    color = fields.Char("Color")

    number_of_reminders = fields.Integer(default=2)
    reminder_days = fields.Char("Reminder Before Days")

    agreement_template = fields.Html()

    # # ✅ VALIDATION (image wala error)
    # @api.constrains('reminder_days', 'number_of_reminders')
    # def _check_reminder_days(self):
    #     for rec in self:
    #         if rec.reminder_days:
    #             days = rec.reminder_days.split(',')
    #             if len(days) != rec.number_of_reminders:
    #                 raise ValidationError(
    #                     "Please select exactly %s day(s) in the Reminder Days field."
    #                     % rec.number_of_reminders
    #                 )