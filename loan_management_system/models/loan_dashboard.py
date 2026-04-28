from datetime import timedelta

from odoo import api, fields, models


class LoanDashboard(models.TransientModel):
    _name = "loan.dashboard"
    _description = "Loan Dashboard"

    user_id = fields.Many2one("res.users", string="Users")
    borrower_id = fields.Many2one("res.partner", string="Borrower")
    loan_type_id = fields.Many2one("loan.type", string="Loan Type")
    date_range = fields.Selection(
        [
            ("lifetime", "Lifetime"),
            ("this_month", "This Month"),
            ("last_3_month", "Last 3 Months"),
            ("this_year", "This Year"),
        ],
        default="lifetime",
    )
    top_limit = fields.Integer(default=5)

    approved_amount = fields.Monetary(compute="_compute_metrics")
    disbursed_amount = fields.Monetary(compute="_compute_metrics")
    repayment_amount = fields.Monetary(compute="_compute_metrics")
    interest_amount = fields.Monetary(compute="_compute_metrics")
    lead_count = fields.Integer(compute="_compute_metrics")
    processing_fee_total = fields.Monetary(compute="_compute_metrics")
    closed_count = fields.Integer(compute="_compute_metrics")
    open_count = fields.Integer(compute="_compute_metrics")
    avg_interest_rate = fields.Float(compute="_compute_metrics")

    total_installment = fields.Integer(compute="_compute_installment_metrics")
    paid_installment = fields.Integer(compute="_compute_installment_metrics")
    unpaid_installment = fields.Integer(compute="_compute_installment_metrics")

    top_partner_ids = fields.Many2many("res.partner", compute="_compute_top_lists")
    top_installment_ids = fields.Many2many("loan.installment", compute="_compute_top_lists")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")

    def _loan_domain(self):
        self.ensure_one()
        domain = []
        if self.user_id:
            domain.append(("user_id", "=", self.user_id.id))
        if self.borrower_id:
            domain.append(("partner_id", "=", self.borrower_id.id))
        if self.loan_type_id:
            domain.append(("loan_type_id", "=", self.loan_type_id.id))

        today = fields.Date.today()
        if self.date_range == "this_month":
            domain.append(("application_date", ">=", today.replace(day=1)))
        elif self.date_range == "last_3_month":
            domain.append(("application_date", ">=", today - timedelta(days=90)))
        elif self.date_range == "this_year":
            domain.append(("application_date", ">=", today.replace(month=1, day=1)))
        return domain

    @api.depends("user_id", "borrower_id", "loan_type_id", "date_range")
    def _compute_metrics(self):
        lead_model = self.env["crm.lead"]
        for rec in self:
            domain = rec._loan_domain()
            loans = self.env["loan.loan"].search(domain)
            rec.approved_amount = sum(loans.filtered(lambda l: l.state in ("approved", "open", "closed")).mapped("principal_amount"))
            rec.disbursed_amount = sum(loans.mapped("disbursed_amount"))
            rec.repayment_amount = sum(loans.mapped("paid_amount"))
            rec.interest_amount = sum(loans.mapped("total_interest"))
            rec.processing_fee_total = sum(loans.mapped("processing_fee"))
            rec.closed_count = len(loans.filtered(lambda l: l.state == "closed"))
            rec.open_count = len(loans.filtered(lambda l: l.state == "open"))
            rec.avg_interest_rate = (sum(loans.mapped("interest_rate")) / len(loans)) if loans else 0.0
            rec.lead_count = lead_model.search_count([])

    @api.depends("user_id", "borrower_id", "loan_type_id", "date_range")
    def _compute_installment_metrics(self):
        for rec in self:
            loan_domain = rec._loan_domain()
            loans = self.env["loan.loan"].search(loan_domain)
            installments = self.env["loan.installment"].search([("loan_id", "in", loans.ids)])
            rec.total_installment = len(installments)
            rec.paid_installment = len(installments.filtered(lambda i: i.state == "paid"))
            rec.unpaid_installment = len(installments.filtered(lambda i: i.state != "paid"))

    @api.depends("user_id", "borrower_id", "loan_type_id", "date_range", "top_limit")
    def _compute_top_lists(self):
        for rec in self:
            loans = self.env["loan.loan"].search(rec._loan_domain())
            partner_group = self.env["loan.loan"].read_group(
                [("id", "in", loans.ids)],
                ["partner_id", "principal_amount:sum"],
                ["partner_id"],
                limit=max(rec.top_limit, 1),
                orderby="principal_amount desc",
            )
            partner_ids = [p["partner_id"][0] for p in partner_group if p.get("partner_id")]
            rec.top_partner_ids = [(6, 0, partner_ids)]

            installment_ids = self.env["loan.installment"].search(
                [("loan_id", "in", loans.ids)],
                limit=max(rec.top_limit, 1),
                order="amount_due desc",
            )
            rec.top_installment_ids = [(6, 0, installment_ids.ids)]

    def action_refresh(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "loan.dashboard",
            "view_mode": "form",
            "target": "current",
            "res_id": self.id,
        }

    def action_print_dashboard(self):
        self.ensure_one()
        return self.env.ref("loan_management_system.action_report_loan_dashboard").report_action(self)

    @api.model
    def get_dashboard_payload(self, filters=None, page=1, per_page=10):
        filters = filters or {}
        domain = []
        user_id = filters.get("user_id")
        borrower_id = filters.get("borrower_id")
        loan_type_id = filters.get("loan_type_id")
        date_range = filters.get("date_range", "lifetime")
        top_limit = int(filters.get("top_limit") or 5)

        if user_id:
            domain.append(("user_id", "=", user_id))
        if borrower_id:
            domain.append(("partner_id", "=", borrower_id))
        if loan_type_id:
            domain.append(("loan_type_id", "=", loan_type_id))

        today = fields.Date.today()
        if date_range == "this_month":
            domain.append(("application_date", ">=", today.replace(day=1)))
        elif date_range == "last_3_month":
            domain.append(("application_date", ">=", today - timedelta(days=90)))
        elif date_range == "this_year":
            domain.append(("application_date", ">=", today.replace(month=1, day=1)))

        loans = self.env["loan.loan"].search(domain)
        installments = self.env["loan.installment"].search([("loan_id", "in", loans.ids)])

        approved_amount = sum(loans.filtered(lambda l: l.state in ("approved", "open", "closed")).mapped("principal_amount"))
        disbursed_amount = sum(loans.mapped("disbursed_amount"))
        repayment_amount = sum(loans.mapped("paid_amount"))
        interest_amount = sum(loans.mapped("total_interest"))
        processing_fee_total = sum(loans.mapped("processing_fee"))
        closed_count = len(loans.filtered(lambda l: l.state == "closed"))
        open_count = len(loans.filtered(lambda l: l.state == "open"))
        avg_interest_rate = (sum(loans.mapped("interest_rate")) / len(loans)) if loans else 0.0

        # stage count
        stage_group = self.env["loan.loan"].read_group(domain, ["state"], ["state"])
        stage_counts = {g["state"]: g["state_count"] for g in stage_group if g.get("state")}

        # loan type volumes
        type_group = self.env["loan.loan"].read_group(domain, ["principal_amount:sum", "loan_type_id"], ["loan_type_id"])
        type_data = [
            {
                "name": g["loan_type_id"][1] if g.get("loan_type_id") else "Undefined",
                "amount": g.get("principal_amount", 0.0),
            }
            for g in type_group
        ]

        # monthly trend (3 month)
        month_points = []
        for i in range(2, -1, -1):
            start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
            amt = sum(self.env["loan.loan"].search(domain + [("application_date", ">=", start), ("application_date", "<", end)]).mapped("principal_amount"))
            month_points.append({"label": start.strftime("%b"), "amount": amt})

        partner_group = self.env["loan.loan"].read_group(
            [("id", "in", loans.ids)],
            ["partner_id", "principal_amount:sum"],
            ["partner_id"],
            limit=max(top_limit, 1),
            orderby="principal_amount desc",
        )
        top_partners = [
            {
                "name": p["partner_id"][1] if p.get("partner_id") else "Undefined",
                "amount": p.get("principal_amount", 0.0),
            }
            for p in partner_group
        ]

        all_top_installments = self.env["loan.installment"].search([("loan_id", "in", loans.ids)], order="amount_due desc")
        page = max(int(page or 1), 1)
        per_page = max(int(per_page or 10), 1)
        start = (page - 1) * per_page
        end = start + per_page
        top_installments = all_top_installments[start:end]
        installment_rows = [
            {
                "id": i.id,
                "name": f"INS-{i.loan_id.name}-{i.sequence}",
                "loan": i.loan_id.name,
                "borrower": i.loan_id.partner_id.name,
                "amount_due": i.amount_due,
                "due_date": str(i.due_date or ""),
                "state": i.state,
            }
            for i in top_installments
        ]

        return {
            "greeting": f"Good Afternoon, {self.env.user.name}.",
            "filters": {
                "users": self.env["res.users"].search_read([], ["name"], limit=200),
                "borrowers": self.env["res.partner"].search_read([("id", "in", loans.mapped("partner_id").ids or [0])], ["name"], limit=200),
                "loan_types": self.env["loan.type"].search_read([], ["name"], limit=200),
            },
            "kpis": {
                "approved_amount": approved_amount,
                "disbursed_amount": disbursed_amount,
                "repayment_amount": repayment_amount,
                "interest_amount": interest_amount,
                "lead_count": self.env["crm.lead"].search_count([]),
                "processing_fee_total": processing_fee_total,
                "closed_count": closed_count,
                "open_count": open_count,
                "avg_interest_rate": avg_interest_rate,
                "paid_installment": len(installments.filtered(lambda i: i.state == "paid")),
                "unpaid_installment": len(installments.filtered(lambda i: i.state != "paid")),
            },
            "stage_counts": stage_counts,
            "loan_type_volume": type_data,
            "monthly_trend": month_points,
            "top_partners": top_partners,
            "top_installments": installment_rows,
            "page": page,
            "has_prev": page > 1,
            "has_next": end < len(all_top_installments),
        }
