from odoo import fields, models


class LoanCollectionReportWizard(models.TransientModel):
    _name = "loan.collection.report.wizard"
    _description = "Loan Collection Report Wizard"

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    def action_print(self):
        self.ensure_one()
        payments = self.env["loan.payment"].search([
            ("payment_date", ">=", self.date_from),
            ("payment_date", "<=", self.date_to),
        ])
        return self.env.ref("loan_management_system.action_report_loan_collection").report_action(payments)
