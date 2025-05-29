# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ThsTreatmentRoom(models.Model):
    """
    Model for managing medical treatment rooms
    Integrates with resource.resource for calendar booking functionality
    """
    _name = 'ths.treatment.room'
    _description = 'Medical Treatment Room'
    _order = 'sequence, name'
    _rec_name = 'name'

    # Basic information
    name = fields.Char(
        string='Room Name',
        required=True,
        help="Name of the treatment room"
    )
    code = fields.Char(
        string='Room Code',
        help="Short code for the room (e.g., TR01, SURG1)"
    )
    description = fields.Text(
        string='Description',
        help="Detailed description of the room and its capabilities"
    )

    # Sequencing and organization
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Used to order rooms in lists and selections"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, the room will be hidden from most views"
    )

    # Resource integration for calendar booking
    resource_id = fields.Many2one(
        'resource.resource',
        string='Resource',
        required=True,
        ondelete='cascade',
        help="Associated resource for calendar booking system"
    )

    # Room characteristics
    room_type = fields.Selection([
        ('consultation', 'Consultation Room'),
        ('examination', 'Examination Room'),
        ('surgery', 'Surgery Room'),
        ('treatment', 'Treatment Room'),
        ('diagnostic', 'Diagnostic Room'),
        ('recovery', 'Recovery Room'),
        ('isolation', 'Isolation Room'),
        ('other', 'Other'),
    ], string='Room Type', default='consultation',
        help="Type of medical room")

    capacity = fields.Integer(
        string='Capacity',
        default=1,
        help="Maximum number of patients that can be treated simultaneously"
    )

    # Equipment and features
    equipment_ids = fields.Many2many(
        'ths.medical.equipment',
        'room_equipment_rel',
        'room_id',
        'equipment_id',
        string='Available Equipment',
        help="Medical equipment available in this room"
    )

    # Room features (stored as JSON or separate model if complex)
    has_sink = fields.Boolean(
        string='Has Sink',
        default=True,
        help="Room has a sink for hand washing"
    )
    has_computer = fields.Boolean(
        string='Has Computer',
        default=False,
        help="Room has a computer workstation"
    )
    has_exam_table = fields.Boolean(
        string='Has Exam Table',
        default=True,
        help="Room has an examination table"
    )
    is_sterile = fields.Boolean(
        string='Sterile Environment',
        default=False,
        help="Room maintains sterile conditions for surgery"
    )

    # Location and access
    floor = fields.Char(
        string='Floor',
        help="Floor or level where the room is located"
    )
    wing = fields.Char(
        string='Wing/Section',
        help="Wing or section of the building"
    )
    access_notes = fields.Text(
        string='Access Notes',
        help="Special instructions for accessing the room"
    )

    # Booking and availability
    default_duration = fields.Float(
        string='Default Duration (hours)',
        default=1.0,
        help="Default appointment duration for this room in hours"
    )
    advance_booking_days = fields.Integer(
        string='Advance Booking Days',
        default=30,
        help="How many days in advance can this room be booked"
    )

    # Statistics and computed fields
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_appointment_count',
        help="Number of appointments scheduled for this room"
    )

    # Company and multi-tenancy
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help="Company that owns this room"
    )

    @api.model
    def create(self, vals):
        """Override create to automatically create associated resource"""
        # Create resource if not provided
        if not vals.get('resource_id'):
            resource_vals = {
                'name': vals.get('name', 'Treatment Room'),
                'resource_type': 'material',  # Rooms are material resources
                'company_id': vals.get('company_id', self.env.company.id),
                'active': vals.get('active', True),
            }
            resource = self.env['resource.resource'].create(resource_vals)
            vals['resource_id'] = resource.id

        return super().create(vals)

    def write(self, vals):
        """Override write to sync with resource"""
        result = super().write(vals)

        # Sync certain fields with resource
        resource_vals = {}
        if 'name' in vals:
            resource_vals['name'] = vals['name']
        if 'active' in vals:
            resource_vals['active'] = vals['active']

        if resource_vals:
            for record in self:
                if record.resource_id:
                    record.resource_id.write(resource_vals)

        return result

    def unlink(self):
        """Override unlink to handle resource cleanup"""
        resources_to_delete = self.mapped('resource_id')
        result = super().unlink()
        # Delete associated resources
        resources_to_delete.unlink()
        return result

    def _compute_appointment_count(self):
        """Compute number of appointments for this room"""
        for room in self:
            # Count appointments where this room is assigned
            appointments = self.env['calendar.event'].search_count([
                ('ths_room_id', '=', room.id),
                ('start', '>=', fields.Datetime.now()),
            ])
            room.appointment_count = appointments

    @api.constrains('capacity')
    def _check_capacity(self):
        """Validate room capacity"""
        for room in self:
            if room.capacity < 1:
                raise ValidationError(_("Room capacity must be at least 1."))

    @api.constrains('default_duration')
    def _check_default_duration(self):
        """Validate default duration"""
        for room in self:
            if room.default_duration <= 0:
                raise ValidationError(_("Default duration must be positive."))

    def action_view_appointments(self):
        """Action to view appointments for this room"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("calendar.action_calendar_event")
        action['domain'] = [('ths_room_id', '=', self.id)]
        action['context'] = {
            'default_ths_room_id': self.id,
            'search_default_future': 1,
        }
        return action

    def action_book_appointment(self):
        """Action to book a new appointment in this room"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Book Appointment'),
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ths_room_id': self.id,
                'default_duration': self.default_duration,
            },
        }

    @api.model
    def get_available_rooms(self, start_datetime, end_datetime, room_type=None):
        """
        Get rooms available for booking during specified time period

        :param start_datetime: Start of desired booking period
        :param end_datetime: End of desired booking period
        :param room_type: Optional filter by room type
        :return: Available rooms recordset
        """
        domain = [('active', '=', True)]

        if room_type:
            domain.append(('room_type', '=', room_type))

        # Get all rooms matching criteria
        all_rooms = self.search(domain)

        # Filter out rooms with conflicting appointments
        conflicting_appointments = self.env['calendar.event'].search([
            ('ths_room_id', 'in', all_rooms.ids),
            ('start', '<', end_datetime),
            ('stop', '>', start_datetime),
        ])

        conflicted_room_ids = conflicting_appointments.mapped('ths_room_id.id')
        available_rooms = all_rooms.filtered(lambda r: r.id not in conflicted_room_ids)

        return available_rooms

    def check_availability(self, start_datetime, end_datetime):
        """
        Check if room is available during specified time period

        :param start_datetime: Start of desired booking period
        :param end_datetime: End of desired booking period
        :return: True if available, False if conflicted
        """
        self.ensure_one()

        conflicting_count = self.env['calendar.event'].search_count([
            ('ths_room_id', '=', self.id),
            ('start', '<', end_datetime),
            ('stop', '>', start_datetime),
        ])

        return conflicting_count == 0

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced name search to include room code"""
        if args is None:
            args = []

        domain = args.copy()
        if name:
            domain += ['|', ('name', operator, name), ('code', operator, name)]

        records = self.search(domain, limit=limit)
        return records.name_get()

    def name_get(self):
        """Custom name_get to show code and name"""
        result = []
        for record in self:
            if record.code:
                name = f"[{record.code}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result
