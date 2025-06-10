# -*- coding: utf-8 -*-

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """ Inherit to add medical/vet fields """
        params = super()._loader_params_res_partner()
        fields_to_load = params['search_params']['fields']
        # Ensure fields for vet/membership/etc are included
        fields_to_load.extend([
            'ths_partner_type_id',
            'is_patient',  # Boolean field for filtering patients
            'ths_pet_owner_id',
            'ref',  # Patient file number
            'mobile',  # Patient contact
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
            'department_id',  # Might be useful for medical department filtering
            # Add other fields if needed for display/filtering in POS
            'name',
            'id'
        ])
        params['search_params']['fields'] = list(set(fields_to_load))
        # Define the domain to load only active medical staff with resources
        employee_domain = params['search_params'].get('domain', [])
        employee_domain.extend([
            ('resource_id', '!=', False),
            ('ths_is_medical', '=', True),
            ('active', '=', True)  # Only active employees
        ])
        params['search_params']['domain'] = employee_domain
        return params

    # Add Loader for ths.treatment.room
    def _loader_params_ths_treatment_room(self):
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

    # Override _pos_ui_models_to_load to include ths.treatment.room
    def _pos_ui_models_to_load(self):
        """ Add ths.treatment.room to the list of models loaded by POS """
        models_to_load = super()._pos_ui_models_to_load()
        # Add our custom models if they aren't already included via dependencies/other modules
        medical_models = [
            'ths.treatment.room',
            'ths.pending.pos.item',  # For pending items functionality
        ]

        for model in medical_models:
            if model not in models_to_load:
                models_to_load.append(model)

        return models_to_load

    # Optional: Define how partner types are loaded if not done elsewhere
    # def _loader_params_ths_partner_type(self):
    #     return {'search_params': {'fields': ['id', 'name', 'is_patient', 'is_employee']}}

    # Add loader for pending POS items
    def _loader_params_ths_pending_pos_item(self):
        """ Define fields and domain for loading pending POS items """
        return {
            'search_params': {
                'domain': [('state', '=', 'pending')],  # Only load pending items
                'fields': [
                    'id', 'name', 'encounter_id', 'appointment_id',
                    'partner_id', 'patient_id', 'product_id', 'description',
                    'qty', 'price_unit', 'discount', 'practitioner_id',
                    'commission_pct', 'state', 'notes'
                ],
                'order': 'create_date desc',  # Show newest first
                'limit': 1000,  # Reasonable limit for POS performance
            },
        }

    # Add get_pos_ui_ths_treatment_room method for loading
    def get_pos_ui_ths_treatment_room(self, params):
        """ Method called by POS UI to load treatment rooms """
        return self.env['ths.treatment.room'].search_read(**params['search_params'])

    def get_pos_ui_ths_pending_pos_item(self, params):
        """ Method called by POS UI to load pending POS items """
        return self.env['ths.pending.pos.item'].search_read(**params['search_params'])

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

    # --- HUMAN MEDICAL SPECIFIC METHODS ---
    def _get_patients_for_pos(self):
        """
        Get patients that should be available in POS for human medical practice
        """
        return self.env['res.partner'].search([
            ('ths_partner_type_id.is_patient', '=', True),
            ('active', '=', True)
        ])

    def _get_medical_staff_for_pos(self):
        """
        Get medical staff that should be available in POS
        """
        return self.env['hr.employee'].search([
            ('ths_is_medical', '=', True),
            ('resource_id', '!=', False),
            ('active', '=', True)
        ])

    def _get_pending_items_count(self):
        """
        Get count of pending medical items for dashboard/monitoring
        """
        return self.env['ths.pending.pos.item'].search_count([
            ('state', '=', 'pending')
        ])

    # --- HELPER METHODS FOR POS MEDICAL INTEGRATION ---
    def _validate_medical_pos_setup(self):
        """
        Validate that medical POS setup is correct
        Returns list of warnings/errors for medical POS configuration
        """
        issues = []

        # Check if medical staff exists
        medical_staff_count = self.env['hr.employee'].search_count([
            ('ths_is_medical', '=', True),
            ('active', '=', True)
        ])
        if medical_staff_count == 0:
            issues.append("No active medical staff found. Add medical practitioners to use medical POS features.")

        # Check if treatment rooms exist
        treatment_rooms_count = self.env['ths.treatment.room'].search_count([
            ('active', '=', True)
        ])
        if treatment_rooms_count == 0:
            issues.append(
                "No active treatment rooms found. Consider adding treatment rooms for better appointment management.")

        # Check if patient types are configured
        patient_types_count = self.env['ths.partner.type'].search_count([
            ('is_patient', '=', True)
        ])
        if patient_types_count == 0:
            issues.append("No patient partner types configured. Set up partner types for proper patient management.")

        return issues

    # TODO: Add methods for real-time updates and monitoring
    def _get_real_time_pending_items(self):
        """
        Get real-time count of pending items for POS dashboard
        """
        # TODO: Could be enhanced with real-time notifications
        return self._get_pending_items_count()

    def _refresh_medical_data_in_pos(self):
        """
        Refresh medical data in active POS sessions
        """
        # TODO: Implement real-time data refresh for medical information
        pass
