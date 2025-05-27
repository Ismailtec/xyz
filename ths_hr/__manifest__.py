# -*- coding: utf-8 -*-
{
    'name': 'Techouse HR Enhancements',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Customization',
    'summary': 'Adds inventory locations, analytic accounts, department codes/sequences, and custom fields for HR.',
    'description': """
This module enhances Odoo's HR functionality by:
- Adding 'is_employee' flag to Partner Types (defined in ths_base).
- Adding Department Code and auto-managed Sequence.
- Automatically creating dedicated inventory loss locations for Employees under their Department location.
- Automatically creating inventory locations for Departments under a parent 'Departments' location.
- Automatically creating Analytic Accounts for Departments and Employees, maintaining hierarchy.
- Adding 'Part Time' and 'External Contractor' options to Employee Type selection.
- Establishing link between Employee creation and Partner creation/update (setting Partner Type to 'Employee').
- Providing retroactive actions to create missing locations/accounts/sequences.
- Defining specific HR User and Manager groups for security.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'base',
        'hr',  # Human Resources base
        'stock',  # For stock.location
        'account',  # For account.analytic.account/group
        'ths_base', # Dependency for ths.partner.type and base structures
        'analytic', # Often needed explicitly for analytic features
        # 'inventory' dependency is usually covered by 'stock'
    ],
    'data': [
        # Security
        'security/hr_security.xml',
        'security/ir.model.access.csv',

        # Data files
        'data/ir_sequence.xml',
        'data/partner_type_data.xml',
        'data/stock_location_data.xml',
        'data/account_analytics_data.xml',

        # Views
        'views/partner_type.xml',
        'views/hr_department.xml',
        'views/hr_employee.xml',
        'views/res_partner.xml',
        #'views/hr_employee_type.xml',
        #'views/hr_menus.xml',  # Menu for Employee Sub Type
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
