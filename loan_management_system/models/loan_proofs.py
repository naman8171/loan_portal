from odoo import models, fields


# 🔹 Loan Proofs
class LoanProofs(models.Model):
    _name = "loan.proofs"
    _description = "Loan Proofs"

    name = fields.Char("Proof Name", required=True)
    description = fields.Text("Description")
    active = fields.Boolean("Active", default=True)


# 🔹 Borrower Category
class BorrowerCategory(models.Model):
    _name = "loan.borrower.category"
    _description = "Borrower Category"

    name = fields.Char("Category Name", required=True)
    description = fields.Text()


# 🔹 Eligibility
class EligibilityCriteria(models.Model):
    _name = "loan.eligibility.criteria"
    _description = "Eligibility Criteria"

    name = fields.Char("Criteria Name", required=True)
    min_income = fields.Float("Minimum Income")
    max_age = fields.Integer("Maximum Age")


# 🔹 Co-Borrower
class CoBorrowerRelation(models.Model):
    _name = "loan.coborrower.relation"
    _description = "Co-Borrower Relation"

    name = fields.Char("Relation Name", required=True)


# 🔹 Agreement Type
class AgreementType(models.Model):
    _name = "loan.agreement.type"
    _description = "Agreement Type"

    name = fields.Char("Agreement Type", required=True)


# 🔹 Notice Type
class NoticeType(models.Model):
    _name = "loan.notice.type"
    _description = "Notice Type"

    name = fields.Char(required=True)


# 🔹 Terms Template
class TermsTemplate(models.Model):
    _name = "loan.terms.template"
    _description = "Terms Template"

    name = fields.Char(required=True)
    content = fields.Html()


# =====================================================
# ✅ NEW MODELS (IMPORTANT FIX)
# =====================================================

# 🔹 Document Checklist Template (MAIN MODEL)
class DocumentChecklistTemplate(models.Model):
    _name = "loan.document.checklist.template"
    _description = "Document Checklist Template"

    name = fields.Char(required=True)

    line_ids = fields.One2many(
        "loan.document.checklist.line",
        "template_id",
        string="Required Documents"
    )


# 🔹 Checklist Lines (SUB MODEL)
class DocumentChecklistLine(models.Model):
    _name = "loan.document.checklist.line"
    _description = "Document Checklist Line"

    template_id = fields.Many2one(
        "loan.document.checklist.template",
        ondelete="cascade"
    )

    name = fields.Char(required=True)

    document_type_id = fields.Many2one(
        "loan.document.type",
        string="Document Type"
    )


# 🔹 Document Template
class DocumentTemplate(models.Model):
    _name = "loan.document.template"
    _description = "Document Template"

    template_id = fields.Many2one(
        "loan.document.checklist.template",
        string="Checklist Template",
        ondelete="cascade"
    )

    name = fields.Char("Name", required=True)

    document_type_id = fields.Many2one(
        "loan.document.type",
        string="Document Type"
    )


# 🔹 Required Document
class RequiredDocument(models.Model):
    _name = "loan.required.document"
    _description = "Required Document"

    name = fields.Char(required=True)
    mandatory = fields.Boolean()


# 🔹 Document Type
class DocumentType(models.Model):
    _name = "loan.document.type"
    _description = "Document Type"

    name = fields.Char(required=True)