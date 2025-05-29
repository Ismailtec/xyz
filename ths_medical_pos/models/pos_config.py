# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosConfig(models.Model):
    """
    Extension of pos.config to support medical POS functionality
    """
    _inherit = 'pos.config'

    # Medical appointment settings
    appointment_default_duration = fields.Float(
        string='Default Appointment Duration (minutes)',
        default=30.0,
        help="Default duration for new appointments created from POS (in minutes)"
    )
    allow_walk_in_appointments = fields.Boolean(
        string='Allow Walk-in Appointments',
        default=True,
        help="Allow creating walk-in appointments from POS"
    )
    require_practitioner_selection = fields.Boolean(
        string='Require Practitioner Selection',
        default=False,
        help="Require selecting a practitioner for all appointments"
    )

    # Medical billing settings
    auto_load_pending_items = fields.Boolean(
        string='Auto-load Pending Items',
        default=True,
        help="Automatically load pending medical items when customer is selected"
    )
    commission_calculation_method = fields.Selection([
        ('none', 'No Commission'),
        ('fixed', 'Fixed Percentage'),
        ('product_based', 'Product-based'),
        ('practitioner_based', 'Practitioner-based'),
    ], string='Commission Calculation', default='none',
        help="Method for calculating practitioner commissions")

    default_medical_category_id = fields.Many2one(
        'pos.category',
        string='Default Medical Category',
        help="Default POS category for medical products"
    )

    # Patient management settings
    require_patient_selection = fields.Boolean(
        string='Require Patient Selection',
        default=True,
        help="Require selecting a patient for medical transactions"
    )
    auto_create_medical_records = fields.Boolean(
        string='Auto-create Medical Records',
        default=False,
        help="Automatically create medical encounter records from POS orders"
    )
    default_appointment_type_id = fields.Many2one(
        'ths.appointment.type',
        string='Default Appointment Type',
        help="Default type for appointments created from POS"
    )

    # Integration settings
    sync_with_calendar = fields.Boolean(
        string='Sync with Calendar',
        default=True,
        help="Synchronize appointments with calendar system"
    )
    notification_settings = fields.Selection([
        ('none', 'No Notifications'),
        ('basic', 'Basic Notifications'),
        ('advanced', 'Advanced Notifications'),
    ], string='Notification Level', default='basic',
        help="Level of notifications to send for appointment events")

    # Medical staff access
    allowed_practitioner_ids = fields.Many2many(
        'hr.employee',
        'pos_config_practitioner_rel',
        'config_id',
        'employee_id',
        string='Allowed Practitioners',
        domain=[('ths_is_medical', '=', True)],
        help="Practitioners allowed to be selected in this POS"
    )

    # Room management
    allowed_room_ids = fields.Many2many(
        'ths.treatment.room',
        'pos_config_room_rel',
        'config_id',
        'room_id',
        string='Available Rooms',
        domain=[('active', '=', True)],
        help="Treatment rooms available for booking in this POS"
    )

    @api.onchange('appointment_default_duration')
    def _onchange_appointment_default_duration(self):
        """Validate appointment default duration"""
        if self.appointment_default_duration and self.appointment_default_duration <= 0:
            return {
                'warning': {
                    'title': "Invalid Duration",
                    'message': "Appointment duration must be positive."
                }
            }

    def get_medical_pos_config(self):
        """
        Get medical-specific configuration for POS session
        Used by JavaScript to configure medical POS functionality
        """
        self.ensure_one()

        return {
            'appointment_default_duration': self.appointment_default_duration,
            'allow_walk_in_appointments': self.allow_walk_in_appointments,
            'require_practitioner_selection': self.require_practitioner_selection,
            'auto_load_pending_items': self.auto_load_pending_items,
            'commission_calculation_method': self.commission_calculation_method,
            'require_patient_selection': self.require_patient_selection,
            'auto_create_medical_records': self.auto_create_medical_records,
            'sync_with_calendar': self.sync_with_calendar,
            'notification_settings': self.notification_settings,
            'default_appointment_type_id': self.default_appointment_type_id.id if self.default_appointment_type_id else False,
            'default_medical_category_id': self.default_medical_category_id.id if self.default_medical_category_id else False,
            'allowed_practitioner_ids': self.allowed_practitioner_ids.ids,
            'allowed_room_ids': self.allowed_room_ids.ids,
        }

    @api.model
    def get_pos_ui_medical_data(self, config_id):
        """
        Get medical data needed for POS UI initialization
        """
        config = self.browse(config_id)

        # Get practitioners
        practitioner_domain = [('ths_is_medical', '=', True)]
        if config.allowed_practitioner_ids:
            practitioner_domain.append(('id', 'in', config.allowed_practitioner_ids.ids))

        practitioners = self.env['hr.employee'].search_read(
            practitioner_domain,
            ['id', 'name', 'partner_id', 'resource_id'],
            limit=100
        )

        # Get treatment rooms
        room_domain = [('active', '=', True)]
        if config.allowed_room_ids:
            room_domain.append(('id', 'in', config.allowed_room_ids.ids))

        rooms = self.env['ths.treatment.room'].search_read(
            room_domain,
            ['id', 'name', 'code', 'room_type', 'default_duration'],
            limit=50
        )

        # Get appointment types
        appointment_types = self.env['ths.appointment.type'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'code', 'default_duration', 'color'],
            limit=20
        )

        # Get partner types for patient filtering
        partner_types = self.env['ths.partner.type'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'code'],
        )

        return {
            'medical_config': config.get_medical_pos_config(),
            'practitioners': practitioners,
            'treatment_rooms': rooms,
            'appointment_types': appointment_types,
            'partner_types': partner_types,
        }


class PosSession(models.Model):
    """
    Extension of pos.session to support medical data loading
    """
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """Extend partner loading to include medical fields"""
        result = super()._loader_params_res_partner()

        # Add medical fields to partner loading
        medical_fields = [
            'ths_partner_type_id',
            'ths_pet_owner_id',
            'ths_is_medical_client',
        ]

        if 'search_params' in result and 'fields' in result['search_params']:
            result['search_params']['fields'].extend(medical_fields)

        return result

    def _loader_params_hr_employee(self):
        """Load employee data with medical fields"""
        result = super()._loader_params_hr_employee()

        # Add medical fields
        medical_fields = [
            'ths_is_medical',
            'resource_id',
            'partner_id',
        ]

        if 'search_params' in result and 'fields' in result['search_params']:
            result['search_params']['fields'].extend(medical_fields)

        return result

    def _get_pos_ui_res_partner(self, params):
        """Override to ensure medical partner data is loaded"""
        partners = super()._get_pos_ui_res_partner(params)

        # Load additional medical data if needed
        for partner in partners:
            if partner.get('ths_partner_type_id'):
                # Ensure partner type name is available
                partner_type = self.env['ths.partner.type'].browse(partner['ths_partner_type_id'][0])
                partner['ths_partner_type_name'] = partner_type.name

        return partners

    def _get_pos_ui_hr_employee(self, params):
        """Load employee data with medical information"""
        employees = super()._get_pos_ui_hr_employee(params)

        # Add medical practitioners to the list
        if self.config_id.allowed_practitioner_ids:
            medical_employees = self.env['hr.employee'].search_read(
                [('id', 'in', self.config_id.allowed_practitioner_ids.ids)],
                params.get('search_params', {}).get('fields', []),
            )

            # Merge with existing employees (avoid duplicates)
            existing_ids = {emp['id'] for emp in employees}
            for med_emp in medical_employees:
                if med_emp['id'] not in existing_ids:
                    employees.append(med_emp)

        return employees

    def get_medical_data_for_pos(self):
        """Get all medical data needed for POS operation"""
        self.ensure_one()

        return self.config_id.get_pos_ui_medical_data(self.config_id.id)
