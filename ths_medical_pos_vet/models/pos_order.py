# ths_medical_pos_vet/models/pos_order.py

from odoo import models, fields, api, _
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
		help="Pet owner responsible for billing in veterinary practice"
	)

	# === VET-SPECIFIC ENCOUNTER INTEGRATION ===

	@api.model
	def _process_order(self, order, existing_order):
		"""
		Override to add vet-specific logic
		"""
		order_id = super()._process_order(order, existing_order)
		pos_order = self.browse(order_id)

		if not pos_order:
			return order_id

		# VET: Set pet owner ID from partner_id (in vet context, partner_id = pet owner)
		if pos_order.partner_id and not pos_order.ths_pet_owner_id:
			# Verify partner is actually a pet owner
			if (pos_order.partner_id.ths_partner_type_id and
					pos_order.partner_id.ths_partner_type_id.name == 'Pet Owner'):
				pos_order.ths_pet_owner_id = pos_order.partner_id

		# VET: Sync encounter with vet-specific fields
		if pos_order.encounter_id:
			encounter_vals = {}

			# Set pet owner on encounter if not set
			if pos_order.ths_pet_owner_id and not pos_order.encounter_id.ths_pet_owner_id:
				encounter_vals['ths_pet_owner_id'] = pos_order.ths_pet_owner_id.id

			if encounter_vals:
				pos_order.encounter_id.write(encounter_vals)

		return order_id

	@api.onchange('partner_id')
	def _onchange_partner_sync_pet_owner(self):
		"""VET: When partner changes, sync pet owner if it's a pet owner"""
		if (self.partner_id and
				self.partner_id.ths_partner_type_id and
				self.partner_id.ths_partner_type_id.name == 'Pet Owner'):
			self.ths_pet_owner_id = self.partner_id

	@api.onchange('ths_pet_owner_id')
	def _onchange_pet_owner_sync_partner(self):
		"""VET: When pet owner changes, sync partner for billing"""
		if self.ths_pet_owner_id:
			self.partner_id = self.ths_pet_owner_id

	# === VET-SPECIFIC ENCOUNTER CREATION ===

	def _create_new_order_popup(self, partner_id):
		"""
		VET: Create popup for new order with pet/practitioner/room selection
		This should be called when a new order is created for a customer
		"""
		if not partner_id:
			return False

		partner = self.env['res.partner'].browse(partner_id)

		# Only show popup for pet owners
		if not (partner.ths_partner_type_id and partner.ths_partner_type_id.name == 'Pet Owner'):
			return False

		# Check for today's encounter
		today = fields.Date.context_today(self)
		existing_encounter = self.env['ths.medical.base.encounter'].search([
			('ths_pet_owner_id', '=', partner_id),
			('encounter_date', '=', today)
		], limit=1)

		popup_data = {
			'partner_id': partner_id,
			'partner_name': partner.name,
			'existing_encounter': existing_encounter.id if existing_encounter else False,
			'pets': partner.ths_pet_ids.read(['id', 'name', 'ths_species_id']),
			'practitioners': self.env['appointment.resource'].search([
				('ths_resource_category', '=', 'practitioner')
			]).read(['id', 'name']),
			'rooms': self.env['appointment.resource'].search([
				('ths_resource_category', '=', 'room')
			]).read(['id', 'name']),
		}

		if existing_encounter:
			# Pre-fill with encounter data
			popup_data.update({
				'selected_pets': existing_encounter.patient_ids.ids,
				'selected_practitioner': existing_encounter.practitioner_id.id if existing_encounter.practitioner_id else False,
				'selected_room': existing_encounter.room_id.id if existing_encounter.room_id else False,
			})

		return popup_data

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

			encounter = self.env['ths.medical.base.encounter'].create(encounter_vals)
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
				encounter.write(update_vals)

		# Link order to encounter
		self.encounter_id = encounter.id

		# Load pending items for this encounter
		pending_items = self.env['ths.pending.pos.item'].search([
			('encounter_id', '=', encounter.id),
			('state', '=', 'pending')
		])

		# Auto-populate pending items as order lines
		for item in pending_items:
			try:
				self._add_pending_item_to_order(item)
			except Exception as e:
				_logger.error(f"Failed to add pending item {item.id} to order: {e}")

		return encounter

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
			'ths_patient_id': pending_item.patient_id.id,
			'ths_provider_id': pending_item.practitioner_id.id,
			'ths_commission_pct': pending_item.commission_pct,
			'encounter_id': pending_item.encounter_id.id,
		}

		line = self.env['pos.order.line'].create(line_vals)

		# Link pending item to order line
		pending_item.write({
			'pos_order_line_id': line.id,
		})

		return line

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