# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ThsDailyEncounter(models.Model):
    """ Groups clinical encounters by day for overview. """
    _name = 'ths.daily.encounter'
    _description = 'Daily Encounters'
    _order = 'date desc'  # Show most recent days first

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
        readonly=True,  # Date shouldn't change after creation
        default=fields.Date.context_today,
        copy=False
    )
    encounter_ids = fields.One2many(
        'ths.medical.base.encounter',
        'daily_id',
        string='Encounters'
    )
    encounter_count = fields.Integer(
        string='Encounter Count',
        compute='_compute_encounter_count'
    )
    # company_id = fields.Many2one(  # Add company field
    #     'res.company', string='Company',
    #     default=lambda self: self.env.company, readonly=True)
    #
    # _sql_constraints = [
    #     ('date_company_uniq', 'unique (date, company_id)',
    #      'Only one daily encounter record allowed per date per company!'),
    # ]

    @api.depends('date')
    def _compute_name(self):
        """ Compute name based on date. """
        for record in self:
            record.name = _("Encounters %s", fields.Date.to_string(record.date)) if record.date else _(
                "Encounters Undated")

    @api.depends('encounter_ids')
    def _compute_encounter_count(self):
        """ Compute number of encounters for the day. """
        for record in self:
            record.encounter_count = len(record.encounter_ids)

    def action_view_encounters(self):
        """ Action to view the encounters linked to this daily record. """
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'ths_medical_base.action_ths_medical_encounter')  # Use correct action ID
        action['domain'] = [('id', 'in', self.encounter_ids.ids)]
        # Ensure context is a dict
        ctx = {}
        if isinstance(action.get('context'), dict):
            ctx = action['context'].copy()
        elif isinstance(action.get('context'), str):
            try:
                ctx = eval(action['context'])
            except Exception:
                pass  # Keep empty context on error
        # Set default daily_id if creating new from this view
        ctx['default_daily_id'] = self.id
        action['context'] = ctx
        return action
