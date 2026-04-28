/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class LoanDashboardClientAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            page: 1,
            filters: { user_id: false, borrower_id: false, loan_type_id: false, date_range: "lifetime", top_limit: 5 },
            data: null,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData(page = 1) {
        this.state.loading = true;
        this.state.page = page;
        this.state.data = await this.orm.call("loan.dashboard", "get_dashboard_payload", [this.state.filters, page, 10]);
        this.state.loading = false;
    }

    async onFilterChange(ev, key) {
        const val = ev.target.value;
        this.state.filters[key] = val ? (Number.isNaN(parseInt(val)) ? val : parseInt(val)) : false;
        await this.loadData(1);
    }

    async prevPage() {
        if (this.state.data?.has_prev) {
            await this.loadData(this.state.page - 1);
        }
    }

    async nextPage() {
        if (this.state.data?.has_next) {
            await this.loadData(this.state.page + 1);
        }
    }

    async printDashboard() {
        await this.action.doAction("loan_management_system.action_report_loan_dashboard");
    }

    amount(value) {
        return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    monthlyWidth(amount) {
        const vals = (this.state.data?.monthly_trend || []).map((row) => Number(row.amount || 0));
        const max = Math.max(...vals, 1);
        return `width:${Math.round((Number(amount || 0) / max) * 100)}%`;
    }

    stageRows() {
        const entries = Object.entries(this.state.data?.stage_counts || {});
        return entries.map(([label, count]) => ({ label, count: Number(count || 0) }));
    }

    stageWidth(count) {
        const vals = this.stageRows().map((row) => row.count);
        const max = Math.max(...vals, 1);
        return `height:${Math.round((Number(count || 0) / max) * 100)}%`;
    }

    loanTypeStyle() {
        const rows = this.state.data?.loan_type_volume || [];
        const first = Number(rows[0]?.amount || 0);
        const second = Number(rows[1]?.amount || 0);
        const total = first + second;
        const ratio = total ? Math.round((first * 100) / total) : 0;
        return `background:conic-gradient(#51c99b 0 ${ratio}%, #eb6a67 ${ratio}% 100%)`;
    }

    paidUnpaidStyle() {
        const paid = Number(this.state.data?.kpis?.paid_installment || 0);
        const unpaid = Number(this.state.data?.kpis?.unpaid_installment || 0);
        const total = paid + unpaid;
        const ratio = total ? Math.round((paid * 100) / total) : 0;
        return `background:conic-gradient(#55cb9b 0 ${ratio}%, #ee6b67 ${ratio}% 100%)`;
    }

    upcomingInstallments() {
        const today = new Date();
        return (this.state.data?.top_installments || []).filter((item) => new Date(item.due_date) >= today);
    }

    overdueInstallments() {
        const today = new Date();
        return (this.state.data?.top_installments || []).filter((item) => new Date(item.due_date) < today);
    }
}

LoanDashboardClientAction.template = "loan_management_system.LoanDashboardClientAction";
registry.category("actions").add("loan_dashboard.client_action", LoanDashboardClientAction);
