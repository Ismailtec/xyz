# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    """ Inherit Calendar Event to add medical context and encounter creation. """
    _inherit = 'calendar.event'

    name = fields.Char(default="Draft")

    ths_practitioner_id = fields.Many2one(
        'appointment.resource',
        string='Service Provider',
        domain="[('ths_resource_category', '=', 'practitioner')]",
        compute='_compute_appointment_ars',
        store=True,
        readonly=False,
        tracking=True,
        help="The specific service provider (as an appointment resource) for this event."
    )
    ths_room_id = fields.Many2one(
        'appointment.resource',
        string='Room',
        domain="[('ths_resource_category', '=', 'location')]",
        compute='_compute_appointment_ars',
        store=True,
        readonly=False,
        tracking=True,
        copy=False,
        help="The specific room (as an appointment resource) for this event."
    )

    ths_practitioner_id_domain = fields.Char(compute='_compute_ar_domains')
    ths_room_id_domain = fields.Char(compute='_compute_ar_domains')

    # Patient receiving the service
    ths_patient_id = fields.Many2one(
        'res.partner', string='Patients', index=True, tracking=True, store=True,
        compute='_compute_patient_from_partner_ids',
        domain="['|', ('ths_partner_type_id.is_patient', '=', True), ('ths_partner_type_id.name', '=', 'Walk-in')]",
        help="The patient this appointment is for."
    )

    ths_reason_for_visit = fields.Text(string='Reason for Visit')

    appointment_status = fields.Selection(
        selection_add=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('checked_in', 'Checked In'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('billed', 'Billed'),
            ('cancelled_by_patient', 'Cancelled (Patient)'),
            ('cancelled_by_clinic', 'Cancelled (Clinic)'),
            ('no_show', 'No Show')
        ],
        ondelete={
            'draft': 'cascade', 'confirmed': 'cascade', 'checked_in': 'cascade',
            'in_progress': 'cascade', 'completed': 'cascade', 'billed': 'cascade',
            'cancelled_by_patient': 'cascade', 'cancelled_by_clinic': 'cascade',
            'no_show': 'cascade',
            # Hide unwanted original statuses
            'request': 'set null', 'booked': 'set null',
            'attended': 'set null'
        }
    )

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

    # appointment_booking_line_ids = fields.One2many(
    #     'appointment.booking.line',
    #     'calendar_event_id',
    #     string="Medical Booking Lines"
    # )

    @api.depends('appointment_type_id.schedule_based_on')
    def _compute_is_resource_based_type(self):
        for rec in self:
            rec.is_resource_based_type = rec.appointment_type_id.schedule_based_on == 'resources'

    @api.depends('appointment_type_id.resource_ids', 'appointment_type_id.schedule_based_on')
    def _compute_ar_domains(self):
        for rec in self:
            domain_pract = "[('ths_resource_category', '=', 'practitioner')]"
            domain_loc = "[('ths_resource_category', '=', 'location')]"

            if rec.appointment_type_id and rec.appointment_type_id.schedule_based_on == 'resources':
                ids_str = str(rec.appointment_type_id.resource_ids.ids)
                domain_pract = "[('ths_resource_category', '=', 'practitioner'), ('id', 'in', %s)]" % ids_str
                domain_loc = "[('ths_resource_category', '=', 'location'), ('id', 'in', %s)]" % ids_str

            rec.ths_practitioner_id_domain = domain_pract
            rec.ths_room_id_domain = domain_loc

    @api.depends('resource_ids')
    def _compute_appointment_ars(self):
        for rec in self:
            practitioner = None
            location = None
            for res in rec.resource_ids:
                if res.ths_resource_category == 'practitioner' and not practitioner:
                    practitioner = res
                elif res.ths_resource_category == 'location' and not location:
                    location = res

            rec.ths_practitioner_id = practitioner
            rec.ths_room_id = location

    @api.depends('partner_ids')
    def _compute_patient_from_partner_ids(self):
        for event in self:
            if event.partner_ids:
                first = event.partner_ids[0]
                if getattr(first, 'ths_partner_type_id', False) and (
                        first.ths_partner_type_id.is_patient or first.ths_partner_type_id.name == 'Walk-in'
                ):
                    event.ths_patient_id = first
                else:
                    event.ths_patient_id = False
            else:
                event.ths_patient_id = False

    @api.model
    def default_get(self, fields_list):
        """
        Handles gantt context properly and let inverse methods do the work
        """
        res = super().default_get(fields_list)
        # _logger.info(f"CALENDAR_EVENT DG: Context (After super 1st): {self.env.context}")

        # Get appointment type from context
        ctx_appointment_type_id = self.env.context.get('default_appointment_type_id')
        if ctx_appointment_type_id and 'appointment_type_id' in fields_list:
            res['appointment_type_id'] = ctx_appointment_type_id

        # Gantt sets default_resource_ids, we use resource_ids (computed field with inverse)
        ctx_resource_ids = self.env.context.get('default_resource_ids', [])

        if ctx_resource_ids and 'resource_ids' in fields_list:
            # Set resource_ids - this will trigger inverse method automatically
            res['resource_ids'] = [Command.set(ctx_resource_ids)]
            # _logger.info(f"CALENDAR_EVENT DG: Set resource_ids from gantt context (2nd): {ctx_resource_ids}")

            # The onchange will populate our custom fields from resource_ids
            if len(ctx_resource_ids) == 1:
                resource = self.env['appointment.resource'].browse(ctx_resource_ids[0]).exists()
                if resource:
                    if resource.ths_resource_category == 'practitioner' and 'ths_practitioner_id' in fields_list:
                        res['ths_practitioner_id'] = resource.id
                    elif resource.ths_resource_category == 'location' and 'ths_room_id' in fields_list:
                        res['ths_room_id'] = resource.id

        # Set default medical status
        if res.get('appointment_type_id') and 'appointment_status' in fields_list and not res.get('appointment_status'):
            res['appointment_status'] = 'draft'

        partner_ids = self.env.context.get('default_partner_ids') or []
        if partner_ids and 'ths_patient_id' in fields_list:
            res['ths_patient_id'] = partner_ids[0]

        # _logger.info(f"CALENDAR_EVENT DG: Final res: {res}")
        return res

    # --- Compute and Onchange Methods ---
    # @api.depends('ths_practitioner_id', 'ths_practitioner_id.employee_id',
    #              'ths_room_id', 'ths_room_id.ths_treatment_room_id')
    # def _compute_derived_medical_entities(self):
    #     """Populate ths_practitioner_id (Employee) and ths_room_id (TreatmentRoom)
    #        from the selected appointment.resource records."""
    #     for event in self:
    #         event.ths_practitioner_id = event.ths_practitioner_id.employee_id if event.ths_practitioner_id else False
    #         event.ths_room_id = event.ths_room_id.ths_treatment_room_id if event.ths_room_id else False

    @api.onchange('ths_practitioner_id', 'ths_room_id')
    def _onchange_practitioner_or_room(self):
        selected_ids = []
        if self.ths_practitioner_id:
            selected_ids.append(self.ths_practitioner_id.id)
        if self.ths_room_id:
            selected_ids.append(self.ths_room_id.id)
        self.resource_ids = [Command.set(list(set(selected_ids)))]

        # This ensures the standard M2M field is updated whenever our specific AR selectors change
        if 'appointment_resource_ids' in self._fields:
            self.appointment_resource_ids = [Command.set(list(set(selected_ids)))]
        # _logger.info(
        #     f"CALENDAR_EVENT OnChange ARs: Event {self.id or self.display_name or 'New'} updated standard appointment_resource_ids to {selected_ar_ids}")

    @api.onchange('partner_ids')
    def _onchange_partner_ids_to_patient(self):
        """Auto-populate ths_patient_id when partner_id is set to a patient"""
        if self.partner_ids:
            first = self.partner_ids[0]
            if hasattr(first, 'ths_partner_type_id') and (
                    first.ths_partner_type_id.is_patient or first.ths_partner_type_id.name == 'Walk-in'):
                self.ths_patient_id = first
            else:
                self.ths_patient_id = False
        else:
            self.ths_patient_id = False
            # _logger.info(f"CALENDAR_EVENT: Auto-set patient from partner: {self.partner_id.name}")

    @api.onchange('ths_patient_id')
    def _onchange_patient_attendees(self):
        if self.ths_patient_id:
            self.partner_ids = [Command.set([self.ths_patient_id.id])]
        else:
            self.partner_ids = [Command.clear()]

    # @api.depends('ths_practitioner_id', 'ths_room_id')
    # def _compute_default_resources(self):
    #     for rec in self:
    #         if not rec.resource_ids:
    #             selected = []
    #             if rec.ths_practitioner_id:
    #                 selected.append(rec.ths_practitioner_id.id)
    #             if rec.ths_room_id:
    #                 selected.append(rec.ths_room_id.id)
    #             rec.resource_ids = [Command.set(list(set(selected)))]

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
            # _logger.info("Creating a new Walk-in partner for walk-in appointment.")
            partner_vals = self._prepare_walkin_partner_vals(walkin_type.id)
            try:
                # Use sudo for partner creation
                walkin_partner = self.env['res.partner'].sudo().create(partner_vals)
                # _logger.info(f"Created Walk-in partner: {walkin_partner.name} (ID: {walkin_partner.id})")
                # Assign the new partner to both patient and partner fields of the appointment
                vals['ths_patient_id'] = walkin_partner.id
                vals['partner_id'] = walkin_partner.id
                # Add attendees automatically if needed
                vals['partner_ids'] = vals.get('partner_ids', []) + [(4, walkin_partner.id)]
            except Exception as e:
                # _logger.error(f"Failed to create walk-in partner: {e}")
                # Raise error to prevent appointment creation without partner?
                raise UserError(_("Failed to create walk-in partner record: %s", e))
        return vals

    # --- Create Override ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Override create to handle walk-in partner creation and set ARs and patient from context """
        processed_vals_list = []
        for vals in vals_list:
            vals = self._handle_walkin_partner(vals.copy())

            # Populate ths_patient_id from partner_id
            # if vals.get("partner_id") and not vals.get("ths_patient_id"):
            #     vals["ths_patient_id"] = vals["partner_id"]

            vals["name"] = self.env["ir.sequence"].next_by_code("medical.appointment")
            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    # --- Write Override ---
    def write(self, vals):
        # Handle walk-in before super to ensure partner_id is set if needed
        if vals.get("ths_is_walk_in") and not vals.get("ths_patient_id") and not self.ths_patient_id:
            vals = self._handle_walkin_partner(vals.copy())

        # Update ths_patient_id if partner_id is updated
        # if "partner_id" in vals and not vals.get("ths_patient_id"):
        #     vals["ths_patient_id"] = vals["partner_id"]

        return super().write(vals)

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
            if event.appointment_status not in ('draft', 'confirmed'):
                raise UserError(_("Appointment must be Draft or Confirmed to Check In."))
            if event.appointment_status in ('completed', 'billed', 'cancelled_by_clinic', 'no_show'):
                raise UserError(_('You cannot check-in a completed or cancelled appointment.'))
            # Ensure patient/partner is set before check-in
            if not event.ths_patient_id or not event.partner_id:
                raise UserError(_("Cannot check in appointment without a Patient and Customer assigned."))
                # Ensure practitioner is selected if medical appointment
            if event.appointment_type_id and event.appointment_type_id.schedule_based_on == 'resources' and not event.ths_practitioner_id:
                raise UserError(
                    _("Cannot check in: A Service Provider must be selected for this medical appointment type."))
            event.write({
                'appointment_status': 'checked_in',
                'ths_check_in_time': now
            })
            event._create_medical_encounter()  # Trigger encounter creation
        return True

    def action_start_consultation(self):
        """ Set status to In Progress. """
        for event in self:
            if event.appointment_status != 'checked_in':
                raise UserError(_("Patient must be Checked In before starting the consultation."))
            if not event.ths_encounter_id:
                event._create_medical_encounter()
            if not event.ths_encounter_id:
                raise UserError(_("Cannot start consultation: Medical Encounter is missing."))

            event.write({'appointment_status': 'in_progress'})
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
            if event.appointment_status not in ('checked_in', 'in_progress'):
                raise UserError(_("Appointment must be Checked In or In Progress to mark as Completed."))
            if not event.ths_encounter_id:
                raise UserError(_("Cannot complete appointment: Corresponding Medical Encounter not found."))

            event.write({
                'appointment_status': 'completed',
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
                    # _logger.error("Error calling action_ready_for_billing from appointment %s: %s", event.id, e)
                    raise UserError(_("An error occurred while preparing items for billing: %s", e))
        return True

    def action_cancel_appointment(self):
        """ Open wizard to select cancellation reason and set status. """
        # TODO: Implement wizard for reason selection. Needs a transient model.
        # For now, simple cancel:
        # Determine blame based on simple logic or default
        blame_reason = self.env['ths.medical.cancellation.reason'].search([('blame', '=', 'clinic')], limit=1)
        vals_to_write = {
            'appointment_status': 'cancelled_by_clinic',
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
        self.write({'appointment_status': 'no_show'})
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
        practitioner_employee = self.ths_practitioner_id  # This is now computed from ths_practitioner_id
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
                # _logger.info(f"Appointment {self.id}: Linked existing encounter {existing.name}.")
            else:
                try:
                    encounter_vals = self._prepare_encounter_vals()
                    # Use sudo for encounter creation
                    new_encounter = Encounter.sudo().create(encounter_vals)
                    # Use sudo to write back link
                    self.sudo().write({'ths_encounter_id': new_encounter.id})
                    # _logger.info(f"Appointment {self.id}: Created new encounter {new_encounter.name}.")
                    self.message_post(body=_("Medical Encounter %s created.", new_encounter._get_html_link()),
                                      message_type='comment', subtype_xmlid='mail.mt_note')
                except Exception as e:
                    # _logger.error(f"Failed to create encounter for appointment {self.id}: {e}")
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

    @api.model
    def _cron_send_appointment_reminders(self):
        """Send appointment reminders 24 hours before"""
        tomorrow = fields.Datetime.now() + timedelta(days=1)
        tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0)
        tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)

        appointments = self.search([
            ('start', '>=', tomorrow_start),
            ('start', '<=', tomorrow_end),
            ('appointment_status', 'in', ['draft', 'confirmed']),
            ('ths_patient_id', '!=', False),
        ])

        template = self.env.ref('ths_medical_base.email_template_appointment_reminder', False)
        if not template:
            _logger.warning("Appointment reminder email template not found")
            return

        for appointment in appointments:
            try:
                template.send_mail(appointment.id, force_send=True)
                appointment.message_post(
                    body=_("Reminder sent to %s") % appointment.partner_id.name,
                    message_type='notification'
                )
            except Exception as e:
                _logger.error("Failed to send reminder for appointment %s: %s", appointment.id, e)
