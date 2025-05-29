# -*- coding: utf-8 -*-
{
    'name': 'Techouse Medical API',
    'version': '18.0.1.0.0',
    'category': 'Medical/API',
    'summary': 'REST API for Techouse Medical modules',
    'description': """
Provides REST API endpoints for:
- Appointment booking
- Patient information
- Medical history access
- Pending items retrieval
    """,
    'author': 'Techouse Solutions',
    'website': 'https://www.techouse.ae',
    'depends': [
        'ths_medical_base',
        'ths_medical_vet',
        'base_rest',
        'base_rest_datamodel',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/api_security.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
