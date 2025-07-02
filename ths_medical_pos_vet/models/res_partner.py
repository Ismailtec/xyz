# -*- coding: utf-8 -*-

from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_pet_badge_data(self):
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'species': self.ths_species_id.name if self.ths_species_id else '',
            'color': self.ths_species_id.color or 0,
        }

    @api.model
    def _load_pos_data_fields(self, config_id):
        base_fields = super()._load_pos_data_fields(config_id)
        return base_fields + [
            'is_pet', 'is_pet_owner', 'ths_pet_owner_id',
            'ths_species_id', 'ths_deceased', 'pet_membership_ids'
        ]

    @api.model
    def _load_pos_data(self, data):
        result = super()._load_pos_data(data)
        partner_ids = [record['id'] for record in result['data']]
        partners = self.browse(partner_ids)
        badge_data = [partner.get_pet_badge_data() for partner in partners if partner.is_pet]

        result['badge_data'] = badge_data
        result['fields'] = list(set(result['fields'] + [
            'is_pet', 'is_pet_owner', 'ths_pet_owner_id',
            'ths_species_id', 'ths_deceased', 'pet_membership_ids'
        ]))

        return result