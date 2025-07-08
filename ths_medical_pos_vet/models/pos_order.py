# -*- coding: utf-8 -*-
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
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

	# Override patient_ids to represent pets in veterinary context
	patient_ids = fields.Many2many(
		'res.partner',
		'pos_order_patient_rel',
		'order_id',
		'patient_id',
		string='Pets',  # Changed from 'Patients' to 'Pets'
		domain="[('ths_partner_type_id.name', '=', 'Pet')]",
		help="Pets receiving services in this order"
	)

	# === VET-SPECIFIC ENCOUNTER INTEGRATION ===

	def _get_encounter_domain(self, partner_id, encounter_date):
		"""  Vet override: Find encounters for pet owners, not pets  """
		# In vet context, partner_id should be the pet owner
		return [
			('ths_pet_owner_id', '=', partner_id),  # Look for pet owner encounters
			('encounter_date', '=', encounter_date)
		]

	def _get_encounter_vals(self, partner_id, encounter_date):
		"""  Vet override: Create encounters for pet owners with proper context  """
		# Get pet owner record
		pet_owner = self.env['res.partner'].browse(partner_id)

		# Base encounter values for vet context
		encounter_vals = {
			'partner_id': partner_id,  # Partner is the pet owner
			'ths_pet_owner_id': partner_id,  # Explicitly set pet owner
			'encounter_date': encounter_date,
			'state': 'in_progress',
			'patient_ids': [],  # Will be populated with selected pets
		}

		# Add default pets if owner has any
		if hasattr(pet_owner, 'ths_pet_ids') and pet_owner.ths_pet_ids:
			encounter_vals['patient_ids'] = [(6, 0, pet_owner.ths_pet_ids.ids)]

		return encounter_vals

	@api.model
	def _process_order(self, order, draft, existing_order=None):
		"""  Override to add vet-specific logic after base processing  """
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

		return super()._process_order(order, draft, existing_order=None)

	# === NEW ORDER POPUP WORKFLOW ===

	@api.model
	def _create_new_order_popup(self, partner_id):
		"""  Create popup data for new vet order setup Called from partner_list_screen.js when pet owner selected  """
		try:
			partner = self.env['res.partner'].browse(partner_id)
			if not partner.exists():
				raise UserError(_("Partner not found"))

			# Verify this is a pet owner
			if not (partner.ths_partner_type_id and partner.ths_partner_type_id.name == 'Pet Owner'):
				return False  # Not a pet owner, use standard flow

			# Check for existing encounter today
			today = date.today()
			existing_encounter = self.env['ths.medical.base.encounter'].search([
				('ths_pet_owner_id', '=', partner_id),
				('encounter_date', '=', today)
			], limit=1)

			# Get pet owner's pets
			pets = self.env['res.partner'].search([
				('ths_pet_owner_id', '=', partner_id),
				('ths_partner_type_id.name', '=', 'Pet'),
				('active', '=', True),
				('ths_deceased', '=', False)
			])

			# Get available practitioners
			practitioners = self.env['appointment.resource'].search([
				('ths_resource_category', '=', 'practitioner'),
				('active', '=', True)
			])

			# Get available rooms
			rooms = self.env['appointment.resource'].search([
				('ths_resource_category', '=', 'location'),
				('active', '=', True)
			])

			# Format pets with species information
			pets_data = []
			for pet in pets:
				pet_data = {
					'id': pet.id,
					'name': pet.name,
					'ths_species_id': pet.ths_species_id.id if pet.ths_species_id else False,
				}
				pets_data.append(pet_data)

			# Format practitioners
			practitioners_data = [{'id': p.id, 'name': p.name} for p in practitioners]

			# Format rooms
			rooms_data = [{'id': r.id, 'name': r.name} for r in rooms]

			# Pre-select pets from existing encounter
			selected_pets = []
			selected_practitioner = False
			selected_room = False

			if existing_encounter:
				selected_pets = existing_encounter.patient_ids.ids
				selected_practitioner = existing_encounter.practitioner_id.id if existing_encounter.practitioner_id else False
				selected_room = existing_encounter.room_id.id if existing_encounter.room_id else False

			return {
				'partner_id': partner_id,
				'partner_name': partner.name,
				'existing_encounter': existing_encounter.id if existing_encounter else False,
				'pets': pets_data,
				'practitioners': practitioners_data,
				'rooms': rooms_data,
				'selected_pets': selected_pets,
				'selected_practitioner': selected_practitioner,
				'selected_room': selected_room,
			}

		except Exception as e:
			_logger.error(f"Error creating new order popup data: {e}")
			raise UserError(_("Error setting up order: %s") % str(e))

	@api.model
	def _process_new_order_popup_result(self, popup_data):
		""" Process the result from PetOrderSetupPopup
			Creates/updates encounter with selected pets, practitioner, room  """
		try:
			partner_id = popup_data.get('partner_id')
			selected_pets = popup_data.get('selected_pets', [])
			selected_practitioner = popup_data.get('selected_practitioner')
			selected_room = popup_data.get('selected_room')

			if not partner_id:
				raise UserError(_("Partner ID is required"))

			# Find or create today's encounter
			today = date.today()
			encounter = self.env['ths.medical.base.encounter'].search([
				('ths_pet_owner_id', '=', partner_id),
				('encounter_date', '=', today)
			], limit=1)

			encounter_vals = {
				'patient_ids': [(6, 0, selected_pets)] if selected_pets else [(5,)],
				'practitioner_id': selected_practitioner if selected_practitioner else False,
				'room_id': selected_room if selected_room else False,
				'state': 'in_progress',
			}

			if encounter:
				# Update existing encounter
				encounter.write(encounter_vals)
				_logger.info(f"Updated encounter {encounter.id} with popup selections")
			else:
				# Create new encounter
				encounter_vals.update({
					'partner_id': partner_id,
					'ths_pet_owner_id': partner_id,
					'encounter_date': today,
					'name': f"Encounter - {self.env['res.partner'].browse(partner_id).name} - {today}",
				})
				encounter = self.env['ths.medical.base.encounter'].create(encounter_vals)
				_logger.info(f"Created new encounter {encounter.id} from popup selections")

			# Process any existing park check-ins for selected pets
			if selected_pets:
				self._process_pet_park_checkins(selected_pets, encounter)

			return {
				'encounter_id': encounter.id,
				'encounter_name': encounter.name,
				'patient_ids': [(pet.id, pet.name) for pet in encounter.patient_ids],
				'practitioner_id': [encounter.practitioner_id.id,
									encounter.practitioner_id.name] if encounter.practitioner_id else False,
				'room_id': [encounter.room_id.id, encounter.room_id.name] if encounter.room_id else False,
				'success': True,
			}

		except Exception as e:
			_logger.error(f"Error processing new order popup result: {e}")
			raise UserError(_("Error processing order setup: %s") % str(e))

	def _process_pet_park_checkins(self, pet_ids, encounter):
		"""  Process park check-ins for selected pets and Link any active park sessions to the encounter  """
		try:
			# Find active park check-ins for these pets
			park_checkins = self.env['park.checkin'].search([
				('patient_ids', 'in', pet_ids),
				('state', '=', 'checked_in'),
				('encounter_id', '=', False)  # Not yet linked to encounter
			])

			if park_checkins:
				# Link park check-ins to encounter
				park_checkins.write({'encounter_id': encounter.id})
				_logger.info(f"Linked {len(park_checkins)} park check-ins to encounter {encounter.id}")

		except Exception as e:
			_logger.error(f"Error processing pet park check-ins: {e}")

	# def _add_pending_item_to_order(self, pending_item):
	# 	"""   VET: Add a pending item to the current order as an order line  """
	# 	if not pending_item.product_id:
	# 		return False
	#
	# 	# Create order line from pending item
	# 	line_vals = {
	# 		'order_id': self.id,
	# 		'product_id': pending_item.product_id.id,
	# 		'qty': pending_item.qty,
	# 		'price_unit': pending_item.price_unit,
	# 		'discount': pending_item.discount,
	# 		'ths_pending_item_id': pending_item.id,
	# 		'ths_patient_id': pending_item.patient_id.id if pending_item.patient_id else False,
	# 		'ths_provider_id': pending_item.practitioner_id.id if pending_item.practitioner_id else False,
	# 		'ths_commission_pct': pending_item.commission_pct,
	# 	}
	#
	# 	line = self.env['pos.order.line'].create(line_vals)
	#
	# 	# Link pending item to order line
	# 	pending_item.write({
	# 		'pos_order_line_id': line.id,
	# 		'state': 'processed',
	# 		'processed_date': fields.Datetime.now(),
	# 		'processed_by': self.env.user.id,
	# 	})
	#
	# 	_logger.info(f"Added pending item {pending_item.display_name} to order {self.name}")
	# 	return line

	# === HELPER METHODS ===

	def _get_pet_membership_status(self, pet_id):
		"""Get membership status for a pet"""
		try:
			membership = self.env['vet.pet.membership'].search([
				('patient_ids', 'in', [pet_id]),
				('state', '=', 'running'),
				('is_paid', '=', True)
			], limit=1)

			return 'active' if membership else 'inactive'

		except Exception as e:
			_logger.error(f"Error checking pet membership status: {e}")
			return 'unknown'

	def _validate_pet_owner_relationship(self):
		"""Validate that pets belong to the designated owner"""
		for order in self:
			if order.ths_pet_owner_id and order.patient_ids:
				for pet in order.patient_ids:
					if pet.ths_pet_owner_id != order.ths_pet_owner_id:
						raise ValidationError(
							_("Pet '%s' does not belong to owner '%s'") %
							(pet.name, order.ths_pet_owner_id.name)
						)

	@api.constrains('ths_pet_owner_id', 'patient_ids')
	def _check_pet_owner_consistency(self):
		"""Ensure pets belong to their designated owner"""
		self._validate_pet_owner_relationship()

	# === REPORTING METHODS ===

	def get_vet_order_summary(self):
		"""Get veterinary-specific order summary"""
		self.ensure_one()

		summary = {
			'pet_owner': self.ths_pet_owner_id.name if self.ths_pet_owner_id else None,
			'pets': [(p.id, p.name, p.ths_species_id.name if p.ths_species_id else None) for p in self.patient_ids],
			'practitioner': self.practitioner_id.name if self.practitioner_id else None,
			'room': self.room_id.name if self.room_id else None,
			'encounter': self.encounter_id.name if self.encounter_id else None,
		}

		return summary

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
# TODO: Add pet membership discount integration
# TODO: Add park check-in billing integration
# TODO: Add pet medical history integration
# TODO: Add multi-pet service bundling logic