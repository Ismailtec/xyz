# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical Base',
    'version': '18.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Adds base medical-related flags to HR models.',
    'description': """
Adds base models and logic for medical workflows:
- Medical flags for Employee Types and Employees.
- Product Sub Type classification system.
- Treatment Room management with resource linking.
- Daily Encounter grouping.
- Medical Encounter tracking linked to appointments.
- Pending POS Item model for billing bridge.
- Extends Calendar Event for medical context.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'hr',  # Dependency for hr.employee and hr.employee.type
        'base',
        'mail',
        'ths_hr',  # Dependency for potential future interactions or structure
        'ths_base',
        'stock',
        'product',
        'account',
        'analytic',
        'appointment',
        'calendar',
        'resource',
        'web_gantt_extension',
        'point_of_sale',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Data Files
        'data/ir_sequence.xml',
        'data/hr_employee_type_config_data.xml',
        'data/partner_type_data.xml',
        'data/product_sub_type_data.xml',
        # Views
        'views/hr_employee.xml', # Adds medical flag & calendar flag to Employee views
        'views/hr_employee_type_config.xml',
        'views/treatment_room.xml',  # New Treatment Room views
        'views/product_sub_type.xml', # Views for the NEW sub-type model
        'views/daily_encounter.xml', # New Daily Encounter views
        'views/medical_encounter.xml',  # New Encounter views
        'views/pending_pos_item.xml', # New Pending POS Item views
        'views/medical_menus.xml', # Menu for Treatment Rooms etc.
        'views/appointment_type.xml',
        'views/appointment_resource.xml',
        'views/product.xml', # Adds sub-type field to Product views & domain logic
        'views/hr_department.xml', # Adds medical flag to Department views
        'views/calendar_event.xml', # Inherited Calendar Event view
        'views/partner_type.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
