# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CalendarEvent(models.Model):
    """
    Extension of calendar.event to support medical appointments
    """
    _inherit = 'calendar.event'

    # Medical appointment fields
    ths_patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        domain=[('ths_partner_type_id.name', '=', 'Pet')],
        help="The patient (pet) for this medical appointment"
    )
    ths_practitioner_id = fields.Many2one(
        'hr.employee',
        string='Practitioner',
        domain=[('ths_is_medical', '=', True)],
        help="Medical practitioner assigned to this appointment"
    )
    ths_room_id = fields.Many2one(
        'ths.treatment.room',
        string='Treatment Room',
        domain=[('active', '=', True)],
        help="Treatment room reserved for this appointment"
    )

    # Appointment status specific to medical workflow
    ths_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('billed', 'Billed'),
        ('cancelled_by_patient', 'Cancelled by Patient'),
        ('cancelled_by_clinic', 'Cancelled by Clinic'),
        ('no_show', 'No Show'),
    ], string='Medical Status', default='scheduled',
        help="Status of the medical appointment")

    # Medical specific fields
    ths_reason_for_visit = fields.Text(
        string='Reason for Visit',
        help="Primary reason for the medical appointment"
    )
    appointment_type_id = fields.Many2one(
        'ths.appointment.type',
        string='Appointment Type',
        help="Type of medical appointment (consultation, surgery, etc.)"
    )
    ths_is_walk_in = fields.Boolean(
        string='Walk-in Appointment',
        default=False,
        help="True if this is a walk-in appointment"
    )

    # Related medical encounter
    medical_encounter_id = fields.Many2one(
        'ths.medical.encounter',
        string='Medical Encounter',
        help="Medical encounter record created from this appointment"
    )

    # Computed fields for medical context
    is_medical_appointment = fields.Boolean(
        string='Is Medical',
        compute='_compute_is_medical_appointment',
        store=True,
        help="True if this is a medical appointment"
    )
    patient_owner_id = fields.Many2one(
        'res.partner',
        string='Patient Owner',
        related='ths_patient_id.ths_pet_owner_id',
        store=True,
        help="Owner of the patient"
    )

    @api.depends('ths_patient_id')
    def _compute_is_medical_appointment(self):
        """Compute if this is a medical appointment"""
        for event in self:
            event.is_medical_appointment = bool(event.ths_patient_id)

    @api.onchange('ths_patient_id')
    def _onchange_ths_patient_id(self):
        """Update partner when patient changes"""
        if self.ths_patient_id:
            # Set the patient owner as the main partner
            if self.ths_patient_id.ths_pet_owner_id:
                self.partner_id = self.ths_patient_id.ths_pet_owner_id
                # Add both owner and patient to partner_ids
                partner_ids = [self.ths_patient_id.ths_pet_owner_id.id, self.ths_patient_id.id]
                if self.ths_practitioner_id and self.ths_practitioner_id.partner_id:
                    partner_ids.append(self.ths_practitioner_id.partner_id.id)
                self.partner_ids = [(6, 0, list(set(partner_ids)))]

    @api.onchange('ths_practitioner_id')
    def _onchange_ths_practitioner_id(self):
        """Add practitioner to attendees when selected"""
        if self.ths_practitioner_id and self.ths_practitioner_id.partner_id:
            current_partner_ids = [p.id for p in self.partner_ids]
            if self.ths_practitioner_id.partner_id.id not in current_partner_ids:
                current_partner_ids.append(self.ths_practitioner_id.partner_id.id)
                self.partner_ids = [(6, 0, current_partner_ids)]

    @api.onchange('ths_room_id')
    def _onchange_ths_room_id(self):
        """Set default duration based on room when room changes"""
        if self.ths_room_id and self.ths_room_id.default_duration and not self.duration:
            self.duration = self.ths_room_id.default_duration

    def action_check_in(self):
        """Check in patient for appointment"""
        self.ensure_one()
        if self.ths_status not in ('scheduled', 'confirmed'):
            raise ValidationError(_("Only scheduled or confirmed appointments can be checked in."))

        self.ths_status = 'checked_in'
        return True

    def action_start_appointment(self):
        """Start the medical appointment"""
        self.ensure_one()
        if self.ths_status not in ('scheduled', 'confirmed', 'checked_in'):
            raise ValidationError(_("Cannot start appointment from current status."))

        self.ths_status = 'in_progress'

        # Create medical encounter if not exists
        if not self.medical_encounter_id and self.ths_patient_id:
            encounter_vals = {
                'appointment_id': self.id,
                'patient_id': self.ths_patient_id.id,
                'owner_id': self.partner_id.id if self.partner_id else False,
                'practitioner_id': self.ths_practitioner_id.id if self.ths_practitioner_id else False,
                'room_id': self.ths_room_id.id if self.ths_room_id else False,
                'encounter_date': self.start,
                'encounter_type': self._get_encounter_type(),
                'chief_complaint': self.ths_reason_for_visit or '',
                'state': 'in_progress',
            }
            encounter = self.env['ths.medical.encounter'].create(encounter_vals)
            self.medical_encounter_id = encounter.id

        return True

    def action_complete_appointment(self):
        """Complete the medical appointment"""
        self.ensure_one()
        if self.ths_status != 'in_progress':
            raise ValidationError(_("Only in-progress appointments can be completed."))

        self.ths_status = 'completed'

        # Complete related medical encounter
        if self.medical_encounter_id:
            self.medical_encounter_id.action_complete_encounter()

        return True

    def action_mark_no_show(self):
        """Mark appointment as no-show"""
        self.ensure_one()
        if self.ths_status not in ('scheduled', 'confirmed'):
            raise ValidationError(_("Only scheduled or confirmed appointments can be marked as no-show."))

        self.ths_status = 'no_show'
        return True

    def action_cancel_appointment(self):
        """Cancel the appointment"""
        self.ensure_one()
        if self.ths_status in ('completed', 'billed'):
            raise ValidationError(_("Completed or billed appointments cannot be cancelled."))

        self.ths_status = 'cancelled_by_clinic'

        # Cancel related medical encounter
        if self.medical_encounter_id:
            self.medical_encounter_id.action_cancel_encounter()

        return True

    def action_create_encounter(self):
        """Manually create medical encounter from appointment"""
        self.ensure_one()
        if not self.ths_patient_id:
            raise ValidationError(_("Cannot create encounter without a patient."))

        if self.medical_encounter_id:
            # Open existing encounter
            return {
                'type': 'ir.actions.act_window',
                'name': _('Medical Encounter'),
                'res_model': 'ths.medical.encounter',
                'res_id': self.medical_encounter_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Create new encounter
        encounter_vals = {
            'appointment_id': self.id,
            'patient_id': self.ths_patient_id.id,
            'owner_id': self.partner_id.id if self.partner_id else False,
            'practitioner_id': self.ths_practitioner_id.id if self.ths_practitioner_id else False,
            'room_id': self.ths_room_id.id if self.ths_room_id else False,
            'encounter_date': self.start,
            'encounter_type': self._get_encounter_type(),
            'chief_complaint': self.ths_reason_for_visit or '',
            'state': 'scheduled',
        }

        encounter = self.env['ths.medical.encounter'].create(encounter_vals)
        self.medical_encounter_id = encounter.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Medical Encounter'),
            'res_model': 'ths.medical.encounter',
            'res_id': encounter.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_encounter_type(self):
        """Determine encounter type based on appointment"""
        if self.appointment_type_id:
            # Map appointment type to encounter type
            type_mapping = {
                'consultation': 'consultation',
                'examination': 'examination',
                'surgery': 'surgery',
                'follow_up': 'follow_up',
                'vaccination': 'vaccination',
                'checkup': 'checkup',
                'dental': 'dental',
                'grooming': 'grooming',
            }
            return type_mapping.get(self.appointment_type_id.code, 'consultation')
        return 'consultation'

    @api.constrains('ths_room_id', 'start', 'stop')
    def _check_room_availability(self):
        """Check room availability for medical appointments"""
        for event in self:
            if event.ths_room_id and event.start and event.stop:
                # Check for overlapping appointments in the same room
                overlapping = self.search([
                    ('id', '!=', event.id),
                    ('ths_room_id', '=', event.ths_room_id.id),
                    ('start', '<', event.stop),
                    ('stop', '>', event.start),
                    ('ths_status', 'not in', ('cancelled_by_patient', 'cancelled_by_clinic', 'no_show'))
                ])

                if overlapping:
                    raise ValidationError(
                        _("Room '%(room)s' is already booked during this time period. "
                          "Conflicting appointment: %(conflict)s",
                          room=event.ths_room_id.name,
                          conflict=overlapping[0].display_name)
                    )

    @api.model
    def create(self, vals):
        """Override create to handle medical appointment specifics"""
        result = super().create(vals)

        # Auto-confirm medical appointments if configured
        if result.ths_patient_id and result.ths_status == 'scheduled':
            # You can add auto-confirmation logic here if needed
            pass

        return result

    def write(self, vals):
        """Override write to handle status changes"""
        result = super().write(vals)

        # Handle status change notifications or other logic
        if 'ths_status' in vals:
            for event in self:
                if event.ths_patient_id:
                    event._handle_status_change(vals['ths_status'])

        return result

    def _handle_status_change(self, new_status):
        """Handle medical appointment status changes"""
        # This method can be extended to send notifications,
        # update related records, etc.
        if new_status == 'confirmed':
            # Send confirmation notification
            pass
        elif new_status == 'cancelled_by_clinic':
            # Send cancellation notification
            pass
        elif new_status == 'completed':
            # Trigger billing process
            pass

    @api.model
    def get_medical_appointments_for_pos(self, date_from=None, date_to=None, partner_id=None):
        """
        Get medical appointments for POS integration

        :param date_from: Filter from this date
        :param date_to: Filter to this date
        :param partner_id: Filter by patient owner
        :return: List of appointment data
        """
        domain = [('ths_patient_id', '!=', False)]

        if date_from:
            domain.append(('start', '>=', date_from))
        if date_to:
            domain.append(('start', '<=', date_to))
        if partner_id:
            domain.append(('partner_id', '=', partner_id))

        appointments = self.search(domain, order='start DESC', limit=100)

        return appointments.read([
            'id', 'display_name', 'start', 'stop', 'ths_status',
            'ths_patient_id', 'partner_id', 'ths_practitioner_id',
            'ths_room_id', 'ths_reason_for_visit', 'medical_encounter_id'
        ])

    def name_get(self):
        """Custom name_get for medical appointments"""
        result = []
        for event in self:
            if event.ths_patient_id:
                # Medical appointment format
                date_str = event.start.strftime('%m/%d %H:%M') if event.start else ''
                name = f"{event.ths_patient_id.name} - {date_str}"
                if event.ths_practitioner_id:
                    name += f" ({event.ths_practitioner_id.name})"
            else:
                # Regular calendar event
                name = event.name or _('Calendar Event')

            result.append((event.id, name))

        return result


class ThsAppointmentType(models.Model):
    """
    Model for different types of medical appointments
    """
    _name = 'ths.appointment.type'
    _description = 'Medical Appointment Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Appointment Type',
        required=True,
        help="Name of the appointment type"
    )
    code = fields.Char(
        string='Code',
        required=True,
        help="Short code for the appointment type"
    )
    description = fields.Text(
        string='Description',
        help="Description of this appointment type"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Used to order appointment types"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this type will be hidden"
    )

    # Duration and scheduling
    default_duration = fields.Float(
        string='Default Duration (hours)',
        default=1.0,
        help="Default duration for this type of appointment"
    )
    color = fields.Integer(
        string='Color',
        help="Color for calendar display"
    )

    # Requirements
    requires_room = fields.Boolean(
        string='Requires Room',
        default=True,
        help="Whether this appointment type requires a treatment room"
    )
    requires_practitioner = fields.Boolean(
        string='Requires Practitioner',
        default=True,
        help="Whether this appointment type requires a practitioner"
    )

    # Product and pricing
    default_product_ids = fields.Many2many(
        'product.product',
        'appointment_type_product_rel',
        'type_id',
        'product_id',
        string='Default Products/Services',
        domain=[('available_in_pos', '=', True)],
        help="Default products/services for this appointment type"
    )

    @api.constrains('default_duration')
    def _check_default_duration(self):
        """Validate default duration"""
        for record in self:
            if record.default_duration <= 0:
                raise ValidationError(_("Default duration must be positive."))

    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure appointment type codes are unique"""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_("Appointment type code must be unique."))

    def name_get(self):
        """Custom name_get to include code"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}" if record.code else record.name
            result.append((record.id, name))
        return result
