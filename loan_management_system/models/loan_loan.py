from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LoanLoan(models.Model):
    _name = "loan.loan"
    _description = "Loan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default="New", copy=False, readonly=True, tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Loan Officer", default=lambda self: self.env.user, tracking=True)
    lead_id = fields.Many2one("crm.lead", string="Source Enquiry", copy=False, tracking=True)

    loan_type_id = fields.Many2one("loan.type", required=True, tracking=True)
    loan_type = fields.Char(related="loan_type_id.code", string="Loan Code", store=True)
    purpose = fields.Text()

    application_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    approval_date = fields.Date(tracking=True)
    disbursement_date = fields.Date(tracking=True)
    first_due_date = fields.Date(required=True, tracking=True)
    foreclosure_date = fields.Date(tracking=True)

    principal_amount = fields.Monetary(required=True, tracking=True)
    interest_rate = fields.Float(help="Annual interest rate in percentage", tracking=True)
    term_months = fields.Integer(required=True, default=12, tracking=True)
    grace_period_months = fields.Integer(default=0)
    processing_fee = fields.Monetary(default=0.0)
    processing_fee_not_deducted_from_disbursal = fields.Boolean(
        string="Do Not Deduct Processing Fee From Disbursed Amount",
        default=True,
        help="If disabled, the processing fee is deducted from the displayed disbursed amount.",
    )
    penalty_rate = fields.Float(default=0.0, help="Monthly penalty rate for overdue installments")

    agreement_html = fields.Html()
    processing_fee_invoice_id = fields.Many2one("account.move", readonly=True, copy=False)
    has_processing_fee_invoice = fields.Boolean(compute="_compute_has_processing_fee_invoice")

    agreement_signed = fields.Boolean(default=False)
    agreement_signed_date = fields.Date()
    agreement_signed_by = fields.Char(readonly=True)
    agreement_signature = fields.Char(readonly=True)
    request_source = fields.Selection([("backend", "Backend"), ("website", "Website")], default="backend", readonly=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("disbursed", "Disbursed"),
            ("open", "Open"),
            ("closed", "Closed"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )

    installment_ids = fields.One2many("loan.installment", "loan_id", string="Installments", copy=False)
    payment_ids = fields.One2many("loan.payment", "loan_id", string="Payments", copy=False)
    disbursement_ids = fields.One2many("loan.disbursement", "loan_id", string="Disbursements", copy=False)

    installment_count = fields.Integer(compute="_compute_counts")
    payment_count = fields.Integer(compute="_compute_counts")
    disbursement_count = fields.Integer(compute="_compute_counts")

    total_interest = fields.Monetary(compute="_compute_totals", store=True)
    total_fees = fields.Monetary(compute="_compute_totals", store=True)
    total_amount = fields.Monetary(compute="_compute_totals", store=True)
    outstanding_amount = fields.Monetary(compute="_compute_totals", store=True)
    paid_amount = fields.Monetary(compute="_compute_totals", store=True)
    disbursed_amount = fields.Monetary(compute="_compute_totals", store=True)
    remaining_to_disburse = fields.Monetary(compute="_compute_totals", store=True)
    settlement_amount = fields.Monetary(readonly=True)

    next_due_date = fields.Date(compute="_compute_next_due", store=True)
    next_due_amount = fields.Monetary(compute="_compute_next_due", store=True)
    overdue_amount = fields.Monetary(compute="_compute_next_due", store=True)
    overdue_installment_count = fields.Integer(compute="_compute_next_due", store=True)

    notes = fields.Text()
    close_note = fields.Text(readonly=True)

    def _compute_has_processing_fee_invoice(self):
        for rec in self:
            rec.has_processing_fee_invoice = bool(rec.processing_fee_invoice_id)

    @api.onchange("loan_type_id")
    def _onchange_loan_type_id(self):
        for rec in self:
            if rec.loan_type_id:
                rec.interest_rate = rec.loan_type_id.default_interest_rate
                rec.term_months = rec.loan_type_id.default_term_months
                rec.processing_fee = (rec.principal_amount * rec.loan_type_id.processing_fee_percent) / 100 if rec.principal_amount else 0
                rec.agreement_html = rec.loan_type_id.agreement_template

    @api.depends("installment_ids", "payment_ids", "disbursement_ids")
    def _compute_counts(self):
        for rec in self:
            rec.installment_count = len(rec.installment_ids)
            rec.payment_count = len(rec.payment_ids)
            rec.disbursement_count = len(rec.disbursement_ids)

    @api.depends(
        "principal_amount",
        "processing_fee",
        "installment_ids.interest_amount",
        "installment_ids.fee_amount",
        "installment_ids.amount_due",
        "installment_ids.amount_paid",
        "disbursement_ids.amount",
        "disbursement_ids.state",
        "processing_fee_not_deducted_from_disbursal",
    )
    def _compute_totals(self):
        for rec in self:
            total_interest = sum(rec.installment_ids.mapped("interest_amount"))
            total_fees = rec.processing_fee + sum(rec.installment_ids.mapped("fee_amount"))
            total_due = sum(rec.installment_ids.mapped("amount_due")) + rec.processing_fee
            paid_amount = sum(rec.installment_ids.mapped("amount_paid"))
            posted_disbursements = rec.disbursement_ids.filtered(lambda d: d.state == "posted")
            gross_disbursed_amount = sum(posted_disbursements.mapped("amount"))
            disbursed_amount = gross_disbursed_amount
            if not rec.processing_fee_not_deducted_from_disbursal:
                disbursed_amount = max(gross_disbursed_amount - rec.processing_fee, 0.0)

            rec.total_interest = total_interest
            rec.total_fees = total_fees
            rec.total_amount = total_due if total_due else rec.principal_amount + total_interest + total_fees
            rec.paid_amount = paid_amount
            rec.outstanding_amount = rec.total_amount - paid_amount
            rec.disbursed_amount = disbursed_amount
            rec.remaining_to_disburse = rec.principal_amount - gross_disbursed_amount

    @api.depends("installment_ids.state", "installment_ids.due_date", "installment_ids.amount_due", "installment_ids.amount_paid")
    def _compute_next_due(self):
        today = fields.Date.today()
        for rec in self:
            upcoming = rec.installment_ids.filtered(lambda l: l.state != "paid").sorted(key=lambda l: l.due_date or fields.Date.today())
            overdue = rec.installment_ids.filtered(lambda l: l.state != "paid" and l.due_date and l.due_date < today)
            if upcoming:
                rec.next_due_date = upcoming[0].due_date
                rec.next_due_amount = upcoming[0].amount_due - upcoming[0].amount_paid
            else:
                rec.next_due_date = False
                rec.next_due_amount = 0.0
            rec.overdue_amount = sum(overdue.mapped(lambda l: max(l.amount_due - l.amount_paid, 0.0)))
            rec.overdue_installment_count = len(overdue)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("loan.loan") or "New"
            if vals.get("loan_type_id") and not vals.get("interest_rate"):
                loan_type = self.env["loan.type"].browse(vals["loan_type_id"])
                vals["interest_rate"] = loan_type.default_interest_rate
                vals["term_months"] = vals.get("term_months") or loan_type.default_term_months
                vals["agreement_html"] = vals.get("agreement_html") or loan_type.agreement_template
        return super().create(vals_list)

    @api.constrains("principal_amount", "interest_rate", "term_months", "processing_fee", "grace_period_months")
    def _check_financial_inputs(self):
        for rec in self:
            if rec.principal_amount <= 0:
                raise UserError(_("Principal amount must be greater than zero."))
            if rec.term_months <= 0:
                raise UserError(_("Term (months) must be greater than zero."))
            if rec.interest_rate < 0:
                raise UserError(_("Interest rate cannot be negative."))
            if rec.processing_fee < 0:
                raise UserError(_("Processing fee cannot be negative."))
            if rec.grace_period_months < 0:
                raise UserError(_("Grace period cannot be negative."))

    @api.constrains("application_date", "first_due_date")
    def _check_dates(self):
        for rec in self:
            if rec.application_date and rec.first_due_date and rec.first_due_date < rec.application_date:
                raise UserError(_("First due date cannot be before application date."))

    def _check_before_schedule_generation(self):
        for rec in self:
            if rec.term_months <= 0:
                raise UserError(_("Term (months) must be greater than zero."))
            if rec._get_schedule_base_amount() <= 0:
                raise UserError(_("Disbursed amount used for schedule generation must be greater than zero."))
            if not rec.first_due_date:
                raise UserError(_("Please set the first due date."))
            if rec.loan_type_id.min_amount and rec.principal_amount < rec.loan_type_id.min_amount:
                raise UserError(_("Amount is below minimum allowed for this loan type."))
            if rec.loan_type_id.max_amount and rec.principal_amount > rec.loan_type_id.max_amount:
                raise UserError(_("Amount exceeds maximum allowed for this loan type."))

    def _get_schedule_base_amount(self):
        self.ensure_one()
        if self.disbursed_amount > 0:
            return self.disbursed_amount
        if self.processing_fee_not_deducted_from_disbursal:
            return self.principal_amount
        return max(self.principal_amount - self.processing_fee, 0.0)

    def action_generate_schedule(self):
        self._check_before_schedule_generation()
        for rec in self:
            rec.installment_ids.unlink()
            rate = (rec.interest_rate / 100.0) / 12.0
            months = rec.term_months
            disbursed_base_amount = rec._get_schedule_base_amount()
            total_interest_amount = disbursed_base_amount * rate * months
            total_schedule_amount = disbursed_base_amount + total_interest_amount
            emi = total_schedule_amount / months
            monthly_interest = total_interest_amount / months if months else 0.0

            balance = disbursed_base_amount
            due_date = rec.first_due_date + relativedelta(months=rec.grace_period_months)
            for number in range(1, months + 1):
                interest_amount = monthly_interest
                principal_portion = emi - interest_amount
                if number == months:
                    principal_portion = balance
                    interest_amount = total_schedule_amount - (emi * (months - 1)) - principal_portion
                    emi = principal_portion + interest_amount
                ending_balance = balance - principal_portion
                self.env["loan.installment"].create(
                    {
                        "loan_id": rec.id,
                        "sequence": number,
                        "due_date": due_date,
                        "opening_balance": balance,
                        "principal_amount": principal_portion,
                        "interest_amount": interest_amount,
                        "fee_amount": 0.0,
                        "penalty_amount": 0.0,
                        "amount_due": emi,
                        "balance_amount": max(ending_balance, 0.0),
                    }
                )
                balance = ending_balance
                due_date = due_date + relativedelta(months=1)

                template = self.env.ref(
            "loan_management_system.email_template_loan_schedule_generated",
            raise_if_not_found=False
        )

        for rec in self:
            if template:
                template.send_mail(rec.id, force_send=True)



    def _notify_manager_loan_submitted(self):
        """
        Send the manager-notification email for every record in self.

        Extracted from action_submit so that external callers (e.g. the
        website portal controller) can trigger the same email without
        re-running the backend schedule-generation checks.

        Safe to call even when the template is missing or the loan officer
        has no email address – errors are caught and logged rather than
        propagated, so a missing SMTP configuration never blocks the
        customer's loan submission.
        """
        template = self.env.ref(
            "loan_management_system.email_template_loan_manager_notify",
            raise_if_not_found=False,
        )
        if not template:
            return

        for rec in self:
            if not rec.user_id.email:
                continue
            try:
                template.send_mail(rec.id, force_send=True)
            except Exception:
                # Log but do not crash – email failure must not roll back
                # the loan record that was already saved.
                _logger = __import__("logging").getLogger(__name__)
                _logger.exception(
                    "Loan manager notification email failed for loan %s", rec.name
                )

    def action_submit(self):
        self._check_before_schedule_generation()
        self.write({"state": "submitted"})
        self._notify_manager_loan_submitted()

    def action_approve(self):
        self.write({
            "state": "approved",
            "approval_date": fields.Date.context_today(self)
        })

        template = self.env.ref(
            "loan_management_system.email_template_loan_approved",
            raise_if_not_found=False
        )

        for rec in self:
            if template:
                template.send_mail(rec.id, force_send=True)

    def action_disburse(self):
        self.write({"state": "open", "disbursement_date": fields.Date.context_today(self)})

        template = self.env.ref(
            "loan_management_system.email_template_loan_disbursed",
            raise_if_not_found=False
        )

        for rec in self:
            if template:
                template.send_mail(rec.id, force_send=True)


    def action_open_loan(self):
        self.write({"state": "open"})

    def action_create_processing_fee_invoice(self):
        for rec in self:
            if rec.processing_fee <= 0:
                raise UserError(_("Processing fee must be greater than zero."))
            if rec.processing_fee_invoice_id:
                continue
            account = rec.loan_type_id.income_account_id
            if not account:
                raise UserError(_("Please configure Income Account on Loan Type."))
            invoice = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": rec.partner_id.id,
                    "invoice_date": fields.Date.context_today(self),
                    "invoice_origin": rec.name,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": _("Loan Processing Fee") + f" - {rec.name}",
                                "quantity": 1.0,
                                "price_unit": rec.processing_fee,
                                "account_id": account.id,
                            },
                        )
                    ],
                }
            )
            rec.processing_fee_invoice_id = invoice.id

    def action_view_processing_fee_invoice(self):
        self.ensure_one()
        if not self.processing_fee_invoice_id:
            return False
        return {
            "name": _("Processing Fee Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.processing_fee_invoice_id.id,
        }

    def action_open_disburse_wizard(self):
        self.ensure_one()
        return {
            "name": _("Register Disbursement"),
            "type": "ir.actions.act_window",
            "res_model": "loan.disburse.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_loan_id": self.id,
                "default_amount": self.remaining_to_disburse,
                "default_journal_id": self.loan_type_id.journal_id.id,
            },
        }

    def action_mark_agreement_signed(self):
        self.write({
            "agreement_signed": True,
            "agreement_signed_date": fields.Date.context_today(self),
            "agreement_signed_by": self.env.user.name,
        })

    def action_open_foreclosure_wizard(self):
        self.ensure_one()
        return {
            "name": _("Foreclosure"),
            "type": "ir.actions.act_window",
            "res_model": "loan.foreclose.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_loan_id": self.id,
                "default_settlement_amount": self.outstanding_amount,
            },
        }

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_close(self):
        for rec in self:
            if any(line.state != "paid" for line in rec.installment_ids):
                raise UserError(_("You can only close loans after all installments are paid."))
        self.write({"state": "closed"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    def action_advance_payment(self):
        self.ensure_one()
        return {
            "name": _("Advance Payment"),
            "type": "ir.actions.act_window",
            "res_model": "loan.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_loan_id": self.id,
                "default_payment_mode": "advance",
                "default_journal_id": self.loan_type_id.journal_id.id,
            },
        }

    def action_register_payment(self):
        self.ensure_one()
        return {
            "name": _("Register Payment"),
            "type": "ir.actions.act_window",
            "res_model": "loan.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_loan_id": self.id,
                "default_amount": self.next_due_amount or self.outstanding_amount,
                "default_journal_id": self.loan_type_id.journal_id.id,
            },
        }

    def action_view_installments(self):
        self.ensure_one()
        return {
            "name": _("Installments"),
            "type": "ir.actions.act_window",
            "res_model": "loan.installment",
            "view_mode": "list,form,pivot,graph",
            "domain": [("loan_id", "=", self.id)],
            "context": {"default_loan_id": self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            "name": _("Payments"),
            "type": "ir.actions.act_window",
            "res_model": "loan.payment",
            "view_mode": "list,form,pivot,graph",
            "domain": [("loan_id", "=", self.id)],
            "context": {"default_loan_id": self.id},
        }

    def action_view_disbursements(self):
        self.ensure_one()
        return {
            "name": _("Disbursements"),
            "type": "ir.actions.act_window",
            "res_model": "loan.disbursement",
            "view_mode": "list,form",
            "domain": [("loan_id", "=", self.id)],
            "context": {"default_loan_id": self.id},
        }
