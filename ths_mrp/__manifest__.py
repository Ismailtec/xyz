# -*- coding: utf-8 -*-
{
    'name': 'Techouse MRP',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing/Customization',
    'summary': 'MRP specific customizations for Techouse Solutions',
    'description': """
Techouse MRP (ths_mrp) extends the functionality of the Techouse Base (ths_base) module into Odoo 18's Manufacturing application. It ensures that Manufacturing Orders (MOs) and Unbuild Orders utilize the "Effective Date" concept established by ths_base, allowing for accurate backdating of manufacturing-related inventory moves and accounting entries.
(Requires the 'Techouse Base' module to be installed)
Detailed Feature List (User-Friendly)
•	Effective Date for Manufacturing:
	    - Adds an "Effective Date" to Manufacturing Orders, automatically set based on the MO's Planned Start Date.
        - Adds an "Effective Date" to Unbuild Orders, automatically derived from the related Manufacturing Order (if linked).
        - Ensures inventory movements (component consumption, finished product production, unbuild components/products) use this Effective Date.
        - Ensures related accounting entries also reflect the Effective Date.
•	Improved Journal Entry References:
        - Adds references to the Manufacturing Order or Unbuild Order in the corresponding Journal Entry descriptions for better traceability.
    """,
    'author': 'Techouse Solutions / Ismail Abdelkhalik',
    'website': 'https://www.techouse.ae',
    'depends': [
        'base',
        'mrp',
        'stock_account',
        'ths_base', # Dependency for the core effective date logic/field
    ],
    'data': [
        # Security files first
        'security/ir.model.access.csv',
        # Views
        'views/mrp_production.xml',
        'views/mrp_unbuild.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}