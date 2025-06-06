# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical POS Veterinary',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale/Medical',
    'summary': 'Veterinary specific UI adaptations for Medical POS.',
    'description': """
Extends the Techouse Medical POS Integration for veterinary specifics.
- Adapts POS UI elements (e.g., pending item lists, customer selection) to display Pet/Owner information clearly.
- Handles fetching and potentially filtering data based on Pet/Owner context.
- (Future) Integrates with Membership module for displaying Park Management status.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'ths_medical_pos',  # Core POS medical integration
        'ths_medical_vet',  # Core Vet data models and fields
        'membership',
    ],
    'data': [
        # 'security/ir.model.access.csv', # If specific permissions needed later
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # Odoo standard assets required for Gantt and calendar views
            'web_gantt/static/src/**/*',
            'appointment/static/src/views/gantt/**/*',
            'calendar/static/src/views/widgets/**/*',
            'calendar/static/src/views/calendar_form/**/*',
            # Patches should load after the original components they patch
            # === PATCH FILE ===
            'ths_medical_pos_vet/static/src/popups/pending_items_list_popup.xml',
            'ths_medical_pos_vet/static/src/components/pending_items_button/pending_items_button.js',
            # === MEMBERSHIP DISPLAY PATCHES ===
            'ths_medical_pos_vet/static/src/screens/product_screen/product_screen.xml',
            'ths_medical_pos_vet/static/src/screens/product_screen/product_screen.js',
            # === END ===
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
