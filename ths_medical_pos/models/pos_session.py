# -*- coding: utf-8 -*-

from odoo import models, api, fields


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """ Inherit to add medical/vet fields """
        params = super()._loader_params_res_partner()
        fields_to_load = params['search_params']['fields']
        # Ensure fields for vet/membership/etc are included
        fields_to_load.extend([
            'ths_partner_type_id',
            'ths_pet_owner_id',
            'membership_state',
            'membership_start',
            'membership_stop'
        ])
        params['search_params']['fields'] = list(set(fields_to_load))
        return params

    def _loader_params_hr_employee(self):
        """ Inherit to add medical fields and filter for practitioners """
        params = super()._loader_params_hr_employee()
        fields_to_load = params['search_params']['fields']
        fields_to_load.extend([
            'ths_is_medical',
            'resource_id',
            # Add other fields if needed for display/filtering in POS
            'name',
            'id'
        ])
        params['search_params']['fields'] = list(set(fields_to_load))
        # Define the domain to load only active medical staff with resources
        # Combine with existing domain if any
        employee_domain = params['search_params'].get('domain', [])
        employee_domain.extend([
            ('resource_id', '!=', False),
            ('ths_is_medical', '=', True),
            ('active', '=', True)  # Only active employees
        ])
        params['search_params']['domain'] = employee_domain
        return params

    # Add Loader for ths.treatment.room
    @staticmethod
    def _loader_params_ths_treatment_room():
        """ Define fields and domain for loading rooms into POS """
        return {
            'search_params': {
                'domain': [
                    ('resource_id', '!=', False),  # Must be a schedulable resource
                    ('active', '=', True)  # Must be active
                ],
                'fields': ['id', 'name', 'resource_id'],  # Load ID, name, and resource link
            },
        }

    # Add Loader for calendar.event (medical appointments)
    @staticmethod
    def _loader_params_calendar_event():
        """ Define fields and domain for loading medical appointments into POS """
        return {
            'search_params': {
                'domain': [
                    ('ths_patient_id', '!=', False),  # Only medical appointments
                    ('start', '>=', '2024-01-01 00:00:00'),  # Recent appointments only
                ],
                'fields': [
                    'id', 'name', 'display_name', 'start', 'stop', 'duration',
                    'partner_id', 'ths_patient_id', 'ths_practitioner_id',
                    'ths_room_id', 'ths_status', 'ths_reason_for_visit',
                    'appointment_type_id', 'ths_is_walk_in', 'allday'
                ],
                'order': 'start DESC',
                'limit': 500,  # Reasonable limit for POS performance
            },
        }

    # Add Loader for ths.partner.type
    @staticmethod
    def _loader_params_ths_partner_type():
        """ Load partner types for patient filtering """
        return {
            'search_params': {
                'domain': [('active', '=', True)],
                'fields': ['id', 'name', 'code', 'is_patient', 'is_employee'],
            },
        }

    # Override _pos_ui_models_to_load to include ths.treatment.room
    def _pos_ui_models_to_load(self):
        """ Add ths.treatment.room to the list of models loaded by POS """
        models_to_load = super()._pos_ui_models_to_load()
        # Add our custom models if they aren't already included via dependencies/other modules
        medical_models = [
            'ths.treatment.room',
            'calendar.event',  # For appointments
            'ths.partner.type',  # For patient types
        ]
        for model in medical_models:
            if model not in models_to_load:
                models_to_load.append(model)

        if 'ths.treatment.room' not in models_to_load:
            models_to_load.append('ths.treatment.room')
        # Ensure partner types are loaded if ths_base doesn't handle it via pos context
        # if 'ths.partner.type' not in models_to_load:
        #     models_to_load.append('ths.partner.type')
        return models_to_load

    # Optional: Define how partner types are loaded if not done elsewhere
    # def _loader_params_ths_partner_type(self):
    #     return {'search_params': {'fields': ['id', 'name', 'is_patient', 'is_employee']}}

    # Add get_pos_ui_ths_treatment_room method for loading
    def get_pos_ui_ths_treatment_room(self, params):
        """ Method called by POS UI to load treatment rooms """
        return self.env['ths.treatment.room'].search_read(**params['search_params'])

    def get_pos_ui_calendar_event(self, params):
        """ Method called by POS UI to load medical appointments """
        return self.env['calendar.event'].search_read(**params['search_params'])

    def get_pos_ui_ths_partner_type(self, params):
        """ Method called by POS UI to load partner types """
        return self.env['ths.partner.type'].search_read(**params['search_params'])

    # Override get_pos_ui_hr_employee to use the modified loader params
    # This ensures our domain/fields are used when POS loads employees
    def get_pos_ui_hr_employee(self, params):
        """ Method called by POS UI to load employees """
        # Note: This method name might vary slightly based on Odoo version / other modules
        # Verify the exact method name used by your POS version to load employees if issues arise.
        # For v17+, using the loader_params dictionary might be sufficient without needing this explicit override.
        # However, explicit override guarantees usage.
        loader_params = self._loader_params_hr_employee()
        return self.env['hr.employee'].search_read(**loader_params['search_params'])

    # Override get_pos_ui_res_partner if needed to ensure vet fields load
    def get_pos_ui_res_partner(self, params):
        loader_params = self._loader_params_res_partner()
        return self.env['res.partner'].search_read(**loader_params['search_params'])

    @api.model
    def get_pos_ui_medical_config(self):
        """ Get medical-specific configuration for POS """
        return {
            'appointment_default_duration': 30,  # Default 30 minutes
            'show_medical_screens': True,
            'load_appointments': True,
            'max_appointments_to_load': 500,
        }
