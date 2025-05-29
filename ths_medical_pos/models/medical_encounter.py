# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ThsMedicalEncounter(models.Model):
    """
    Model for managing medical encounters/visits
    Links appointments with medical records and billing
    """
    _name = 'ths.medical.encounter'
    _description = 'Medical Encounter'
    _order = 'encounter_date desc, id desc'
    _rec_name = 'display_name'

    # Basic identification
    name = fields.Char(
        string='Encounter Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help="Unique identifier for the medical encounter"
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        help="Computed display name for the encounter"
    )

    # Core encounter information
    encounter_date = fields.Datetime(
        string='Encounter Date',
        required=True,
        default=fields.Datetime.now,
        help="Date and time of the medical encounter"
    )

    # Patient and owner information
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        domain=[('ths_partner_type_id.name', '=', 'Pet')],
        help="The patient (pet) being treated"
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        required=True,
        help="The owner of the patient"
    )

    # Medical staff
    practitioner_id = fields.Many2one(
        'hr.employee',
        string='Primary Practitioner',
        required=True,
        domain=[('ths_is_medical', '=', True)],
        help="Primary medical practitioner for this encounter"
    )
    assistant_ids = fields.Many2many(
        'hr.employee',
        'encounter_assistant_rel',
        'encounter_id',
        'employee_id',
        string='Medical Assistants',
        domain=[('ths_is_medical', '=', True)],
        help="Medical assistants involved in the encounter"
    )

    # Appointment linkage
    appointment_id = fields.Many2one(
        'calendar.event',
        string='Related Appointment',
        help="Calendar appointment that initiated this encounter"
    )
    room_id = fields.Many2one(
        'ths.treatment.room',
        string='Treatment Room',
        help="Room where the encounter took place"
    )

    # Encounter status and type
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('billed', 'Billed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', required=True,
        help="Current status of the encounter")

    encounter_type = fields.Selection([
        ('consultation', 'Consultation'),
        ('examination', 'Examination'),
        ('surgery', 'Surgery'),
        ('follow_up', 'Follow-up'),
        ('emergency', 'Emergency'),
        ('vaccination', 'Vaccination'),
        ('checkup', 'Routine Checkup'),
        ('dental', 'Dental'),
        ('grooming', 'Grooming'),
        ('other', 'Other'),
    ], string='Encounter Type', default='consultation',
        help="Type of medical encounter")

    # Clinical information
    chief_complaint = fields.Text(
        string='Chief Complaint',
        help="Primary reason for the visit as described by the owner"
    )
    history_present_illness = fields.Text(
        string='History of Present Illness',
        help="Detailed history of the current medical issue"
    )
    physical_examination = fields.Text(
        string='Physical Examination',
        help="Results of physical examination"
    )
    assessment = fields.Text(
        string='Assessment',
        help="Medical assessment and diagnosis"
    )
    treatment_plan = fields.Text(
        string='Treatment Plan',
        help="Planned treatments and interventions"
    )
    notes = fields.Text(
        string='Additional Notes',
        help="Any additional notes about the encounter"
    )

    # Vital signs and measurements
    temperature = fields.Float(
        string='Temperature (°F)',
        help="Patient's body temperature in Fahrenheit"
    )
    weight = fields.Float(
        string='Weight (lbs)',
        help="Patient's weight in pounds"
    )
    heart_rate = fields.Integer(
        string='Heart Rate (BPM)',
        help="Heart rate in beats per minute"
    )
    respiratory_rate = fields.Integer(
        string='Respiratory Rate',
        help="Respiratory rate per minute"
    )

    # Billing and financial
    pending_amount = fields.Float(
        string='Pending Amount',
        compute='_compute_billing_amounts',
        store=True,
        help="Amount still pending billing"
    )

    # Timing fields
    start_time = fields.Datetime(
        string='Start Time',
        help="When the encounter actually started"
    )
    end_time = fields.Datetime(
        string='End Time',
        help="When the encounter was completed"
    )
    duration = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True,
        help="Duration of the encounter in hours"
    )

    # Company and access control
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help="Company that owns this encounter"
    )

    @api.model
    def create(self, vals):
        """Override create to generate sequence number"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('ths.medical.encounter') or _('New')

        # Auto-set owner from patient if not provided
        if 'patient_id' in vals and not vals.get('owner_id'):
            patient = self.env['res.partner'].browse(vals['patient_id'])
            if patient.ths_pet_owner_id:
                vals['owner_id'] = patient.ths_pet_owner_id.id

        return super().create(vals)

    @api.depends('patient_id', 'encounter_date', 'name')
    def _compute_display_name(self):
        """Compute display name for the encounter"""
        for record in self:
            if record.patient_id and record.encounter_date:
                date_str = record.encounter_date.strftime('%Y-%m-%d')
                record.display_name = f"{record.name} - {record.patient_id.name} ({date_str})"
            elif record.patient_id:
                record.display_name = f"{record.name} - {record.patient_id.name}"
            else:
                record.display_name = record.name or _('Medical Encounter')

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Compute encounter duration"""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds() / 3600.0  # Convert to hours
            else:
                record.duration = 0.0

    @api.depends('pending_items_ids', 'pos_order_ids')
    def _compute_billing_amounts(self):
        """Compute billing amounts"""
        for record in self:
            # Calculate pending amount
            pending_amount = sum(record.pending_items_ids.filtered(
                lambda x: x.state == 'pending'
            ).mapped('total_amount'))
            record.pending_amount = pending_amount

            # Calculate billed amount from POS orders
            billed_amount = 0.0
            for order in record.pos_order_ids:
                # Sum order lines that reference this encounter
                encounter_lines = order.lines.filtered(
                    lambda l: l.ths_encounter_id and l.ths_encounter_id.id == record.id
                )
                billed_amount += sum(encounter_lines.mapped('price_subtotal_incl'))

            record.total_billed_amount = billed_amount

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Set owner when patient changes"""
        if self.patient_id and self.patient_id.ths_pet_owner_id:
            self.owner_id = self.patient_id.ths_pet_owner_id

    @api.onchange('appointment_id')
    def _onchange_appointment_id(self):
        """Populate fields from appointment"""
        if self.appointment_id:
            appointment = self.appointment_id
            if appointment.ths_patient_id:
                self.patient_id = appointment.ths_patient_id
            if appointment.partner_id:
                self.owner_id = appointment.partner_id
            if appointment.ths_practitioner_id:
                self.practitioner_id = appointment.ths_practitioner_id
            if appointment.ths_room_id:
                self.room_id = appointment.ths_room_id
            if appointment.start:
                self.encounter_date = appointment.start
            if appointment.ths_reason_for_visit:
                self.chief_complaint = appointment.ths_reason_for_visit

    def action_start_encounter(self):
        """Mark encounter as started"""
        self.ensure_one()
        if self.state != 'scheduled':
            raise ValidationError(_("Only scheduled encounters can be started."))

        self.write({
            'state': 'in_progress',
            'start_time': fields.Datetime.now(),
        })

        # Update related appointment status
        if self.appointment_id:
            self.appointment_id.ths_status = 'in_progress'

        return True

    def action_complete_encounter(self):
        """Mark encounter as completed"""
        self.ensure_one()
        if self.state not in ('scheduled', 'in_progress'):
            raise ValidationError(_("Only scheduled or in-progress encounters can be completed."))

        values = {
            'state': 'completed',
            'end_time': fields.Datetime.now(),
        }

        # Set start time if not already set
        if not self.start_time:
            values['start_time'] = self.encounter_date or fields.Datetime.now()

        self.write(values)

        # Update related appointment status
        if self.appointment_id:
            self.appointment_id.ths_status = 'completed'

        return True

    def action_mark_billed(self):
        """Mark encounter as fully billed"""
        self.ensure_one()
        if self.state != 'completed':
            raise ValidationError(_("Only completed encounters can be marked as billed."))

        # Check if there are pending items
        if self.pending_items_ids.filtered(lambda x: x.state == 'pending'):
            raise ValidationError(_("Cannot mark as billed while there are pending items."))

        self.state = 'billed'

        # Update related appointment status
        if self.appointment_id:
            self.appointment_id.ths_status = 'billed'

        return True

    def action_cancel_encounter(self):
        """Cancel the encounter"""
        self.ensure_one()
        if self.state == 'billed':
            raise ValidationError(_("Billed encounters cannot be cancelled."))

        self.state = 'cancelled'

        # Cancel pending items
        self.pending_items_ids.filtered(lambda x: x.state == 'pending').action_mark_cancelled()

        # Update related appointment status
        if self.appointment_id:
            self.appointment_id.ths_status = 'cancelled_by_clinic'

        return True

    def action_add_pending_item(self):
        """Action to add a new pending item"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Pending Item'),
            'res_model': 'ths.pending.pos.item',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_encounter_id': self.id,
                'default_partner_id': self.owner_id.id,
                'default_patient_id': self.patient_id.id,
                'default_practitioner_id': self.practitioner_id.id,
            },
        }

    def action_view_pending_items(self):
        """Action to view pending items"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ths_medical_pos.action_pending_pos_item")
        action['domain'] = [('encounter_id', '=', self.id)]
        action['context'] = {'default_encounter_id': self.id}
        return action

    def action_view_pos_orders(self):
        """Action to view related POS orders"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("point_of_sale.action_pos_pos_form")
        action['domain'] = [('id', 'in', self.pos_order_ids.ids)]
        return action

    def create_pending_items(self, items_data):
        """
        Create multiple pending items for this encounter

        :param items_data: List of dictionaries with item data
        :return: Created pending items recordset
        """
        self.ensure_one()

        pending_items = self.env['ths.pending.pos.item']
        for item_data in items_data:
            vals = {
                'encounter_id': self.id,
                'partner_id': self.owner_id.id,
                'patient_id': self.patient_id.id,
                'practitioner_id': self.practitioner_id.id,
                **item_data
            }
            pending_items |= pending_items.create(vals)

        return pending_items

    @api.model
    def get_encounters_for_pos(self, partner_id=None, date_from=None, limit=50):
        """
        Get encounters for POS integration

        :param partner_id: Filter by owner partner ID
        :param date_from: Filter encounters from this date
        :param limit: Maximum records to return
        :return: List of encounter data
        """
        domain = [('state', 'in', ('completed', 'billed'))]

        if partner_id:
            domain.append(('owner_id', '=', partner_id))

        if date_from:
            domain.append(('encounter_date', '>=', date_from))

        encounters = self.search(domain, limit=limit, order='encounter_date desc')

        return encounters.read([
            'id', 'display_name', 'encounter_date', 'patient_id',
            'owner_id', 'practitioner_id', 'state', 'total_billed_amount',
            'pending_amount'
        ])

    @api.constrains('start_time', 'end_time')
    def _check_encounter_times(self):
        """Validate encounter times"""
        for record in self:
            if record.start_time and record.end_time:
                if record.end_time <= record.start_time:
                    raise ValidationError(_("End time must be after start time."))

    @api.constrains('temperature')
    def _check_temperature(self):
        """Validate temperature readings"""
        for record in self:
            if record.temperature and (record.temperature < 90 or record.temperature > 110):
                raise ValidationError(_("Temperature seems abnormal. Please verify the reading."))

    @api.constrains('weight')
    def _check_weight(self):
        """Validate weight readings"""
        for record in self:
            if record.weight and record.weight <= 0:
                raise ValidationError(_("Weight must be positive."))

    def _check_access_rights(self, operation,):
        """Override to ensure proper access control"""
        # Allow POS users to read encounters for billing
        if operation == 'read' and self.env.user.has_group('point_of_sale.group_pos_user'):
            return True
        return super()._check_access(operation)
