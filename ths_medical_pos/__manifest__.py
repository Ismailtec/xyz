# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical POS Integration',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale/Medical',
    'summary': 'Integrates medical encounters and billing with Point of Sale.',
    'description': '''
        Medical Point of Sale Extension
        ==============================
        
        This module extends the Odoo 18 Point of Sale application to support medical practices:
        
        Features:
        - Appointment management directly from POS
        - Patient and pet management integration
        - Pending medical items handling
        - Medical practitioner assignment
        - Treatment room booking
        - Commission tracking for medical services
        
        Technical Implementation:
        - Built with OWL 3 framework
        - Follows Odoo 18 POS standards
        - Responsive design for mobile and tablet use
        - Real-time appointment calendar integration
    ''',
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'point_of_sale',
        'ths_medical_base',  # Depends on the medical base for encounter/pending items
        'ths_hr',  # Needed for hr.employee (practitioner) access
        'calendar',
        'hr',
        'resource',
        'contacts',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Views
        #
        # # Data
        #
        # # Assets
        # 'views/assets.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            # 1. Base popup component (no dependencies on other medical components)
            'ths_medical_pos/static/src/popups/pending_items_list_popup.js',
            'ths_medical_pos/static/src/popups/pending_items_list_popup.xml',

            # 2. Button component (depends on popup component)
            'ths_medical_pos/static/src/components/pending_items_button/pending_items_button.js',
            'ths_medical_pos/static/src/components/pending_items_button/pending_items_button.xml',

            # 3. Screen patches (depend on button component)
            'ths_medical_pos/static/src/screens/product_screen/product_screen.js',
            'ths_medical_pos/static/src/screens/product_screen/product_screen.xml',

            # 4. Appointment screen functionality
            'ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.xml',
            'ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.js',

            # 5. Additional widgets and styling (no dependencies)
            'ths_medical_pos/static/src/components/calendar_widget/calendar_widget.js',
            'ths_medical_pos/static/src/css/style.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
