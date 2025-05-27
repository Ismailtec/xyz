# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class VetBoardingStay(models.Model):
    _name = 'vet.boarding.stay'
    _description = 'Veterinary Boarding Stay'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in_datetime desc, name'

    name = fields.Char(
        string='Boarding Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    pet_id = fields.Many2one(
        'res.partner',
        string='Pet',
        required=True,
        index=True,
        domain="[('ths_partner_type_id', '=', 'ths_medical_vet.partner_type_pet')]",
        tracking=True,
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        # related='pet_id.ths_pet_owner_id', # Make it editable in case owner brings pet owned by someone else?
        compute='_compute_owner_id',  # Compute based on pet
        store=True,
        readonly=False,  # Allow override? Or make strictly related? Let's compute but allow override.
        domain="[('ths_partner_type_id', '=', 'ths_medical_vet.partner_type_pet_owner')]",
        tracking=True,
    )
    cage_id = fields.Many2one(
        'vet.boarding.cage',
        string='Assigned Cage',
        required=True,
        index=True,
        domain="[('state', '=', 'available')]",  # Only show available cages initially
        tracking=True,
    )
    check_in_datetime = fields.Datetime(
        string='Check-in',
        default=fields.Datetime.now,
        tracking=True,
    )
    expected_check_out_datetime = fields.Datetime(
        string='Expected Check-out',
        required=True,
        tracking=True,
    )
    actual_check_out_datetime = fields.Datetime(
        string='Actual Check-out',
        readonly=True,  # Set when checked out
        copy=False,
        tracking=True,
    )
    duration_days = fields.Integer(
        string="Duration (Days)",
        compute='_compute_duration_days',
        store=True,
        help="Calculated duration in days based on check-in and expected check-out.",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),  # Booked in advance
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),  # Stay complete, pending payment/finalization
        ('invoiced', 'Invoiced/Paid'),  # Optional final state
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', index=True, required=True, tracking=True, copy=False)

    # == Boarding Information ==
    vaccination_proof_received = fields.Boolean(string='Vaccination Proof Received?', tracking=True)
    medical_conditions = fields.Text(string='Medical Conditions / Allergies',
                                     help="Note any pre-existing conditions or allergies.")
    routines_preferences_quirks = fields.Text(string='Routines & Preferences',
                                              help="Describe feeding schedule, exercise routine, known anxieties, likes/dislikes.")

    owner_brought_food = fields.Boolean(string='Own Food Provided?', default=False)
    food_instructions = fields.Text(string='Feeding Instructions',
                                    help="Details on type, amount, frequency if own food provided.")

    owner_brought_medication = fields.Boolean(string='Own Medication Provided?', default=False)
    medication_instructions = fields.Text(string='Medication Instructions',
                                          help="Details on medication, dosage, timing, administration.")

    consent_form_signed = fields.Boolean(string='Consent Form Signed?', default=False, tracking=True)
    # consent_form_attachment_id = fields.Many2one('ir.attachment', string='Consent Form Scan') # Optional

    notes = fields.Text(string='Internal Boarding Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # TODO: Add relation to vet.boarding.log (One2many) later
    # TODO: Add relation to checklist lines (One2many) later
    # TODO: Add relation to billing (e.g., related product, link to pending items/invoice) later

    # --- Compute / Onchange ---
    @api.depends('pet_id')
    def _compute_owner_id(self):
        """ Default owner from pet """
        for stay in self:
            if stay.pet_id and stay.pet_id.ths_pet_owner_id:
                # Set only if owner is not already set or differs from pet's default owner
                if not stay.owner_id or stay.owner_id != stay.pet_id.ths_pet_owner_id:
                    stay.owner_id = stay.pet_id.ths_pet_owner_id
            # If pet is cleared, do we clear owner? Let's keep it simple for now.

    @api.depends('check_in_datetime', 'expected_check_out_datetime')
    def _compute_duration_days(self):
        """ Calculate stay duration. Needs careful handling of partial days. """
        for stay in self:
            if stay.check_in_datetime and stay.expected_check_out_datetime:
                # Simple difference in days, rounds down. Add 1 maybe? Depends on pricing policy.
                delta = stay.expected_check_out_datetime.date() - stay.check_in_datetime.date()
                stay.duration_days = delta.days + 1  # Example: Check-in Mon, Check-out Tue = 2 days charged?
            else:
                stay.duration_days = 0

    @api.constrains('check_in_datetime', 'expected_check_out_datetime')
    def _check_dates(self):
        for stay in self:
            if stay.check_in_datetime and stay.expected_check_out_datetime and \
                    stay.expected_check_out_datetime < stay.check_in_datetime:
                raise ValidationError(_("Expected Check-out date cannot be before Check-in date."))
            if stay.actual_check_out_datetime and stay.check_in_datetime and \
                    stay.actual_check_out_datetime < stay.check_in_datetime:
                raise ValidationError(_("Actual Check-out date cannot be before Check-in date."))

    @api.constrains('cage_id', 'state')
    def _check_cage_availability(self):
        """ Prevent assigning checked-in stays to occupied/maintenance cages """
        for stay in self:
            if stay.state == 'checked_in' and stay.cage_id and stay.cage_id.state != 'occupied':
                # This constraint is tricky because the cage state depends on the stay state.
                # Handled better via state change methods below.
                pass  # See check_in action

    # --- Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Assign sequence on creation """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('vet.boarding.stay') or _('New')
            # Update cage state if created directly as 'checked_in'
            if vals.get('state') == 'checked_in' and vals.get('cage_id'):
                cage = self.env['vet.boarding.cage'].browse(vals['cage_id'])
                if cage.state != 'available':
                    raise UserError(
                        _("Cannot create a checked-in stay for cage '%s' as it is currently '%s'.", cage.name,
                          cage.state))
                # Defer cage state update to write? Risky if create fails later. Best in action.
        stays = super(VetBoardingStay, self).create(vals_list)
        # Trigger cage update AFTER successful creation via write (or separate method)
        for stay in stays:
            if stay.state == 'checked_in':
                stay.cage_id.sudo().write({'state': 'occupied'})  # Use sudo if needed
        return stays

    def write(self, vals):
        """ Update cage state on state changes """
        # Store old states/cages if needed
        old_cage_map = {s.id: s.cage_id for s in self} if 'cage_id' in vals or 'state' in vals else {}
        old_state_map = {s.id: s.state for s in self} if 'state' in vals else {}

        res = super(VetBoardingStay, self).write(vals)

        # Handle state/cage changes
        for stay in self:
            new_state = vals.get('state', stay.state)
            new_cage_id_val = vals.get('cage_id')  # This is the ID or False
            old_cage = old_cage_map.get(stay.id)
            old_state = old_state_map.get(stay.id,
                                          stay.state if stay.id not in old_state_map else None)  # Get pre-write state

            # If state changes TO checked_in
            if new_state == 'checked_in' and old_state != 'checked_in':
                if not stay.cage_id:
                    raise UserError(_("Cannot check in stay '%s' without assigning a cage.", stay.name))
                if stay.cage_id.state != 'available':
                    # Check if it's occupied by THIS stay already (e.g., write called multiple times)
                    current_occupant = self.env['vet.boarding.stay'].search(
                        [('cage_id', '=', stay.cage_id.id), ('state', '=', 'checked_in')], limit=1)
                    if current_occupant and current_occupant != stay:
                        raise UserError(
                            _("Cannot check in to cage '%s'. It is already occupied by stay '%s'.", stay.cage_id.name,
                              current_occupant.name))
                    elif stay.cage_id.state == 'maintenance':
                        raise UserError(
                            _("Cannot check in to cage '%s' as it is under maintenance.", stay.cage_id.name))
                # Mark new cage as occupied
                stay.cage_id.sudo().write({'state': 'occupied'})
                # If cage was changed *during* this write and old cage exists, free old cage
                if old_cage and old_cage != stay.cage_id:
                    old_cage.sudo().write({'state': 'available'})

            # If state changes FROM checked_in (to checked_out or cancelled)
            elif old_state == 'checked_in' and new_state != 'checked_in':
                # Free up the cage associated with the stay BEFORE the write
                cage_to_free = old_cage_map.get(stay.id) or stay.cage_id
                if cage_to_free:
                    # Ensure no OTHER stay is currently checked into this cage before freeing it
                    other_occupants = self.env['vet.boarding.stay'].search_count([
                        ('cage_id', '=', cage_to_free.id),
                        ('state', '=', 'checked_in'),
                        ('id', '!=', stay.id)
                    ])
                    if other_occupants == 0:
                        cage_to_free.sudo().write({'state': 'available'})
                    else:
                        _logger.warning(
                            "Cage %s state not set to available after check-out/cancel of stay %s, as other occupants found.",
                            cage_to_free.name, stay.name)
                # Set actual check-out time if moving to checked_out
                if new_state == 'checked_out' and not stay.actual_check_out_datetime:
                    vals_checkout = {'actual_check_out_datetime': fields.Datetime.now()}
                    super(VetBoardingStay, stay).write(vals_checkout)  # Use super to avoid recursion

            # If cage is changed while stay is checked_in
            elif new_state == 'checked_in' and 'cage_id' in vals and old_cage != stay.cage_id:
                new_cage = stay.cage_id
                if not new_cage: raise UserError(_("Cannot move checked-in stay '%s' to an empty cage.", stay.name))
                if new_cage.state != 'available': raise UserError(
                    _("Cannot move stay '%s' to cage '%s' as it is currently '%s'.", stay.name, new_cage.name,
                      new_cage.state))
                # Occupy new cage
                new_cage.sudo().write({'state': 'occupied'})
                # Free old cage
                if old_cage: old_cage.sudo().write({'state': 'available'})

        return res

    # --- Actions ---
    def action_check_in(self):
        # Check permissions?
        for stay in self.filtered(lambda s: s.state in ('draft', 'scheduled')):
            stay.write({'state': 'checked_in'})  # Write handles cage logic

    def action_check_out(self):
        # Check permissions?
        # TODO: Check if billing is required/completed before check-out?
        for stay in self.filtered(lambda s: s.state == 'checked_in'):
            # Set actual check out time and state
            stay.write({
                'state': 'checked_out',
                'actual_check_out_datetime': fields.Datetime.now()  # Let write handle state change logic
            })
            # TODO: Trigger creation of pending billing items?
            # self._create_boarding_billing_items()

    def action_cancel(self):
        for stay in self.filtered(lambda s: s.state not in ('checked_out', 'invoiced', 'cancelled')):
            if stay.state == 'checked_in':
                # Need to free the cage
                if stay.cage_id: stay.cage_id.sudo().write({'state': 'available'})
            stay.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        # Use with caution - may require resetting cage states manually if inconsistent
        for stay in self.filtered(lambda s: s.state == 'cancelled'):
            stay.write({'state': 'draft'})

    # --- TODO: Billing Logic ---
    # def _create_boarding_billing_items(self):
    #    self.ensure_one()
    #    PendingItem = self.env['ths.pending.pos.item']
    #    # Find boarding product (e.g., daily rate) - needs configuration
    #    boarding_product = self.env.ref('some_module.product_boarding_daily', raise_if_not_found=False)
    #    if not boarding_product: return
    #    # Calculate qty (days)
    #    qty = self.duration_days # Or recalculate based on actual checkout?
    #    if qty <= 0 : return
    #
    #    item_vals = {
    #        'partner_id': self.owner_id.id,
    #        'patient_id': self.pet_id.id,
    #        'product_id': boarding_product.id,
    #        'qty': qty,
    #        'price_unit': boarding_product.lst_price, # Needs pricelist logic
    #        'practitioner_id': self.env.user.employee_id.id, # Who gets commission? Maybe specific staff?
    #        'state': 'pending',
    #        'company_id': self.company_id.id,
    #        # Add link back to stay?
    #        # 'boarding_stay_id': self.id, # Needs field on pending item
    #    }
    #    PendingItem.sudo().create(item_vals)
