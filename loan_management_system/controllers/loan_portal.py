from datetime import date

from odoo import http
from odoo.http import request


class LoanPortalController(http.Controller):
    @http.route('/my/loans', type='http', auth='user', website=True)
    def my_loans(self, **kwargs):
        partner = request.env.user.partner_id
        loans = request.env['loan.loan'].sudo().search([('partner_id', '=', partner.id)], order='id desc')
        return request.render('loan_management_system.portal_my_loans', {'loans': loans})

    @http.route('/my/loans/<int:loan_id>', type='http', auth='user', website=True)
    def my_loan_detail(self, loan_id, **kwargs):
        partner = request.env.user.partner_id
        loan = request.env['loan.loan'].sudo().browse(loan_id)
        if not loan.exists() or loan.partner_id.id != partner.id:
            return request.not_found()
        return request.render('loan_management_system.portal_loan_detail', {'loan': loan})

    @http.route('/my/loans/<int:loan_id>/sign', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def my_loan_sign(self, loan_id, **post):
        partner = request.env.user.partner_id
        loan = request.env['loan.loan'].sudo().browse(loan_id)
        if loan.exists() and loan.partner_id.id == partner.id:
            signer_name = post.get('signer_name') or partner.name
            loan.write({
                'agreement_signed': True,
                'agreement_signed_date': date.today(),
                'agreement_signed_by': signer_name,
                'agreement_signature': post.get('signature_data') or False,
            })
        return request.redirect(f'/my/loans/{loan_id}')

    @http.route('/loans/apply', type='http', auth='public', website=True)
    def loan_apply(self, **kwargs):
        loan_types = request.env['loan.type'].sudo().search([('active', '=', True)])
        return request.render('loan_management_system.portal_loan_apply', {'loan_types': loan_types})

    @http.route('/loans/apply/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def loan_apply_submit(self, **post):
        loan_type_id = int(post.get('loan_type_id')) if post.get('loan_type_id') else False
        principal = float(post.get('principal_amount') or 0.0)
        term = int(post.get('term_months') or 12)
        partner = request.env.user.partner_id if request.env.user and not request.env.user._is_public() else False

        lead_vals = {
            'name': post.get('full_name') or post.get('purpose') or "Website Loan Enquiry",
            'contact_name': post.get('full_name'),
            'email_from': post.get('email'),
            'phone': post.get('phone'),
            'description': post.get('purpose'),
            'loan_type_id': loan_type_id,
            'loan_amount': principal,
            'loan_term_months': term,
            'partner_id': partner.id if partner else False,
            'type': 'lead',
        }
        lead = request.env['crm.lead'].sudo().create(lead_vals)

        if partner:
            first_due_date = post.get('first_due_date') or date.today().isoformat()
            request.env['loan.loan'].sudo().create({
                'partner_id': partner.id,
                'loan_type_id': loan_type_id,
                'principal_amount': principal,
                'term_months': term,
                'first_due_date': first_due_date,
                'purpose': post.get('purpose'),
                'request_source': 'website',
                'state': 'submitted',
                'lead_id': lead.id,
            })

        return request.redirect('/loans/apply/thank-you')

    @http.route('/loans/apply/thank-you', type='http', auth='public', website=True)
    def loan_apply_thank_you(self, **kwargs):
        return request.render('loan_management_system.portal_loan_apply_thank_you')