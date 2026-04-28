from odoo import models, fields, api

class LoanProofLine(models.Model):
    _name = "loan.proof.line"

    loan_id = fields.Many2one("loan.loan", ondelete="cascade")

    proof_type_id = fields.Many2one("loan.proofs", required=True)
    document_name = fields.Char(required=True)
    file_data = fields.Binary()
    uploaded_on = fields.Datetime(default=fields.Datetime.now)