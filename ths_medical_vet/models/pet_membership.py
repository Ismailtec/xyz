# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VetPetMembership(models.Model):
	_name = 'vet.pet.membership'
	_description = 'Pet Membership Management'
	_inherit = ['mail.thread', 'mail.activity.mixin']
	_order = 'valid_from desc, name desc'

	name = fields.Char(string='Membership Code', required=True, copy=False, readonly=True,
	                   default=lambda self: _('New'))

	partner_id = fields.Many2one(
		'res.partner',
		context={'is_pet': False},
		string='Pet Owner',
		required=True,
		domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
		tracking=True
	)

	patient_ids = fields.Many2many(
		'res.partner',
		'vet_membership_pet_rel',
		'membership_id',
		'pet_id',
		context={'is_pet': True},
		string='Pets',
		store=True,
		domain="[('ths_partner_type_id.name', '=', 'Pet'), ('ths_pet_owner_id', '=', partner_id)]",
		tracking=True
	)

	membership_service_id = fields.Many2one(
		'product.product',
		string='Membership Service',
		# domain=[('ths_product_sub_type_id', '=', 'Membership')],
		required=True,
		tracking=True
	)

	# membership_service_domain = fields.Char(
	# 	compute='_compute_membership_service_domain',
	# 	store=False
	# )

	valid_from = fields.Date(string='Valid From', required=True, default=fields.Date.today, tracking=True)
	valid_to = fields.Date(string='Valid To', readonly=True, compute='_compute_valid_to', store=True)

	state = fields.Selection([
		('draft', 'Draft'),
		('running', 'Running'),
		('expired', 'Expired')
	], string='Status', default='draft', required=True, tracking=True)

	is_paid = fields.Boolean(string='Paid', default=False, tracking=True)
	notes = fields.Text(string='Notes')

	patient_ids_domain = fields.Char(compute='_compute_patient_domain', store=False)

	@api.depends('partner_id')
	def _compute_patient_domain(self):
		for rec in self:
			if rec.partner_id:
				rec.patient_ids_domain = str([
					('ths_pet_owner_id', '=', rec.partner_id.id),
					('ths_partner_type_id.name', '=', 'Pet')
				])
			else:
				rec.patient_ids_domain = str([('ths_partner_type_id.name', '=', 'Pet')])

	# @api.depends()
	# def _compute_membership_service_domain(self):
	# 	member_subtype = self.env.ref('ths_medical_vet.product_sub_type_member', raise_if_not_found=False)
	# 	domain = [('ths_product_sub_type_id', '=', member_subtype)] if member_subtype else [('id', '=', False)]
	# 	for rec in self:
	# 		rec.membership_service_domain = domain


	@api.depends('valid_from', 'membership_service_id.ths_membership_duration')
	def _compute_valid_to(self):
		for membership in self:
			if membership.valid_from and membership.membership_service_id.ths_membership_duration:
				membership.valid_to = membership.valid_from + relativedelta(
					months=membership.membership_service_id.ths_membership_duration
				)
			else:
				membership.valid_to = False

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('name', _('New')) == _('New'):
				vals['name'] = self.env['ir.sequence'].sudo().next_by_code('vet.pet.membership') or _('New')
		return super().create(vals_list)

	def unlink(self):
		for record in self:
			if record.state != 'draft':
				raise UserError(_("You can only delete memberships in draft state."))
		return super().unlink()

	def action_start_membership(self):
		"""Start the membership"""
		self.write({'state': 'running'})

	def action_reset_to_draft(self):
		"""Reset to draft"""
		self.write({'state': 'draft'})

	@api.model
	def check_pet_membership_validity(self, pet_ids):
		"""Helper method to check if pets have valid membership"""
		today = fields.Date.today()
		valid_memberships = self.search([
			('patient_ids', 'in', pet_ids),
			('state', '=', 'running'),
			('is_paid', '=', True),
			('valid_from', '<=', today),
			('valid_to', '>=', today)
		])
		return len(valid_memberships) > 0

# TODO: Add automatic expiration cron job
# TODO: Add membership renewal functionality
# TODO: Add integration with billing/invoicing