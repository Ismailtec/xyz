# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
	_inherit = 'pos.order'

	# === BASE MEDICAL FIELDS ===

	# Many2many field to hold patients for this order
	patient_ids = fields.Many2many(
		'res.partner',
		'pos_order_patient_rel',
		'order_id',
		'patient_id',
		string='Patients',
		domain="[('ths_partner_type_id.is_patient', '=', True)]",
		help="Patients receiving services in this order"
	)

	# Practitioner and room fields for medical context
	practitioner_id = fields.Many2one(
		'appointment.resource',
		string='Service Provider',
		domain="[('ths_resource_category', '=', 'practitioner'), ('active', '=', True)]",
		# IMPROVED: Added active filter
		help="Medical practitioner providing services"
	)

	room_id = fields.Many2one(
		'appointment.resource',
		string='Treatment Room',
		domain="[('ths_resource_category', '=', 'location'), ('active', '=', True)]",  # IMPROVED: Added active filter
		help="Room where services are provided"
	)

	# Link to daily encounter
	encounter_id = fields.Many2one(
		'ths.medical.base.encounter',
		string='Daily Encounter',
		index=True,
		readonly=True,
		help="Daily encounter this order belongs to"
	)

	encounter_created_by_pos = fields.Boolean(
		string='Encounter Created by POS',
		default=False,
		help="Flag to track if this order created the encounter"
	)

	# Processed pending items tracking
	ths_processed_pending_item_ids = fields.Many2many(
		'ths.pending.pos.item',
		string='Processed Pending Items (Trace)',
		readonly=True,
		copy=False
	)

	# === BASE MEDICAL ENCOUNTER INTEGRATION ===

	# @api.model
	# def _order_fields(self, ui_order):
	# 	"""Include medical fields from the UI order"""
	# 	order_fields = super()._order_fields(ui_order)
	#
	# 	# Add medical fields if they exist in UI order
	# 	medical_fields = ['patient_ids', 'practitioner_id', 'room_id', 'encounter_id']
	# 	for field in medical_fields:
	# 		if field in ui_order:
	# 			order_fields[field] = ui_order[field]
	#
	# 	return order_fields

	@api.model
	def _process_order(self, order, draft, existing_order=None):  # FIXED: Added existing_order parameter
		"""
		Override to link pending items and handle encounter creation/population
		Enhanced with encounter management logic
		"""
		# === NEW: Encounter Creation and Population Logic ===
		partner_id = order.get('partner_id')
		encounter_id = None
		encounter_was_new = False

		if partner_id:
			# Use existing unified method from medical_encounter
			encounter = self.env['ths.medical.base.encounter']._find_or_create_daily_encounter(partner_id)
			encounter_id = encounter.id

			# Check if this encounter was newly created (for cleanup tracking)
			existing_orders_count = self.env['pos.order'].search_count([
				('encounter_id', '=', encounter.id),
				('state', 'in', ['paid', 'done', 'invoiced'])
			])
			encounter_was_new = existing_orders_count == 0

			# Add encounter_id to order data for processing
			order['encounter_id'] = encounter_id
			order['encounter_created_by_pos'] = encounter_was_new

		# === EXISTING: Original POS Order Processing ===
		ui_order_lines_data = {line[2]['uuid']: line[2] for line in order.get('lines', []) if
		                       len(line) > 2 and 'uuid' in line[2]}
		_logger.debug(f"UI Order Lines Data Keys (UUIDs): {list(ui_order_lines_data.keys())}")

		# Proper super() call with all parameters
		order_id = super()._process_order(order, draft, existing_order)
		_logger.info(f"Processing POS Order ID: {order_id} from UI Order: {order.get('name')}")

		pos_order = self.browse(order_id)
		if not pos_order:
			_logger.error(f"Failed to browse POS Order {order_id} after creation.")
			return order_id

		# === NEW: Populate Encounter Fields to Order Header ===
		if encounter_id:
			encounter = self.env['ths.medical.base.encounter'].browse(encounter_id)

			# Set encounter on order
			pos_order.encounter_id = encounter_id
			pos_order.encounter_created_by_pos = encounter_was_new

			# Populate encounter fields to order header if not already set
			if encounter.patient_ids:
				pos_order.patient_ids = [(6, 0, encounter.patient_ids.ids)]
			if encounter.practitioner_id:
				pos_order.practitioner_id = encounter.practitioner_id.id
			if encounter.room_id:
				pos_order.room_id = encounter.room_id.id

			_logger.info(f"Linked POS Order {pos_order.name} to encounter {encounter.name}")

		# === EXISTING: Medical Data Processing Logic ===
		lines_to_update_vals = {}
		pending_items_to_link = {}

		if not ui_order_lines_data and order.get('lines'):
			_logger.warning(
				f"POS Order {pos_order.name}: Could not extract UUID mapping from UI order lines. Cannot process medical data reliably for new order.")
		elif order.get('lines'):
			for line in pos_order.lines:
				line_uuid = line.uuid

				ui_line_data = ui_order_lines_data.get(line_uuid)
				if not ui_line_data:
					_logger.warning(
						f"POS Order {pos_order.name}, Line {line.id}: Could not find corresponding UI data using UUID '{line_uuid}'. Skipping medical data processing for this line.")
					continue

				line_extras = ui_line_data.get('extras', {})
				if not line_extras:
					_logger.debug(
						f"POS Order {pos_order.name}, Line {line.id}: No 'extras' found in UI data for UUID '{line_uuid}'.")
					continue

				_logger.info(
					f"POS Order {pos_order.name}, Line {line.id} (UUID {line_uuid}): Processing extras: {line_extras}")

				line_update_vals = {}
				pending_item_id = line_extras.get('ths_pending_item_id')
				patient_id = line_extras.get('ths_patient_id')
				provider_id = line_extras.get('ths_provider_id')
				commission_pct = line_extras.get('ths_commission_pct')

				if pending_item_id:
					line_update_vals['ths_pending_item_id'] = pending_item_id
					pending_items_to_link[pending_item_id] = {'line_id': line.id}

				if patient_id:
					line_update_vals['ths_patient_id'] = patient_id
				if provider_id:
					line_update_vals['ths_provider_id'] = provider_id
				if commission_pct is not None:
					line_update_vals['ths_commission_pct'] = commission_pct

				# Link line to encounter
				if pos_order.encounter_id:
					line_update_vals['encounter_id'] = pos_order.encounter_id.id

				if line_update_vals:
					lines_to_update_vals[line.id] = line_update_vals

		# === EXISTING: Batch Update Lines ===
		if lines_to_update_vals:
			_logger.info(
				f"POS Order {pos_order.name}: Batch updating {len(lines_to_update_vals)} lines with medical data.")
			PosOrderLine = self.env['pos.order.line']
			for line_id, vals in lines_to_update_vals.items():
				try:
					PosOrderLine.browse(line_id).sudo().write(vals)
				except Exception as e:
					_logger.error(f"Failed to write medical data to POS Order Line {line_id}: {e}")
					pos_order.note = (pos_order.note or '') + f"\nError updating line {line_id} medical data: {e}"

		# === EXISTING: Link Pending Items ===
		if pending_items_to_link:
			pending_item_ids = list(pending_items_to_link.keys())
			_logger.info(
				f"POS Order {pos_order.name}: Linking {len(pending_item_ids)} pending items: {pending_item_ids}")
			PendingItem = self.env['ths.pending.pos.item']
			pending_items = PendingItem.sudo().search([('id', 'in', pending_item_ids)])

			for item in pending_items:
				if item.state == 'pending':
					try:
						item.write({
							'pos_order_line_id': pending_items_to_link[item.id]['line_id'],
						})
						_logger.info(
							f"Linked pending item {item.id} to POS line {pending_items_to_link[item.id]['line_id']}")
					except Exception as e:
						_logger.error(f"Failed to link Pending Item {item.id} to POS Order {pos_order.name}: {e}")
						pos_order.note = (pos_order.note or '') + f"\nError linking pending item {item.id}: {e}"
				else:
					_logger.warning(
						f"Pending Item {item.id} state is '{item.state}', expected 'pending'. Skipping linking.")

		return order_id

	def unlink(self):
		"""Enhanced unlink with encounter cleanup safeguards"""
		encounters_to_check = []

		for order in self:
			if order.encounter_created_by_pos and order.encounter_id:
				encounters_to_check.append(order.encounter_id)

		result = super().unlink()

		# Check if encounters can be safely deleted (safeguard logic)
		for encounter in encounters_to_check:
			if encounter.exists() and self._can_safely_delete_encounter(encounter):
				encounter.unlink()
				_logger.info(f"Deleted empty encounter {encounter.id} created by discarded POS order")

		return result

	def _can_safely_delete_encounter(self, encounter):
		"""
		Safeguard: Check if encounter can be safely deleted
		Don't delete if it has any activities, services, or other orders
		"""
		# Check for other POS orders linked to this encounter
		other_orders = self.env['pos.order'].search([
			('encounter_id', '=', encounter.id),
			('id', 'not in', self.ids)
		])
		if other_orders:
			return False

		# Check for pending items
		pending_items = self.env['ths.pending.pos.item'].search([
			('encounter_id', '=', encounter.id)
		])
		if pending_items:
			return False

		# Check for appointments
		appointments = self.env['calendar.event'].search([
			('encounter_id', '=', encounter.id)
		])
		if appointments:
			return False

		# FIXED: Add defensive check for service_line_ids existence
		if hasattr(encounter, 'service_line_ids') and encounter.service_line_ids:
			return False

		# Check if encounter has clinical data (SOAP notes, etc.)
		if (encounter.chief_complaint or encounter.ths_subjective or
				encounter.ths_objective or encounter.ths_assessment or encounter.ths_plan):
			return False

		# Safe to delete - it's truly empty
		return True

	# === HELPER METHODS FOR SUBCLASSES ===

	def _get_encounter_domain(self, partner_id, encounter_date):
		"""Get domain for finding encounters - can be overridden by vet module"""
		return [
			('partner_id', '=', partner_id),
			('encounter_date', '=', encounter_date)
		]

	def _get_encounter_vals(self, partner_id, encounter_date):
		"""Get vals for creating encounters - can be overridden by vet module"""
		return {
			'partner_id': partner_id,
			'encounter_date': encounter_date,
			'state': 'in_progress',
			'patient_ids': [(6, 0, [partner_id])],  # In base medical, partner is the patient
		}

# TODO: Add encounter status synchronization with order states
# TODO: Add encounter analytics for POS integration
# TODO: Add encounter-based commission calculations