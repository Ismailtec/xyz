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

    # For human medical: partner_id = patient (same person receiving care and paying)
    partner_id = fields.Many2one(
        'res.partner',
        string='Patient',  # In human medical, patient is the customer
        #related='appointment_id.partner_id',
        store=True,
        index=True,
        #readonly=True,
        help="Billing customer."
    )

    # For medical: patient_ids = [patient]
    patient_ids = fields.Many2many(
        'res.partner',
        'medical_encounter_patient_rel',
        'encounter_id',
        'patient_id',
        string='Patients',
        domain="[('ths_partner_type_id.is_patient', '=', True)]",
        store=True,
        index=True,
        #readonly=True,
        help="Patients participating in this encounter. In human medical practice, these are the same people as in partner_id."
    )

    # TODO: Add computed fields for primary patient info for backward compatibility
    patient_ref = fields.Char(string="Patient File", related='patient_ids.ref', store=False, readonly=True)
    patient_mobile = fields.Char(string="Patient Mobile", related='patient_ids.mobile', store=False, readonly=True)

    practitioner_id = fields.Many2one(
        'appointment.resource',
        string='Service Provider',
        domain="[('ths_resource_category', '=', 'practitioner')]",
        related='appointment_id.ths_practitioner_id',
        store=True,
        index=True,
        readonly=True
    )
    room_id = fields.Many2one(
        'appointment.resource',
        string='Room',
        related='appointment_id.ths_room_id',
        store=True,
        index=True,
        #readonly=True
    )
    date_start = fields.Datetime(
        string='Start Time',
        related='appointment_id.start',
        store=True,
        #readonly=True
    )
    date_end = fields.Datetime(
        string='End Time',
        related='appointment_id.stop',
        store=True,
        #readonly=True
    )
    appointment_status = fields.Selection(
        related='appointment_id.appointment_status',
        string='Appointment Status',
        store=True,
        readonly=True,
        help="Status of the related appointment"
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('ready_for_billing', 'Ready For Billing'),
        ('billed', 'Billed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', index=True, tracking=True, copy=False)

    # Lines representing services/items used in the encounter
    service_line_ids = fields.One2many(
        'ths.medical.encounter.service',
        'encounter_id',
        string='Services & Products Used',
        copy=True
    )

    notes = fields.Text(string="Internal Notes")

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

    # --- Compute Methods ---
    @api.depends('appointment_id', 'appointment_id.partner_ids')
    def _compute_all_fields(self):
        """
        Compute partner, patient, and practitioner from the appointment.
        For human medical: partner_id = primary patient, patient_ids = all patients (same people)
        """
        for encounter in self:
            appointment = encounter.appointment_id

            # For human medical: partner_id is the primary patient (billing customer)
            #encounter.partner_id = appointment.partner_id if appointment else False

            # For human medical: patient_ids = partner_ids (same people)
            if appointment and hasattr(appointment, 'ths_patient_ids'):
                encounter.patient_ids = appointment.ths_patient_ids
            else:
                encounter.patient_ids = False

            # Get Practitioner from appointment
            encounter.practitioner_id = (appointment.ths_practitioner_id
                                         if appointment and hasattr(appointment, 'ths_practitioner_id')
                                         else False)

            # Get Room from appointment
            encounter.room_id = (appointment.ths_room_id
                                 if appointment and hasattr(appointment, 'ths_room_id')
                                 else False)

    @api.depends('date_start')
    def _compute_daily_id(self):
        """ Find or create the daily encounter record for the encounter's date. """
        DailyEncounter = self.env['ths.daily.encounter']
        for encounter in self:
            target_date = fields.Date.context_today(encounter, timestamp=encounter.date_start)

            if not target_date:
                encounter.daily_id = False
                continue

            daily_rec = DailyEncounter.sudo().search([
                ('date', '=', target_date),
            ], limit=1)

            if not daily_rec:
                try:
                    daily_rec = DailyEncounter.sudo().create([{
                        'date': target_date,
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
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('medical.encounter') or _('New')
        return super(ThsMedicalEncounter, self).create(vals_list)

    # --- Actions ---
    def action_in_progress(self):
        """Mark encounter as in progress - usually triggered by appointment check-in"""
        for encounter in self:
            if encounter.state == 'draft':
                encounter.write({'state': 'in_progress'})
                encounter.message_post(body=_("Encounter started - patient consultation in progress."))
        return True

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
                continue

            # Use a list to collect vals for batch creation
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

                # Ensure patient is set - handle Many2many field
                patients = encounter.patient_ids
                if not patients:
                    raise UserError(_("Patients not set on encounter '%s'.", encounter.name))

                # TODO: Handle multiple patients scenario - for now use first patient
                primary_patient = patients[0]

                # For human medical: customer = patient (same person)
                customer = primary_patient  # In human medical, patient is the customer
                if not customer:
                    raise UserError(_("Customer/Patient is not set on encounter '%s'.", encounter.name))
                # --- End Validation Checks ---

                item_vals = {
                    'encounter_id': encounter.id,
                    'partner_id': encounter.partner_id.id,  # In human medical: patient is the customer
                    'patient_id': primary_patient.id,  # Same as partner_id in human medical
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'qty': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'practitioner_id': practitioner.id,
                    'room_id': encounter.room_id.id if encounter.room_id else False,
                    'commission_pct': line.commission_pct,
                    'state': 'pending',
                    'notes': line.notes,
                }
                pending_item_vals_list.append(item_vals)

            if pending_item_vals_list:
                try:
                    created_items = PendingItem.sudo().create(pending_item_vals_list)
                    items_created_count += len(created_items)
                    _logger.info(f"Created {len(created_items)} pending POS items for encounter {encounter.name}.")
                    encounter.message_post(body=_("%d items marked as pending for POS billing.", len(created_items)))
                except Exception as e:
                    _logger.error(f"Failed to create pending POS items for encounter {encounter.name}: {e}")
                    raise UserError(_("Failed to create pending POS items for encounter %s: %s", encounter.name, e))

            # Update encounter state
            encounter.write({'state': 'ready_for_billing'})

        if items_created_count > 0:
            _logger.info(
                f"Successfully processed {len(encounters_to_process)} encounters, created {items_created_count} total pending POS items.")
        return True

    def action_cancel(self):
        """ Cancel the encounter and any associated pending billing items. """
        # Find pending items linked to these encounters
        pending_items = self.env['ths.pending.pos.item'].search([
            ('encounter_id', 'in', self.ids),
            ('state', '=', 'pending')
        ])
        if pending_items:
            pending_items.sudo().action_cancel()
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
            ('state', '=', 'pending')
        ])
        if pending_items:
            pending_items.sudo().action_cancel()
            self.message_post(body=_("Associated pending billing items were cancelled."))

        self.write({'state': 'draft'})
        return True

    # --- Method to sync encounter state with appointment status ---
    def _sync_with_appointment_status(self):
        """Sync encounter state based on appointment status changes"""
        for encounter in self:
            if not encounter.appointment_id:
                continue

            apt_status = encounter.appointment_id.appointment_status

            # Auto-progress encounter state based on appointment status
            if apt_status == 'checked_in' and encounter.state == 'draft':
                encounter.action_in_progress()
            elif apt_status in ('completed', 'billed') and encounter.state == 'in_progress':
                # Only auto-advance if there are service lines
                if encounter.service_line_ids:
                    encounter.action_ready_for_billing()
            elif apt_status in ('cancelled_by_patient', 'cancelled_by_clinic', 'no_show') and encounter.state not in (
                    'billed', 'cancelled'):
                encounter.action_cancel()

    @api.model
    def _cron_sync_encounter_states(self):
        """Cron job to sync encounter states with appointment statuses"""
        # Find encounters that might need state updates
        encounters_to_check = self.search([
            ('state', 'in', ('draft', 'in_progress')),
            ('appointment_id', '!=', False),
        ])

        for encounter in encounters_to_check:
            try:
                encounter._sync_with_appointment_status()
            except Exception as e:
                _logger.error(f"Failed to sync encounter {encounter.id} with appointment status: {e}")
