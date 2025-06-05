# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalEncounter(models.Model):
    """ Represents a single clinical encounter/visit. """
    _name = 'ths.medical.base.encounter'
    _description = 'Medical Encounter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, name desc'

    name = fields.Char(
        string='Encounter ID',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    appointment_id = fields.Many2one(
        'calendar.event',
        string='Appointment',
        ondelete='set null',
        index=True,
        copy=False
    )
    daily_id = fields.Many2one(
        'ths.daily.encounter',
        string='Daily Record',
        compute='_compute_daily_id',
        store=True,
        readonly=True,
        copy=False,
        index=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer/Owner',
        related='appointment_id.partner_id',
        store=True, index=True, readonly=True
    )
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        # Ensure this gets populated correctly, e.g., from appointment or manually
        store=True, index=True, readonly=True,  # Consider if readonly is always appropriate
        help="The patient (human or animal) receiving treatment."
    )
    patient_ref = fields.Char(string="Patient File", related='patient_id.ref', store=False, readonly=True)
    patient_mobile = fields.Char(string="Patient Mobile", related='patient_id.mobile', store=False, readonly=True)

    practitioner_id = fields.Many2one(
        'hr.employee', string='Practitioner',
        related='appointment_id.ths_practitioner_id',  # Primary link via appointment
        store=True, index=True, readonly=True  # Consider if readonly is always appropriate
    )
    date_start = fields.Datetime(
        string='Start Time',
        related='appointment_id.start',
        store=True, readonly=True
    )
    date_end = fields.Datetime(
        string='End Time',
        related='appointment_id.stop',
        store=True, readonly=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('ready_for_billing', 'Ready For Billing'),
        ('billed', 'Billed'),  # State indicating POS processing completed
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', index=True, tracking=True, copy=False)

    # Lines representing services/items used in the encounter
    # REPLACE encounter_line_ids with service_line_ids
    service_line_ids = fields.One2many(
        'ths.medical.encounter.service',
        'encounter_id',
        string='Services & Products Used',
        copy=True  # Allow copying lines if encounter is duplicated
    )

    # company_id = fields.Many2one(
    #     'res.company', string='Company',
    #     compute='_compute_company_id',
    #     store=True, index=True, readonly=True)
    notes = fields.Text(string="Internal Notes")  # Keep internal notes field

    # === EMR Fields (Base Text Fields) ===
    chief_complaint = fields.Text(string="Chief Complaint")
    history_illness = fields.Text(string="History of Present Illness")
    vitals = fields.Text(string="Vital Signs",
                         help="Record key vitals like Temp, HR, RR, BP etc.")

    # === SOAP Fields ===
    ths_subjective = fields.Text(string="Subjective", help="Patient's reported symptoms and history.")
    ths_objective = fields.Text(string="Objective", help="Practitioner's observations, exam findings, vitals.")
    ths_assessment = fields.Text(string="Assessment", help="Diagnosis or differential diagnosis.")
    ths_plan = fields.Text(string="Plan", help="Treatment plan, tests ordered, prescriptions, follow-up.")

    # === Other Clinical Details (as Text) ===
    ths_diagnosis_text = fields.Text(string="Diagnoses Summary", help="Summary of diagnoses made during encounter.")
    ths_procedures_text = fields.Text(string="Procedures Summary", help="Summary of procedures performed.")
    ths_prescriptions_text = fields.Text(string="Prescriptions Summary", help="Summary of medications prescribed.")
    ths_lab_orders_text = fields.Text(string="Lab Orders Summary", help="Summary of laboratory tests ordered.")
    ths_radiology_orders_text = fields.Text(string="Radiology Orders Summary",
                                            help="Summary of radiology exams ordered.")


    # @api.depends('practitioner_id.company_id', 'appointment_id.user_id.company_id')
    # def _compute_company_id(self):
    #     """Compute company primarily from the practitioner, fallback to appointment user or env company."""
    #     for encounter in self:
    #         if encounter.practitioner_id and encounter.practitioner_id.company_id:
    #             encounter.company_id = encounter.practitioner_id.company_id
    #         elif encounter.appointment_id and encounter.appointment_id.user_id:
    #             # Fallback to appointment creator's company if no practitioner company
    #             encounter.company_id = encounter.appointment_id.user_id.company_id
    #         else:
    #             # Final fallback to current environment company
    #             encounter.company_id = self.env.company

    # --- Compute Methods ---
    @api.depends('appointment_id', 'appointment_id.partner_id')
    def _compute_partner_patient_practitioner(self):
        """Compute partner, patient, and practitioner from the appointment."""
        for encounter in self:
            appointment = encounter.appointment_id
            # Get Partner (Customer/Owner) directly from appointment
            encounter.partner_id = appointment.partner_id if appointment else False
            # Get Patient from custom field on appointment (ensure field name is correct)
            # Use hasattr for safety if ths_patient_id might not always exist (e.g. different modules)
            encounter.patient_id = appointment.ths_patient_id if appointment and hasattr(appointment,
                                                                                         'ths_patient_id') else False
            # Get Practitioner from custom field on appointment (ensure field name is correct)
            encounter.practitioner_id = appointment.ths_practitioner_id if appointment and hasattr(appointment,
                                                                                                   'ths_practitioner_id') else False

    @api.depends('date_start')
    def _compute_daily_id(self):
        """ Find or create the daily encounter record for the encounter's date. """
        DailyEncounter = self.env['ths.daily.encounter']
        for encounter in self:
            target_date = fields.Date.context_today(encounter, timestamp=encounter.date_start)

            if not target_date:
                encounter.daily_id = False
                continue

            # Fallback to env.company since company_id was removed
            company = self.env.company
            daily_rec = DailyEncounter.sudo().search([
                ('date', '=', target_date),
                #('company_id', '=', company.id)
            ], limit=1)

            if not daily_rec:
                try:
                    daily_rec = DailyEncounter.sudo().create([{
                        'date': target_date,
                        #'company_id': company.id
                    }])
                    _logger.info(f"Created Daily Encounter record for date {target_date}")
                except Exception as e:
                    _logger.error(f"Failed to create Daily Encounter record for date {target_date}: {e}")
                    encounter.daily_id = False
                    continue

            encounter.daily_id = daily_rec.id

    # --- Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Assign sequence on creation. """
        # (Keep existing logic as provided previously)
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('medical.encounter') or _('New')
        return super(ThsMedicalEncounter, self).create(vals_list)

    # --- Actions ---
    def action_ready_for_billing(self):
        """ Mark encounter as ready for billing and create pending POS items from service lines. """
        PendingItem = self.env['ths.pending.pos.item']
        items_created_count = 0
        encounters_to_process = self.filtered(lambda enc: enc.state in ('draft', 'in_progress'))

        if not encounters_to_process:
            raise UserError(_("No encounters in 'Draft' or 'In Progress' state selected."))

        for encounter in encounters_to_process:
            if not encounter.service_line_ids:
                _logger.warning(
                    f"Encounter {encounter.name} has no service lines defined. Cannot mark as Ready for Billing without items.")
                # Optional: Raise UserError instead if you want to force users to add lines
                # raise UserError(_("Encounter '%s' has no service/product lines. Please add items before marking as ready for billing.", encounter.name))
                continue  # Skip this encounter if no lines

            # Use a list to collect vals for batch creation if possible
            pending_item_vals_list = []
            for line in encounter.service_line_ids:
                # --- Validation Checks ---
                if not line.product_id:
                    raise UserError(_("Service line is missing a Product/Service."))
                if line.quantity <= 0:
                    raise UserError(
                        _("Service line for product '%s' has zero or negative quantity.", line.product_id.name))
                # Ensure provider is set (crucial for commissions)
                practitioner = line.practitioner_id or encounter.practitioner_id
                if not practitioner:
                    raise UserError(
                        _("Provider is not set on service line for product '%s' and no default practitioner on encounter '%s'.",
                          line.product_id.name, encounter.name))
                # Ensure patient is set
                patient = encounter.patient_id  # Assume patient is always from encounter header
                if not patient:
                    raise UserError(_("Patient is not set on encounter '%s'.", encounter.name))
                # Ensure customer is set
                customer = encounter.partner_id or patient  # Fallback to patient if no owner
                if not customer:
                    raise UserError(_("Customer/Owner is not set on encounter '%s'.", encounter.name))
                # --- End Validation Checks ---

                item_vals = {
                    'encounter_id': encounter.id,
                    'partner_id': customer.id,
                    'patient_id': patient.id,
                    'product_id': line.product_id.id,
                    'description': line.description,  # Use line description
                    'qty': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'practitioner_id': practitioner.id,
                    'commission_pct': line.commission_pct,
                    'state': 'pending',  # Initial state
                    'notes': line.notes,  # Copy line notes
                    #'company_id': self.env.company.id,
                    # Link back to the source service line? Optional, but useful for traceability
                    # 'source_service_line_id': line.id, # Need to add this field to pending.pos.item model if desired
                }
                pending_item_vals_list.append(item_vals)

            if pending_item_vals_list:
                try:
                    # Create pending items - use sudo if permissions require it
                    created_items = PendingItem.sudo().create(pending_item_vals_list)
                    items_created_count += len(created_items)
                    _logger.info(f"Created {len(created_items)} pending POS items for encounter {encounter.name}.")
                    # Post chatter message?
                    encounter.message_post(body=_("%d items marked as pending for POS billing.", len(created_items)))
                except Exception as e:
                    _logger.error(f"Failed to create pending POS items for encounter {encounter.name}: {e}")
                    # Raise error to prevent state change if item creation fails?
                    raise UserError(_("Failed to create pending POS items for encounter %s: %s", encounter.name, e))

            # Update encounter state only if items were successfully processed (or if no items needed creating but state should still change)
            encounter.write({'state': 'ready_for_billing'})

        # Optional: Return notification? Could be done via JS in client action if needed
        if items_created_count > 0:
            _logger.info(
                f"Successfully processed {len(encounters_to_process)} encounters, created {items_created_count} total pending POS items.")
        return True

    def action_cancel(self):
        """ Cancel the encounter and any *associated* pending billing items. """
        # Find pending items LINKED TO THESE ENCOUNTERS specifically
        # Use search instead of mapped for potentially better performance if many encounters
        pending_items = self.env['ths.pending.pos.item'].search([
            ('encounter_id', 'in', self.ids),
            ('state', '=', 'pending')
        ])
        if pending_items:
            pending_items.sudo().action_cancel()  # Use the action on pending item if exists
            self.message_post(body=_("Associated pending billing items were cancelled."))

        # Set encounter state to cancelled
        self.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        """ Reset cancelled or 'Ready for Billing' encounter back to draft. """
        if any(enc.state == 'billed' for enc in self):
            raise UserError(_("Cannot reset an encounter that has already been processed through POS."))

        # Find associated pending items and cancel them if resetting from 'ready_for_billing'
        pending_items = self.env['ths.pending.pos.item'].search([
            ('encounter_id', 'in', self.ids),
            ('state', '=', 'pending')  # Only cancel pending ones
        ])
        if pending_items:
            pending_items.sudo().action_cancel()  # Use the action on pending item
            self.message_post(body=_("Associated pending billing items were cancelled."))

        # Cancel any cancelled pending items linked to this encounter (to allow re-billing if needed)
        # This might be too aggressive depending on workflow, maybe only allow reset from cancelled?
        # cancelled_pending_items = self.env['ths.pending.pos.item'].search([
        #     ('encounter_id', 'in', self.ids),
        #     ('state', '=', 'cancelled')
        # ])
        # if cancelled_pending_items:
        #     cancelled_pending_items.sudo().action_reset_to_pending() # Or maybe delete them? Needs care.
        #     self.message_post(body=_("Previously cancelled billing items were reset to pending."))

        self.write({'state': 'draft'})
        return True
