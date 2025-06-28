# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
	_inherit = 'pos.order'

	# === VET-SPECIFIC FIELDS ===

	# Pet owner field for veterinary billing
	ths_pet_owner_id = fields.Many2one(
		'res.partner',
		string='Pet Owner',
		domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
		help="Pet owner responsible for billing"
	)

	# === VET-SPECIFIC ENCOUNTER INTEGRATION ===

	@api.model
	def _process_order(self, order, draft, existing_order):
		"""
		Override to add vet-specific logic after base processing
		"""
		# Handle vet-specific partner logic before encounter creation
		partner_id = order.get('partner_id')
		if partner_id:
			partner = self.env['res.partner'].browse(partner_id)

			# If partner is a pet, switch to owner for billing
			if partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
				order['partner_id'] = partner.ths_pet_owner_id.id
				order['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
				# Add the pet to patient_ids if not already there
				current_patients = order.get('patient_ids', [])
				if partner.id not in current_patients:
					order['patient_ids'] = current_patients + [partner.id]

		return super()._process_order(order, draft, existing_order)

	# === NEW ORDER POPUP WORKFLOW ===

	@api.model
	def _create_new_order_popup(self, partner_id):
		"""
		VET: Create popup data for new order with pet/practitioner/room selection
		Called from UI when a pet owner is selected for a new order
		"""
		if not partner_id:
			return False

		partner = self.env['res.partner'].browse(partner_id)
		if not partner.exists():
			return False

		# Only show popup for pet owners
		if not (partner.ths_partner_type_id and partner.ths_partner_type_id.name == 'Pet Owner'):
			_logger.info(f"Partner {partner.name} is not a Pet Owner, skipping popup")
			return False

		# Check for today's encounter
		today = fields.Date.context_today(self)
		existing_encounter = self.env['ths.medical.base.encounter'].search([
			('ths_pet_owner_id', '=', partner_id),
			('encounter_date', '=', today)
		], limit=1)

		# Get pets for this owner
		pets = partner.ths_pet_ids.read(['id', 'name', 'ths_species_id'])

		# Get available practitioners
		practitioners = self.env['appointment.resource'].search([
			('ths_resource_category', '=', 'practitioner'),
			('active', '=', True)
		]).read(['id', 'name'])

		# Get available rooms
		rooms = self.env['appointment.resource'].search([
			('ths_resource_category', '=', 'location'),
			('active', '=', True)
		]).read(['id', 'name'])

		popup_data = {
			'partner_id': partner_id,
			'partner_name': partner.name,
			'existing_encounter': existing_encounter.id if existing_encounter else False,
			'pets': pets,
			'practitioners': practitioners,
			'rooms': rooms,
		}

		if existing_encounter:
			# Pre-fill with encounter data
			popup_data.update({
				'selected_pets': existing_encounter.patient_ids.ids,
				'selected_practitioner': existing_encounter.practitioner_id.id if existing_encounter.practitioner_id else False,
				'selected_room': existing_encounter.room_id.id if existing_encounter.room_id else False,
			})

		_logger.info(
			f"Created popup data for pet owner {partner.name}: {len(pets)} pets, {len(practitioners)} practitioners, {len(rooms)} rooms")
		return popup_data

	@api.model
	def _process_new_order_popup_result(self, popup_result):
		"""
		VET: Process the result from the new order popup
		Create or update encounter and load pending items
		"""
		partner_id = popup_result.get('partner_id')
		selected_pets = popup_result.get('selected_pets', [])
		selected_practitioner = popup_result.get('selected_practitioner')
		selected_room = popup_result.get('selected_room')

		if not partner_id:
			_logger.error("No partner_id provided in popup result")
			return False

		partner = self.env['res.partner'].browse(partner_id)
		if not partner.exists():
			_logger.error(f"Partner {partner_id} does not exist")
			return False

		# Find or create today's encounter
		today = fields.Date.context_today(self)
		encounter = self.env['ths.medical.base.encounter'].search([
			('ths_pet_owner_id', '=', partner_id),
			('encounter_date', '=', today)
		], limit=1)

		if not encounter:
			# Create new encounter
			encounter_vals = {
				'partner_id': partner_id,
				'ths_pet_owner_id': partner_id,
				'encounter_date': today,
				'state': 'in_progress',
			}

			if selected_pets:
				encounter_vals['patient_ids'] = [(6, 0, selected_pets)]
			if selected_practitioner:
				encounter_vals['practitioner_id'] = selected_practitioner
			if selected_room:
				encounter_vals['room_id'] = selected_room

			try:
				encounter = self.env['ths.medical.base.encounter'].create(encounter_vals)
				_logger.info(f"Created new encounter {encounter.name} for pet owner {partner.name}")
			except Exception as e:
				_logger.error(f"Failed to create encounter for {partner.name}: {e}")
				raise UserError(_("Failed to create encounter: %s") % str(e))
		else:
			# Update existing encounter
			update_vals = {}
			if selected_pets:
				update_vals['patient_ids'] = [(6, 0, selected_pets)]
			if selected_practitioner:
				update_vals['practitioner_id'] = selected_practitioner
			if selected_room:
				update_vals['room_id'] = selected_room

			if update_vals:
				try:
					encounter.write(update_vals)
					_logger.info(f"Updated existing encounter {encounter.name} for pet owner {partner.name}")
				except Exception as e:
					_logger.error(f"Failed to update encounter {encounter.name}: {e}")
					raise UserError(_("Failed to update encounter: %s") % str(e))

		# Return encounter data for UI
		return {
			'id': encounter.id,
			'name': encounter.name,
			'encounter_date': encounter.encounter_date,
			'state': encounter.state,
			'partner_id': encounter.partner_id.id,
			'ths_pet_owner_id': encounter.ths_pet_owner_id.id,
			'patient_ids': encounter.patient_ids.ids,
			'practitioner_id': encounter.practitioner_id.id if encounter.practitioner_id else False,
			'room_id': encounter.room_id.id if encounter.room_id else False,
		}

	def _add_pending_item_to_order(self, pending_item):
		"""
		VET: Add a pending item to the current order as an order line
		"""
		if not pending_item.product_id:
			return False

		# Create order line from pending item
		line_vals = {
			'order_id': self.id,
			'product_id': pending_item.product_id.id,
			'qty': pending_item.qty,
			'price_unit': pending_item.price_unit,
			'discount': pending_item.discount,
			'ths_pending_item_id': pending_item.id,
			'ths_patient_id': pending_item.patient_id.id if pending_item.patient_id else False,
			'ths_provider_id': pending_item.practitioner_id.id if pending_item.practitioner_id else False,
			'ths_commission_pct': pending_item.commission_pct,
		}

		line = self.env['pos.order.line'].create(line_vals)

		# Link pending item to order line
		pending_item.write({
			'pos_order_line_id': line.id,
			'state': 'processed',
			'processed_date': fields.Datetime.now(),
			'processed_by': self.env.user.id,
		})

		_logger.info(f"Added pending item {pending_item.display_name} to order {self.name}")
		return line

	# def _find_or_create_daily_encounter_for_pos(self, partner_id, ui_order):
	# 	"""Override for vet-specific encounter creation"""
	# 	partner = self.env['res.partner'].browse(partner_id)
	#
	# 	# Ensure we're working with pet owner for encounter
	# 	if partner.ths_partner_type_id.name == 'Pet':
	# 		partner_id = partner.ths_pet_owner_id.id
	#
	# 	return super()._find_or_create_daily_encounter_for_pos(partner_id, ui_order)

	# === VET-SPECIFIC CONSTRAINTS ===

	@api.constrains('partner_id', 'ths_pet_owner_id')
	def _check_vet_billing_consistency(self):
		"""VET: Ensure billing consistency in veterinary orders"""
		for order in self:
			if order.ths_pet_owner_id and order.partner_id:
				if order.ths_pet_owner_id != order.partner_id:
					_logger.warning(
						f"VET Order {order.name}: Pet Owner ({order.ths_pet_owner_id.name}) "
						f"differs from billing partner ({order.partner_id.name})"
					)

	# === VET-SPECIFIC ONCHANGE METHODS ===

	@api.onchange('partner_id')
	def _onchange_partner_sync_pet_owner(self):
		"""VET: When partner changes, sync pet owner if it's a pet owner"""
		if self.partner_id:
			# If selected partner is a pet, get the owner
			if self.partner_id.ths_partner_type_id.name == 'Pet':
				self.ths_pet_owner_id = self.partner_id.ths_pet_owner_id
				self.patient_ids = [(6, 0, [self.partner_id.id])]  # Set the pet as patient
				# Update partner_id to be the owner (billing customer)
				self.partner_id = self.partner_id.ths_pet_owner_id
			elif self.partner_id.ths_partner_type_id.name == 'Pet Owner':
				self.ths_pet_owner_id = self.partner_id
			# Don't auto-set pets - let user choose via popup

	@api.onchange('ths_pet_owner_id')
	def _onchange_pet_owner_sync_partner(self):
		"""VET: When pet owner changes, sync partner for billing"""
		if self.ths_pet_owner_id:
			self.partner_id = self.ths_pet_owner_id

	# === VET-SPECIFIC ACTIONS ===

	def action_view_pet_medical_histories(self):
		"""View medical histories for all pets in this order"""
		self.ensure_one()
		pet_ids = self.lines.mapped('ths_patient_id').ids
		if not pet_ids:
			return {}

		return {
			'name': _('Pet Medical Histories'),
			'type': 'ir.actions.act_window',
			'res_model': 'ths.medical.base.encounter',
			'view_mode': 'list,form',
			'domain': [('patient_ids', 'in', pet_ids)],
			'context': {
				'search_default_groupby_patient': 1,
				'create': False,
			}
		}

	def action_view_pet_owner_orders(self):
		"""View all orders for the pet owner"""
		self.ensure_one()
		if not self.ths_pet_owner_id:
			return {}

		return {
			'name': _('Orders for %s') % self.ths_pet_owner_id.name,
			'type': 'ir.actions.act_window',
			'res_model': 'pos.order',
			'view_mode': 'list,form',
			'domain': [('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)],
			'context': {'create': False}
		}

# TODO: Add multi-pet order handling
# TODO: Add pet-specific service bundling
# TODO: Add breed-based service recommendations