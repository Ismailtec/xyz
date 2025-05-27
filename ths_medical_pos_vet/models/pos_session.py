# -*- coding: utf-8 -*-

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """ Inherit to add medical/vet fields to partner data loaded in POS """
        params = super()._loader_params_res_partner()
        fields_to_load = params['search_params']['fields']
        # Add fields needed for selection, display, and owner linking
        fields_to_load.extend([
            'ths_partner_type_id',
            'ths_pet_owner_id',  # Needed to link Pet -> Owner
            'membership_state',  # From previous step
            'membership_start',  # From previous step
            'membership_stop'  # From previous step
        ])
        # Ensure unique fields
        params['search_params']['fields'] = list(set(fields_to_load))
        # Optional: Add a domain filter if you only want to load specific partner types?
        # params['search_params']['domain'] = ...
        return params

    def _loader_params_hr_employee(self):
        """ Inherit to add medical fields to employee data loaded in POS """
        params = super()._loader_params_hr_employee()
        fields_to_load = params['search_params']['fields']
        # Add fields needed for filtering practitioners
        fields_to_load.extend([
            'ths_is_medical',
            'resource_id'  # Needed to check if they are bookable resources
        ])
        params['search_params']['fields'] = list(set(fields_to_load))
        # Add domain to only load relevant employees (medical staff with resources)
        params['search_params']['domain'] = params['search_params'].get('domain', []) + [
            ('resource_id', '!=', False),
            ('ths_is_medical', '=', True)
        ]
        return params

    # Optional: Loader for ths.treatment.room if needed frequently, otherwise RPC is fine
    # def _loader_params_ths_treatment_room(self):
    #     return {
    #         'search_params': {
    #             'domain': [('resource_id', '!=', False), ('active', '=', True)],
    #             'fields': ['id', 'name'],
    #         },
    #     }

    # Optional: Add the model to the list loaded by POS
    # def _pos_ui_models_to_load(self):
    #      models = super()._pos_ui_models_to_load()
    #      models.append('ths.treatment.room')
    #      return models
