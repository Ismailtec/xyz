# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical POS Integration',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale/Medical',
    'summary': 'Integrates medical encounters and billing with Point of Sale.',
    'description': """
Provides the bridge between backend medical encounters (ths_medical_base) and the Point of Sale interface.
- Extends POS models to link orders/lines to pending medical items.
- Adds fields for patient, provider, and commission tracking on POS lines.
- Includes backend logic to update medical records upon POS order completion.
- Adds frontend JS/OWL components to fetch and manage medical billing items in POS.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'point_of_sale',
        'ths_medical_base',  # Depends on the medical base for encounter/pending items
        'ths_hr',  # Needed for hr.employee (practitioner) access
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'point_of_sale.assets': [
            # 1. Load FullCalendar Library CSS & JS FIRST
            ('include', 'web._assets_helpers'),
            'ths_medical_pos/static/lib/fullcalendar/index.global.min.js',

            # Buttons
            'ths_medical_pos/static/src/components/pending_items_button/pending_items_button.js',
            'ths_medical_pos/static/src/components/pending_items_button/pending_items_button.xml',
            'ths_medical_pos/static/src/components/appointment_screen_button/appointment_screen_button.xml',
            'ths_medical_pos/static/src/components/appointment_screen_button/appointment_screen_button.js',
            # Popups
            'ths_medical_pos/static/src/popups/pending_items_list_popup.js',
            'ths_medical_pos/static/src/popups/pending_items_list_popup.xml',
            'ths_medical_pos/static/src/popups/appointment_detail_popup.xml',
            'ths_medical_pos/static/src/popups/appointment_detail_popup.js',
            'ths_medical_pos/static/src/popups/appointment_create_popup.xml',
            'ths_medical_pos/static/src/popups/appointment_create_popup.js',
            # Screens
            'ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.xml',
            'ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
