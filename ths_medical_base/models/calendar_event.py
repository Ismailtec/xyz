# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    """ Inherit Calendar Event to add medical context and encounter creation. """
    _inherit = 'calendar.event'

    # --- Fields to select specific Appointment Resources ---
    ths_practitioner_ar_id = fields.Many2one(
        'appointment.resource',
        string='Service Provider',
        domain="[('ths_resource_category', '=', 'practitioner')]",
        tracking=True,
        help="The specific service provider (as an appointment resource) for this event."
    )
    ths_location_ar_id = fields.Many2one(
        'appointment.resource',
        string='Room',
        domain="[('ths_resource_category', '=', 'location')]",
        tracking=True,
        copy=False,
        help="The specific room (as an appointment resource) for this event."
    )

    # --- Helper fields to store direct links to Employee and Treatment Room ---
    # These will be populated based on the _ar_id fields for your custom logic.
    # They can be readonly in the UI if selection happens via _ar_id fields.
    ths_practitioner_id = fields.Many2one(
        'hr.employee', string='Practitioner (Employee)',
        compute='_compute_derived_medical_entities', store=True, readonly=True,
        tracking=True, index=True
    )
    ths_room_id = fields.Many2one(
        'ths.treatment.room', string='Room (Treatment Room)',
        compute='_compute_derived_medical_entities', store=True, readonly=True,
        tracking=True, index=True
    )

    # Patient receiving the service
    ths_patient_id = fields.Many2one(
        'res.partner', string='Patient', index=True, tracking=True,
        domain="['|', ('ths_partner_type_id.is_patient', '=', True), ('ths_partner_type_id.name', '=', 'Walk-in')]",
        help="The patient this appointment is for."
    )
    ths_reason_for_visit = fields.Text(string='Reason for Visit')
    ths_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('billed', 'Billed/Departed'),
        ('cancelled_by_patient', 'Cancelled (Patient)'),
        ('cancelled_by_clinic', 'Cancelled (Clinic)'),
        ('no_show', 'No Show')
    ], string='Medical Status', index=True, tracking=True, default='scheduled', copy=False,
        help="Detailed status of the medical appointment.")

    ths_check_in_time = fields.Datetime(string='Check-in Time', readonly=True, copy=False)
    ths_check_out_time = fields.Datetime(string='Check-out Time', readonly=True, copy=False)
    ths_cancellation_reason_id = fields.Many2one(
        'ths.medical.cancellation.reason',
        string='Cancellation Reason', copy=False)

    # --- Walk-in Flag ---
    ths_is_walk_in = fields.Boolean(string="Walk-in", default=False, tracking=True,
                                    help="Check if this appointment was created for a walk-in patient.")

    # Link to the clinical encounter generated from this appointment
    ths_encounter_id = fields.Many2one(
        'ths.medical.base.encounter', string='Medical Encounter',
        readonly=True, copy=False, index=True, ondelete='set null')
    ths_encounter_count = fields.Integer(compute='_compute_ths_encounter_count', store=False)

    is_resource_based_type = fields.Boolean(
        compute='_compute_is_resource_based_type', store=False
    )
    appointment_booking_line_ids = fields.One2many(
        'appointment.booking.line',
        'calendar_event_id',
        string="Medical Booking Lines"
    )

    @api.depends('appointment_type_id.schedule_based_on')
    def _compute_is_resource_based_type(self):
        for rec in self:
            rec.is_resource_based_type = rec.appointment_type_id.schedule_based_on == 'resources'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        _logger.info(f"CALENDAR_EVENT DG: Initial res: {res}, context: {self.env.context}")

        ctx_appointment_type_id = self.env.context.get('default_appointment_type_id')
        ctx_resource_ids_m2m = self.env.context.get('default_appointment_resource_ids')
        ctx_resource_id_m2o = self.env.context.get('default_resource_id')

        appointment_type = self.env['appointment.type']
        if ctx_appointment_type_id:
            appointment_type = self.env['appointment.type'].browse(ctx_appointment_type_id).exists()
            if appointment_type and 'appointment_type_id' in fields_list:
                res['appointment_type_id'] = appointment_type.id
                _logger.info(f"CALENDAR_EVENT DG: Set appointment_type_id from context: {appointment_type.id}")

        context_ar_ids_to_process = []
        if ctx_resource_ids_m2m and isinstance(ctx_resource_ids_m2m, list):
            context_ar_ids_to_process.extend(ctx_resource_ids_m2m)
        if ctx_resource_id_m2o and isinstance(ctx_resource_id_m2o, int):
            if ctx_resource_id_m2o not in context_ar_ids_to_process:
                context_ar_ids_to_process.append(ctx_resource_id_m2o)

        final_selected_ar_ids_for_m2m = []

        if context_ar_ids_to_process:
            appt_resources = self.env['appointment.resource'].browse(list(set(context_ar_ids_to_process))).exists()
            _logger.info(f"CALENDAR_EVENT DG: Context appointment_resources found: {appt_resources.mapped('name')}")

            practitioner_ar = appt_resources.filtered(lambda r: r.ths_resource_category == 'practitioner')
            if practitioner_ar and 'ths_practitioner_ar_id' in fields_list:
                res['ths_practitioner_ar_id'] = practitioner_ar[0].id
                final_selected_ar_ids_for_m2m.append(practitioner_ar[0].id)
                _logger.info(
                    f"CALENDAR_EVENT DG: Defaulting ths_practitioner_ar_id from context: {practitioner_ar[0].name}")

            location_ar = appt_resources.filtered(lambda r: r.ths_resource_category == 'location')
            if location_ar and 'ths_location_ar_id' in fields_list:
                res['ths_location_ar_id'] = location_ar[0].id
                final_selected_ar_ids_for_m2m.append(location_ar[0].id)
                _logger.info(f"CALENDAR_EVENT DG: Defaulting ths_location_ar_id from context: {location_ar[0].name}")

            if not appointment_type and appt_resources:
                possible_types = self.env['appointment.type'].search([('schedule_based_on', '=', 'resources')])
                valid_appointment_types = self.env['appointment.type']
                for apt_type_rec in possible_types:
                    if all(ar_id in apt_type_rec.resource_ids.ids for ar_id in appt_resources.ids):
                        valid_appointment_types |= apt_type_rec
                if len(valid_appointment_types) == 1:
                    res['appointment_type_id'] = valid_appointment_types.id
                    appointment_type = valid_appointment_types
                    _logger.info(
                        f"CALENDAR_EVENT DG: Inferred appointment_type_id from context resources: {valid_appointment_types.name}")

        if 'appointment_resource_ids' in fields_list and final_selected_ar_ids_for_m2m:
            res['appointment_resource_ids'] = [Command.set(list(set(final_selected_ar_ids_for_m2m)))]
            _logger.info(
                f"CALENDAR_EVENT DG: Defaulting standard appointment_resource_ids to: {final_selected_ar_ids_for_m2m}")

        _logger.info(f"CALENDAR_EVENT DG: Final default_get res: {res}")
        return res

    # --- Compute and Onchange Methods ---
    @api.depends('ths_practitioner_ar_id', 'ths_practitioner_ar_id.employee_id',
                 'ths_location_ar_id', 'ths_location_ar_id.ths_treatment_room_id')
    def _compute_derived_medical_entities(self):
        """Populate ths_practitioner_id (Employee) and ths_room_id (TreatmentRoom)
           from the selected appointment.resource records."""
        for event in self:
            event.ths_practitioner_id = event.ths_practitioner_ar_id.employee_id if event.ths_practitioner_ar_id else False
            event.ths_room_id = event.ths_location_ar_id.ths_treatment_room_id if event.ths_location_ar_id else False

    @api.onchange('ths_practitioner_ar_id', 'ths_location_ar_id')
    def _onchange_selected_appointment_resources(self):
        selected_ar_ids = []
        if self.ths_practitioner_ar_id:
            selected_ar_ids.append(self.ths_practitioner_ar_id.id)
        if self.ths_location_ar_id:
            selected_ar_ids.append(self.ths_location_ar_id.id)

        # This ensures the standard M2M field is updated whenever our specific AR selectors change
        if 'appointment_resource_ids' in self._fields:
            self.appointment_resource_ids = [Command.set(list(set(selected_ar_ids)))]
        _logger.info(
            f"CALENDAR_EVENT OnChange ARs: Event {self.id or self.display_name or 'New'} updated standard appointment_resource_ids to {selected_ar_ids}")

    @api.onchange('appointment_type_id')
    def _onchange_appointment_type_id(self):
        """Set domains for ths_practitioner_ar_id and ths_location_ar_id based on selected appointment_type_id.
        Clear selections if they become invalid or if type is not 'resources' based."""

        practitioner_ar_domain = [('id', '=', False)]
        location_ar_domain = [('id', '=', False)]

        # Store current AR values (potentially from default_get or user input)
        # Use self._origin to get the value before this onchange started, if it's an existing record
        origin_practitioner_ar_id = self._origin.ths_practitioner_ar_id if self._origin else self.env[
            'appointment.resource']
        origin_location_ar_id = self._origin.ths_location_ar_id if self._origin else self.env['appointment.resource']

        # If appointment_type_id is cleared, or changed to non-resource based, clear AR fields
        if not self.appointment_type_id or self.appointment_type_id.schedule_based_on != 'resources':
            self.ths_practitioner_ar_id = False
            self.ths_location_ar_id = False
            _logger.info("CALENDAR_EVENT OnChange AptType: Not resource-based or type cleared. Cleared ARs.")
        else:  # appointment_type_id is set and is resource-based
            _logger.info(f"CALENDAR_EVENT OnChange AptType: '{self.appointment_type_id.name}' is resource-based.")
            all_available_ars_for_type = self.appointment_type_id.resource_ids

            practitioner_ars = all_available_ars_for_type.filtered(lambda r: r.ths_resource_category == 'practitioner')
            location_ars = all_available_ars_for_type.filtered(lambda r: r.ths_resource_category == 'location')

            if practitioner_ars:
                practitioner_ar_domain = [('id', 'in', practitioner_ars.ids)]
            if location_ars:
                location_ar_domain = [('id', 'in', location_ars.ids)]

            # Preserve default_get / user-set value if it's still valid for the new type
            if self.ths_practitioner_ar_id:  # If it was set by default_get or user
                if self.ths_practitioner_ar_id not in practitioner_ars:
                    self.ths_practitioner_ar_id = False  # Clear if no longer valid
            elif len(practitioner_ars) == 1:  # Auto-select if only one option and not set by default_get
                self.ths_practitioner_ar_id = practitioner_ars[0]

            if self.ths_location_ar_id:  # If it was set by default_get or user
                if self.ths_location_ar_id not in location_ars:
                    self.ths_location_ar_id = False  # Clear if no longer valid
            elif len(location_ars) == 1:  # Auto-select if only one option
                self.ths_location_ar_id = location_ars[0]

            _logger.info(
                f"CALENDAR_EVENT OnChange AptType: Practitioner AR Domain: {practitioner_ar_domain}, Selected: {self.ths_practitioner_ar_id.name if self.ths_practitioner_ar_id else 'None'}")
            _logger.info(
                f"CALENDAR_EVENT OnChange AptType: Location AR Domain: {location_ar_domain}, Selected: {self.ths_location_ar_id.name if self.ths_location_ar_id else 'None'}")

        # Always call the dependent onchange to sync appointment_resource_ids M2M
        self._onchange_selected_appointment_resources()

        return {'domain': {
            'ths_practitioner_ar_id': practitioner_ar_domain,
            'ths_location_ar_id': location_ar_domain,
        }}

    @api.onchange('ths_practitioner_ar_id', 'ths_location_ar_id')
    def _onchange_selected_appointment_resources(self):
        """
        When a practitioner or location (as appointment.resource) is selected,
        update the standard calendar.event.appointment_resource_ids (M2M) field.
        This also triggers the recompute of ths_practitioner_id and ths_room_id.
        """
        selected_ar_ids = []
        if self.ths_practitioner_ar_id:
            selected_ar_ids.append(self.ths_practitioner_ar_id.id)
        if self.ths_location_ar_id:
            selected_ar_ids.append(self.ths_location_ar_id.id)

        if 'resource_ids' in self._fields:
            self.resource_ids = [Command.set(list(set(selected_ar_ids)))]
        _logger.info(
            f"CALENDAR_EVENT OnChange ARs: Event {self.id or 'New'} updated standard resource_ids to {selected_ar_ids}")

    @api.depends('ths_practitioner_ar_id', 'ths_location_ar_id')
    def _compute_default_resources(self):
        for rec in self:
            if not rec.resource_ids:
                selected = []
                if rec.ths_practitioner_ar_id:
                    selected.append(rec.ths_practitioner_ar_id.id)
                if rec.ths_location_ar_id:
                    selected.append(rec.ths_location_ar_id.id)
                rec.resource_ids = [Command.set(list(set(selected)))]

    @api.onchange('resource_ids')
    def _onchange_resource_ids_to_ar(self):
        if not self.resource_ids:
            return

        practitioner = None
        location = None
        for res in self.resource_ids:
            if res.ths_resource_category == 'practitioner' and not practitioner:
                practitioner = res
            elif res.ths_resource_category == 'location' and not location:
                location = res

        # Only autofill if not already set by the user
        if not self.ths_practitioner_ar_id:
            self.ths_practitioner_ar_id = practitioner
        if not self.ths_location_ar_id:
            self.ths_location_ar_id = location

        _logger.info(
            f"[ONCHANGE] resource_ids updated: AR fields auto-selected: practitioner={practitioner}, location={location}")

    # --- Walk-in Partner Handling ---
    def _get_walkin_partner_type(self):
        """ Helper to safely get the Walk-in partner type """
        # Use sudo() for potential cross-company or restricted access to ref
        return self.env.ref('ths_medical_base.partner_type_walkin', raise_if_not_found=False).sudo()

    def _prepare_walkin_partner_vals(self, walkin_type_id):
        """ Prepare values for creating a walk-in partner """
        # Generate sequence value first to use in name
        walkin_sequence = self.env.ref('ths_medical_base.seq_partner_ref_walkin', raise_if_not_found=False)
        sequence_val = "WALK-IN"  # Fallback name
        if walkin_sequence:
            try:
                sequence_val = walkin_sequence.sudo().next_by_id()
            except Exception as e:
                _logger.error(f"Failed to get next walk-in sequence value: {e}")
                # Proceed with fallback name
        else:
            _logger.warning("Walk-in sequence 'seq_partner_ref_walkin' not found.")

        return {
            'name': f"Walk-in Patient ({sequence_val})",  # Placeholder name
            'ths_partner_type_id': walkin_type_id,
            # company_type will be set automatically based on partner type by ths_base
            # Add company_id if applicable/needed
            # 'company_id': self.env.company.id,
        }

    def _handle_walkin_partner(self, vals):
        """ Check if walk-in partner needs to be created """
        walkin_type = self._get_walkin_partner_type()
        if not walkin_type:
            _logger.error("Walk-in Partner Type not found. Cannot create walk-in partner.")
            # Optionally raise UserError or just log and skip
            # raise UserError(_("Configuration Error: Walk-in Partner Type is missing."))
            return vals  # Return original vals

        # Check conditions: walk-in flag is true, and no patient/partner is provided
        if vals.get('ths_is_walk_in') and not vals.get('ths_patient_id') and not vals.get('partner_id'):
            _logger.info("Creating a new Walk-in partner for walk-in appointment.")
            partner_vals = self._prepare_walkin_partner_vals(walkin_type.id)
            try:
                # Use sudo for partner creation
                walkin_partner = self.env['res.partner'].sudo().create(partner_vals)
                _logger.info(f"Created Walk-in partner: {walkin_partner.name} (ID: {walkin_partner.id})")
                # Assign the new partner to both patient and partner fields of the appointment
                vals['ths_patient_id'] = walkin_partner.id
                vals['partner_id'] = walkin_partner.id
                # Add attendees automatically if needed
                vals['partner_ids'] = vals.get('partner_ids', []) + [(4, walkin_partner.id)]
            except Exception as e:
                _logger.error(f"Failed to create walk-in partner: {e}")
                # Raise error to prevent appointment creation without partner?
                raise UserError(_("Failed to create walk-in partner record: %s", e))
        return vals

    # --- Create Override ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Override create to handle walk-in partner creation """
        processed_vals_list = []
        for vals in vals_list:
            vals = self._handle_walkin_partner(vals.copy())

            apt_type = self.env['appointment.type'].browse(vals.get('appointment_type_id')).exists() if vals.get(
                'appointment_type_id') else None

            if apt_type:
                if not vals.get('ths_practitioner_ar_id'):
                    practitioners = apt_type.resource_ids.filtered(lambda r: r.ths_resource_category == 'practitioner')
                    if practitioners:
                        vals['ths_practitioner_ar_id'] = practitioners[0].id

                if not vals.get('ths_location_ar_id'):
                    rooms = apt_type.resource_ids.filtered(lambda r: r.ths_resource_category == 'location')
                    if rooms:
                        vals['ths_location_ar_id'] = rooms[0].id

            res_ids = list(filter(None, [
                vals.get('ths_practitioner_ar_id'),
                vals.get('ths_location_ar_id')
            ]))

            if res_ids and not vals.get('appointment_booking_line_ids'):
                lines = []
                for res_id in res_ids:
                    resource = self.env['appointment.resource'].browse(res_id).exists()
                    if resource:
                        lines.append((0, 0, {
                            'appointment_resource_id': resource.id,
                            'capacity_reserved': resource.capacity or 1
                        }))
                vals['appointment_booking_line_ids'] = lines

            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    # --- Write Override ---
    # Consider if walk-in logic needs adjustment on write (e.g., if walk-in flag toggled)
    # For now, let's assume walk-in partner is only created at the initial creation step.
    # Adding logic here can become complex (e.g., what if user sets walk-in=True and removes patient?)
    def write(self, vals):
        # Handle walk-in before super to ensure partner_id is set if needed by other logic
        if vals.get('ths_is_walk_in') and not vals.get('ths_patient_id') and not self.ths_patient_id:
            vals = self._handle_walkin_partner(vals.copy())

        update_lines = 'ths_practitioner_ar_id' in vals or 'ths_location_ar_id' in vals

        if update_lines:
            practitioner_id = vals.get('ths_practitioner_ar_id',
                                       self.ths_practitioner_ar_id.id if self.ths_practitioner_ar_id else None)
            location_id = vals.get('ths_location_ar_id',
                                   self.ths_location_ar_id.id if self.ths_location_ar_id else None)

            res_ids = list(filter(None, [practitioner_id, location_id]))
            lines = []
            for res_id in res_ids:
                resource = self.env['appointment.resource'].browse(res_id).exists()
                if resource:
                    lines.append((0, 0, {
                        'appointment_resource_id': resource.id,
                        'capacity_reserved': resource.capacity or 1
                    }))

            vals['appointment_booking_line_ids'] = [(5, 0, 0)] + lines
            vals['appointment_resource_ids'] = [Command.set(res_ids)]

        return super().write(vals)

        # If onchange didn't cover a specific programmatic write scenario for dependencies:
        # if 'ths_practitioner_ar_id' in vals or 'ths_location_ar_id' in vals or 'appointment_type_id' in vals:
        #     for event_rec in self: # self can be multiple records in write
        #         if 'appointment_type_id' in vals: # If type changed, re-trigger its onchange
        #             event_rec._onchange_appointment_type_id()
        #         # Then trigger the AR selection onchange
        #         event_rec._onchange_selected_appointment_resources()
        # return res

    # @api.constrains('ths_is_walk_in', 'ths_patient_id', 'partner_id')
    # def _check_walkin_partner(self):
    #     """ Ensure walk-in appointments have a partner/patient eventually """
    #     for event in self:
    #         # This check might be too strict during initial creation before partner is assigned.
    #         # Let's comment it out for now, relying on the create logic.
    #         # if event.ths_is_walk_in and not event.ths_patient_id and not event.partner_id:
    #         #     raise ValidationError(_("Walk-in appointments must have a Patient/Partner assigned."))
    #         pass  # Keep constraint simple for now

    # --- Encounter Count & Actions
    @api.depends('ths_encounter_id')
    def _compute_ths_encounter_count(self):

        for event in self:
            event.ths_encounter_count = 1 if event.ths_encounter_id else 0

    # --- Action Buttons ---
    def action_check_in(self):
        """ Set status to Checked In and record time. Trigger encounter creation. """
        now = fields.Datetime.now()
        for event in self:
            if event.ths_status not in ('scheduled', 'confirmed'):
                raise UserError(_("Appointment must be Scheduled or Confirmed to Check In."))
            # Ensure patient/partner is set before check-in
            if not event.ths_patient_id or not event.partner_id:
                raise UserError(_("Cannot check in appointment without a Patient and Customer assigned."))
                # Ensure practitioner is selected if medical appointment
            if event.appointment_type_id and event.appointment_type_id.schedule_based_on == 'resources' and not event.ths_practitioner_ar_id:
                raise UserError(
                    _("Cannot check in: A Service Provider must be selected for this medical appointment type."))
            event.write({
                'ths_status': 'checked_in',
                'ths_check_in_time': now
            })
            event._create_medical_encounter()  # Trigger encounter creation
        return True

    def action_start_consultation(self):
        """ Set status to In Progress. """
        for event in self:
            if event.ths_status != 'checked_in':
                raise UserError(_("Patient must be Checked In before starting the consultation."))
            if not event.ths_encounter_id:
                event._create_medical_encounter()
            if not event.ths_encounter_id:
                raise UserError(_("Cannot start consultation: Medical Encounter is missing."))

            event.write({'ths_status': 'in_progress'})
            if event.ths_encounter_id.state == 'draft':
                if hasattr(event.ths_encounter_id, 'action_in_progress'):
                    event.ths_encounter_id.action_in_progress()
                else:  # Fallback if action doesn't exist
                    event.ths_encounter_id.write({'state': 'in_progress'})
        return True

    def action_complete_and_bill(self):
        """ Mark appointment and encounter as completed/ready for billing. """
        now = fields.Datetime.now()
        for event in self:
            if event.ths_status not in ('checked_in', 'in_progress'):
                raise UserError(_("Appointment must be Checked In or In Progress to mark as Completed."))
            if not event.ths_encounter_id:
                raise UserError(_("Cannot complete appointment: Corresponding Medical Encounter not found."))

            event.write({
                'ths_status': 'completed',
                'ths_check_out_time': now
            })
            # Trigger encounter's action_ready_for_billing
            if event.ths_encounter_id.state != 'billed':  # Avoid re-triggering
                try:
                    event.ths_encounter_id.action_ready_for_billing()
                except UserError as ue:
                    # Catch specific user errors (like missing lines) and show them
                    raise ue
                except Exception as e:
                    _logger.error("Error calling action_ready_for_billing from appointment %s: %s", event.id, e)
                    raise UserError(_("An error occurred while preparing items for billing: %s", e))
        return True

    def action_cancel_appointment(self):
        """ Open wizard to select cancellation reason and set status. """
        # TODO: Implement wizard for reason selection. Needs a transient model.
        # For now, simple cancel:
        # Determine blame based on simple logic or default
        blame_reason = self.env['ths.medical.cancellation.reason'].search([('blame', '=', 'clinic')], limit=1)
        vals_to_write = {
            'ths_status': 'cancelled_by_clinic',
            'ths_cancellation_reason_id': blame_reason.id if blame_reason else False
        }

        self.write(vals_to_write)
        for event_rec in self:
            if event_rec.ths_encounter_id and event_rec.ths_encounter_id.state not in ('billed', 'cancelled'):
                if hasattr(event_rec.ths_encounter_id, 'action_cancel'):
                    event_rec.ths_encounter_id.action_cancel()
                else:
                    event_rec.ths_encounter_id.write({'state': 'cancelled'})
        return True

    def action_mark_no_show(self):
        """ Mark as No Show. """
        self.write({'ths_status': 'no_show'})
        # Cancel related encounter
        for event_rec in self:
            if event_rec.ths_encounter_id and event_rec.ths_encounter_id.state not in ('billed', 'cancelled'):
                if hasattr(event_rec.ths_encounter_id, 'action_cancel'):
                    event_rec.ths_encounter_id.action_cancel()
                else:
                    event_rec.ths_encounter_id.write({'state': 'cancelled'})
        return True

    # --- Encounter Creation Logic ---
    def _prepare_encounter_vals(self):
        """ Prepare values for creating a ths.medical.base.encounter record. """
        self.ensure_one()
        # Patient and Partner should be validated before calling this (e.g., in action_check_in)
        patient_partner = self.ths_patient_id
        owner_partner = self.ths_patient_id
        practitioner_employee = self.ths_practitioner_id  # This is now computed from ths_practitioner_ar_id
        if not patient_partner or not owner_partner:
            raise UserError(_("Cannot create encounter: Patient and Customer/Owner must be set on the appointment."))
        if not practitioner_employee:  # Check the derived employee field
            raise UserError(_("Cannot create encounter: Practitioner is not set."))

        return {
            'appointment_id': self.id,
            'state': 'draft',  # Start encounter in draft
            'patient_id': patient_partner.id,
            'practitioner_id': practitioner_employee.id,
            'partner_id': owner_partner.id,
            # EMR fields like chief complaint could potentially be copied from appointment reason
            'chief_complaint': self.ths_reason_for_visit,
            # date_start, date_end, company_id are related or computed
        }

    def _create_medical_encounter(self):
        """ Creates a medical encounter if one doesn't exist for this appointment. """
        self.ensure_one()
        Encounter = self.env['ths.medical.base.encounter']
        if not self.ths_encounter_id:
            # Double check if exists but not linked
            existing = Encounter.sudo().search([('appointment_id', '=', self.id)], limit=1)
            if existing:
                self.sudo().write({'ths_encounter_id': existing.id})
                _logger.info(f"Appointment {self.id}: Linked existing encounter {existing.name}.")
            else:
                try:
                    encounter_vals = self._prepare_encounter_vals()
                    # Use sudo for encounter creation
                    new_encounter = Encounter.sudo().create(encounter_vals)
                    # Use sudo to write back link
                    self.sudo().write({'ths_encounter_id': new_encounter.id})
                    _logger.info(f"Appointment {self.id}: Created new encounter {new_encounter.name}.")
                    self.message_post(body=_("Medical Encounter %s created.", new_encounter._get_html_link()),
                                      message_type='comment', subtype_xmlid='mail.mt_note')
                except Exception as e:
                    _logger.error(f"Failed to create encounter for appointment {self.id}: {e}")
                    self.message_post(body=_("Failed to create medical encounter: %s", e))
                # Consider if check-in should be reverted or an error raised more prominently

    # --- Action to View Encounter ---
    def action_view_encounter(self):
        self.ensure_one()
        if not self.ths_encounter_id:
            return False
        action = self.env['ir.actions.actions']._for_xml_id('ths_medical_base.action_ths_medical_encounter')
        action['domain'] = [('id', '=', self.ths_encounter_id.id)]
        action['res_id'] = self.ths_encounter_id.id
        action['views'] = [(self.env.ref('ths_medical_base.view_ths_medical_encounter_form').id, 'form')]
        return action
