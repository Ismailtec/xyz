# -*- coding: utf-8 -*-

from odoo import api, models


class ResPartner(models.Model):
	_inherit = 'res.partner'

	@api.model
	def _load_pos_data_domain(self, data):
		domain = super()._load_pos_data_domain(data)
		domain += [('active', '=', True), ('ths_partner_type_id.is_customer', '=', True)]
		return domain

	@api.model
	def _load_pos_data_fields(self, config_id):
		base_fields = super()._load_pos_data_fields(config_id)
		return base_fields + ['ths_partner_type_id']

	def _load_pos_data(self, data):
		result = super()._load_pos_data(data)
		result['fields'] = list(set(result['fields'] + ['ths_partner_type_id']))
		return result

	# def action_view_pos_order(self):
	#     """  This function returns an action that displays the pos orders from partner.  """
	#     action = self.env['ir.actions.act_window']._for_xml_id('point_of_sale.action_pos_pos_form')
	#     if self.is_company:
	#         action['domain'] = [('partner_id.commercial_partner_id', '=', self.id)]
	#     else:
	#         action['domain'] = [('partner_id', '=', self.id)]
	#     return action
	#
	# def open_commercial_entity(self):
	#     return {
	#         **super().open_commercial_entity(),
	#         **({'target': 'new'} if self.env.context.get('target') == 'new' else {}),
	#     }