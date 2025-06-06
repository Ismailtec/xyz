# -*- coding: utf-8 -*-

from odoo import models, api, _


class CalendarEvent(models.Model):
    """
    Extension of calendar.event to support medical POS integration
    Minimal extension - only adds the action method to open gantt view
    """
    _inherit = 'calendar.event'

    def action_open_medical_gantt_view(self):
        """
        Action to open the medical appointments gantt view from POS
        Uses existing gantt view from ths_medical_base module
        """
        return {
            'name': _('Medical Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'views': [(self.env.ref("ths_medical_base.calendar_event_medical_resource_gantt_ths_medical").id, "gantt")],
            'target': 'current',
            'context': {
                'appointment_booking_gantt_show_all_resources': True,
                'active_model': 'appointment.type',
                'default_partner_ids': [],
                'default_appointment_status': 'scheduled',
                'default_schedule_based_on': 'resources',
            },
            'domain': [('ths_practitioner_id', '!=', False)],  # Only show medical appointments
        }

    def action_open_medical_form_view(self):
        """
        Action to open appointment form view for editing from POS
        Uses existing form view from ths_medical_base module
        """
        return {
            'name': _('Edit Medical Appointment'),
            'target': 'new',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'views': [(self.env.ref('ths_medical_base.view_calendar_event_form_inherit_ths_medical').id, 'form')],
            'res_id': self.id,
        }
