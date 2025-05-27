# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Appointment Gantt Extension',
    'version': '18.0.0.1',
    'category': 'Services/Appointment',
    'author': 'NHS',
    'summary': 'extends web gantt view',
    'website': 'www.syrupsbiz.com',
    'description': """
Extend web gantt view and add new buttons
    """,
    'depends': ['appointment', 'web_gantt'],
    'data': [
    ],
    'demo': [
    ],
    'assets': {
        'web.assets_backend_lazy': [
            'web_gantt_extension/static/src/js/gantt_renderer.js',
        ],
    },
    'images':  ['static/description/gantt_01.png'],
    'installable': True,
    'application': True,
    'license': 'LGPL-3'
}
