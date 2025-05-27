from odoo import models, fields


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    appointment_status = fields.Selection(selection_add=[('invoice', 'Invoiced')])
