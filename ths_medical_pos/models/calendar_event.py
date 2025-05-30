# -*- coding: utf-8 -*-

from odoo import models, api, _


class CalendarEvent(models.Model):
    """
    Extension of calendar.event for POS integration
    Note: The main medical fields are defined in ths_medical_base
    This extension only adds POS-specific functionality
    """
    _inherit = 'calendar.event'

    @api.model
    def get_medical_appointments_for_pos(self, date_from=None, date_to=None, partner_id=None, limit=500):
        """
        Get medical appointments for POS integration

        :param date_from: Filter from this date
        :param date_to: Filter to this date
        :param partner_id: Filter by patient owner
        :param limit: Maximum records to return
        :return: List of appointment data
        """
        domain = []

        if date_from:
            domain.append(('start', '>=', date_from))
        if date_to:
            domain.append(('start', '<=', date_to))
        if partner_id:
            domain.append(('partner_id', '=', partner_id))

        appointments = self.search(domain, order='start DESC', limit=limit)

        return appointments.read([
            'id', 'display_name', 'name', 'start', 'stop', 'duration',
            'partner_id', 'ths_patient_id', 'ths_practitioner_id',
            'ths_room_id', 'ths_status', 'ths_reason_for_visit',
            'appointment_type_id', 'ths_is_walk_in', 'allday'
        ])

    def action_add_to_pos_order(self):
        """
        Action to add appointment-related items to POS order
        This can be called from appointment detail popup
        """
        self.ensure_one()

        # This method can be extended to automatically add
        # pending items related to this appointment to POS order

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Appointment items can now be processed in POS.'),
                'type': 'success',
            }
        }
