# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.osv import expression
import json
import logging

_logger = logging.getLogger(__name__)


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    department_ids = fields.Many2many(
        'hr.department',
        'appointment_type_hr_department_rel',
        'appointment_type_id',
        'department_id',
        string='Departments',
        domain="[('ths_is_medical_dep', '=', True)]",
        help="Departments whose staff and rooms can be booked for this appointment type."
    )

    ths_practitioner_ids = fields.Many2many(
        'appointment.resource',
        string='Service Providers (from Resources)',
        compute='_compute_filtered_medical_resources',
        readonly=True,
        store=False,
        help="View of service providers (Appointment Resources with category 'practitioner') from the main 'Resources' list."
    )

    ths_location_ids = fields.Many2many(
        'appointment.resource',
        string='Rooms (from Resources)',
        compute='_compute_filtered_medical_resources',
        readonly=True,
        store=False,
        help="View of rooms (Appointment Resources with category 'location') from the main 'Resources' list."
    )

    ths_source_department_id = fields.Many2one(
        'hr.department',
        string='Source Department',
        copy=False,
        index=True,
        ondelete='set null',
        help="Department that auto-generated this appointment type, if applicable.",
    )
    ths_resource_domain_char = fields.Char(
        compute='_compute_resource_domain',
        string='Resource Selection Domain',
        store=False,
    )
    # Computed fields for smart buttons
    ths_practitioner_count = fields.Integer(compute='_compute_counts', string='Service Provider Count')
    ths_location_count = fields.Integer(compute='_compute_counts', string='Room Count')

    @api.depends('ths_practitioner_ids', 'ths_location_ids')
    def _compute_counts(self):
        """Compute counts for smart buttons"""
        for record in self:
            record.ths_practitioner_count = len(record.ths_practitioner_ids)
            record.ths_location_count = len(record.ths_location_ids)

    @api.depends('resource_ids', 'resource_ids.ths_resource_category')
    def _compute_filtered_medical_resources(self):
        for record in self:
            practitioners = record.resource_ids.filtered(lambda r: r.ths_resource_category == 'practitioner')
            locations = record.resource_ids.filtered(lambda r: r.ths_resource_category == 'location')
            record.ths_practitioner_ids = [(6, 0, practitioners.ids)]
            record.ths_location_ids = [(6, 0, locations.ids)]
            _logger.info(
                f"AptType {record.id}: Filtered {len(practitioners)} practitioners, {len(locations)} locations from resource_ids.")

    @api.depends('department_ids', 'schedule_based_on', 'resource_ids')
    def _compute_resource_domain(self):
        """
        Computes the domain for the 'resource_ids' field selection pop-up.
        Filters by selected departments and excludes already selected resources.
        """
        for record in self:
            try:
                if record.schedule_based_on != 'resources':
                    record.ths_resource_domain_char = '[["id", "=", false]]'
                    continue

                AppointmentResource = record.env['appointment.resource']
                base_domain = [
                    ['active', '=', True],
                    ['ths_resource_category', 'in', ['practitioner', 'location']],
                ]

                practitioner_ids = AppointmentResource.search([
                    ('employee_id.department_id', 'in', record.department_ids.ids),
                    ('ths_resource_category', '=', 'practitioner'),
                    ('active', '=', True),
                ]).ids if record.department_ids else []

                location_ids = AppointmentResource.search([
                    ('ths_treatment_room_id.department_id', 'in', record.department_ids.ids),
                    ('ths_resource_category', '=', 'location'),
                    ('active', '=', True),
                ]).ids if record.department_ids else []

                candidate_ids = set(practitioner_ids + location_ids)
                already_selected = set(record.resource_ids.ids)
                remaining_ids = list(candidate_ids - already_selected)

                domain = base_domain + [['id', 'in', remaining_ids]] if remaining_ids else [['id', '=', False]]
                record.ths_resource_domain_char = json.dumps(domain)

            except Exception as e:
                _logger.error(f"[Domain Compute Error] {e}")
                record.ths_resource_domain_char = '[["id", "=", false]]'

    @api.onchange('schedule_based_on', 'department_ids')
    def _onchange_department_or_schedule_type(self):
        if self.schedule_based_on == 'resources':
            AppointmentResource = self.env['appointment.resource']
            resources_to_set = self.env['appointment.resource']

            if self.department_ids:
                practitioner_ars = AppointmentResource.search([
                    ('employee_id.department_id', 'in', self.department_ids.ids),
                    ('ths_resource_category', '=', 'practitioner'),
                    ('active', '=', True)
                ])
                location_ars = AppointmentResource.search([
                    ('ths_treatment_room_id.department_id', 'in', self.department_ids.ids),
                    ('ths_resource_category', '=', 'location'),
                    ('active', '=', True)
                ])
                resources_to_set = practitioner_ars | location_ars

            self.resource_ids = [(6, 0, resources_to_set.ids)]

            if self.ths_source_department_id and not self.department_ids:
                self.department_ids = [(4, self.ths_source_department_id.id, 0)]
        else:
            self.department_ids = [(5, 0, 0)]
            self.resource_ids = [(5, 0, 0)]

    @api.onchange('department_ids', 'resource_ids', 'schedule_based_on')
    def _onchange_resource_ids_domain(self):
        if self.schedule_based_on != 'resources':
            return {'domain': {'resource_ids': [('id', '=', False)]}}

        AppointmentResource = self.env['appointment.resource']

        practitioner_ids = AppointmentResource.search([
            ('employee_id.department_id', 'in', self.department_ids.ids),
            ('ths_resource_category', '=', 'practitioner'),
            ('active', '=', True)
        ]).ids if self.department_ids else []

        location_ids = AppointmentResource.search([
            ('ths_treatment_room_id.department_id', 'in', self.department_ids.ids),
            ('ths_resource_category', '=', 'location'),
            ('active', '=', True)
        ]).ids if self.department_ids else []

        all_visible = set(practitioner_ids + location_ids)
        already_selected = set(self.resource_ids.ids)
        final_visible = list(all_visible - already_selected)

        return {
            'domain': {
                'resource_ids': [('id', 'in', final_visible)] if final_visible else [('id', '=', False)]
            }
        }

    # Create and Write methods
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('schedule_based_on') == 'resources':
                vals['staff_user_ids'] = [(5, 0, 0)]
        return super(AppointmentType, self).create(vals_list)

    def write(self, vals):
        # If department_ids or schedule_based_on changes, the onchange handles resource_ids.
        # If schedule_based_on is being set to 'resources', ensure staff_user_ids is cleared.
        if vals.get('schedule_based_on') == 'resources':
            vals['staff_user_ids'] = [(5, 0, 0)]
        elif 'schedule_based_on' in vals and vals.get('schedule_based_on') != 'resources':
            # If changing away from 'resources', clear resource_ids and department_ids
            vals['resource_ids'] = [(5, 0, 0)]
            vals['department_ids'] = [(5, 0, 0)]

        res = super(AppointmentType, self).write(vals)

        # If schedule_based_on was changed to 'resources' in this write,
        # and department_ids were already set (or also set in this write),
        # the onchange might not have fully populated resource_ids if it ran before departments were set.
        # Re-triggering onchange or re-populating might be needed if write order is an issue.
        # For now, relying on onchange for subsequent UI interactions.
        # If 'department_ids' was in vals, the onchange should have run.
        if 'department_ids' in vals and self.schedule_based_on == 'resources':
            self._onchange_department_or_schedule_type()  # Re-trigger to ensure population

        return res
