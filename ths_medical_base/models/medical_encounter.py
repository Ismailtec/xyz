# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
# from odoo.exceptions import UserError
# from datetime import datetime, date

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

    encounter_date = fields.Date(
        string='Encounter Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
        help="Date for this encounter - one encounter per partner per date"
    )

    appointment_ids = fields.One2many(
        'calendar.event',
        'encounter_id',
        string='Appointments',
        help="All appointments linked to this encounter"
    )

    # For medical: partner_id = patient (same person receiving care and paying)
    partner_id = fields.Many2one(
        'res.partner',
        string='Patient',  # In medical, patient is the customer
        # related='appointment_id.partner_id',
        store=True,
        index=True,
        # readonly=True,
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
        # readonly=True,
        help="Patients participating in this encounter. In human medical practice, these are the same people as in partner_id."
    )

    # TODO: Add computed fields for primary patient info for backward compatibility
    patient_ref = fields.Char(string="Patient File", related='patient_ids.ref', store=False, readonly=True)
    patient_mobile = fields.Char(string="Patient Mobile", related='patient_ids.mobile', store=False, readonly=True)

    practitioner_id = fields.Many2one(
        'appointment.resource',
        string='Service Provider',
        domain="[('ths_resource_category', '=', 'practitioner')]",
        # related='appointment_id.ths_practitioner_id',
        store=True,
        index=True,
        readonly=True
    )
    room_id = fields.Many2one(
        'appointment.resource',
        string='Room',
        related='appointment_ids.ths_room_id',
        store=True,
        index=True,
        # readonly=True
    )
    date_start = fields.Datetime(
        string='Start Time',
        related='appointment_ids.start',
        store=True,
        # readonly=True
    )
    date_end = fields.Datetime(
        string='End Time',
        related='appointment_ids.stop',
        store=True,
        # readonly=True
    )
    appointment_status = fields.Selection(
        related='appointment_ids.appointment_status',
        string='Appointment Status',
        store=True,
        readonly=True,
        help="Status of the related appointment"
    )

    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='Status', default='in_progress', index=True, tracking=True, copy=False)

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

    @api.model
    def _get_encounter_domain_by_context(self):
        domain = []
        date_filter = self.env.context.get('search_encounter_date_range')
        today = fields.Date.context_today(self)

        if date_filter == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            domain += [('encounter_date', '>=', start_week), ('encounter_date', '<=', end_week)]

        elif date_filter == 'last_week':
            start_last_week = today - timedelta(days=today.weekday() + 7)
            end_last_week = start_last_week + timedelta(days=6)
            domain += [('encounter_date', '>=', start_last_week), ('encounter_date', '<=', end_last_week)]

        return domain

    @api.model
    def _find_or_create_daily_encounter(self, partner_id, encounter_date=None):
        """Find existing encounter for partner+date or create new one"""
        if not encounter_date:
            encounter_date = fields.Date.context_today(self)

        # Search for existing encounter
        encounter = self.search([
            ('partner_id', '=', partner_id),
            ('encounter_date', '=', encounter_date)
        ], limit=1)

        if encounter:
            return encounter

        # Create new encounter
        # partner = self.env['res.partner'].browse(partner_id)
        encounter_vals = {
            'partner_id': partner_id,
            'patient_ids': [(4, partner_id)],  # For human medical, patient = partner
            'encounter_date': encounter_date,
            'state': 'in_progress'
        }

        return self.create(encounter_vals)

    # --- Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Assign sequence on creation. """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('medical.encounter') or _('New')

            # Ensure encounter_date is set
            if not vals.get('encounter_date'):
                vals['encounter_date'] = fields.Date.context_today(self)

        return super(ThsMedicalEncounter, self).create(vals_list)

    _sql_constraints = [
        ('unique_partner_date', 'unique(partner_id, encounter_date)',
         'Only one encounter per partner per date is allowed!'),
    ]

    # --- Actions ---
    def action_view_appointments(self):
        """View all appointments for this encounter"""
        self.ensure_one()
        return {
            'name': _('Appointments'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'list,form',
            'domain': [('encounter_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_view_pos_orders(self):
        """View all POS orders for this encounter"""
        self.ensure_one()
        return {
            'name': _('POS Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('encounter_id', '=', self.id)],
            'context': {'create': False}
        }

    def add_service_to_encounter(self, service_model, service_id):
        """Generic method to link any service to this encounter"""
        self.ensure_one()
        service = self.env[service_model].browse(service_id)
        if hasattr(service, 'encounter_id'):
            service.encounter_id = self.id
        return True

# TODO: Add encounter analytics dashboard for daily metrics
# TODO: Implement encounter merge functionality for same-day duplicates
# TODO: Add encounter templates for common service combinations
# TODO: Implement encounter archiving for old records after 1 year
# TODO: Add encounter automatic closure after 7 days of inactivity
# TODO: Implement encounter follow-up scheduling system
# TODO: Add encounter insurance integration for claims
# TODO: Implement encounter inventory tracking for consumed items
# TODO: Create encounter performance metrics per practitioner
# TODO: Add encounter timezone handling for multi-location clinics
