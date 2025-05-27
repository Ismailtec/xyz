# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical Commissions',
    'version': '18.0.1.0.0',
    'category': 'Medical/Commissions',
    'summary': 'Generate and manage commissions for medical staff based on POS sales.',
    'description': """
Calculates commission lines for medical providers based on processed Point of Sale order lines containing provider and commission rate information from the medical workflow.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'ths_medical_pos',  # Needs the fields added to pos.order.line
        'ths_hr',  # Needs hr.employee for provider link
        'account',  # For currency/monetary fields
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/medical_commission_line_views.xml',
        'views/commission_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
