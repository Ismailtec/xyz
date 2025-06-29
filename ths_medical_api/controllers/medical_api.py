# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import json


class MedicalAPI(http.Controller):

    @http.route('/api/medical/appointments/available-slots',
                type='json', auth='public', methods=['POST'], csrf=False)
    def get_available_slots(self, **kwargs):
        """Get available appointment slots

        Expected params:
        - appointment_type_id: int
        - date_from: str (YYYY-MM-DD)
        - date_to: str (YYYY-MM-DD)
        - practitioner_id: int (optional)
        """
        try:
            data = request.jsonrequest
            appointment_type_id = data.get('appointment_type_id')
            date_from = data.get('date_from')
            date_to = data.get('date_to')
            practitioner_id = data.get('practitioner_id')

            if not all([appointment_type_id, date_from, date_to]):
                return {'error': 'Missing required parameters'}

            # Convert dates
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')

            # Get appointment type
            apt_type = request.env['appointment.type'].sudo().browse(appointment_type_id)
            if not apt_type.exists():
                return {'error': 'Invalid appointment type'}

            # Get available slots
            domain = [
                ('appointment_type_id', '=', appointment_type_id),
                ('start', '>=', date_from_dt),
                ('start', '<=', date_to_dt),
                ('state', '=', 'available')
            ]

            if practitioner_id:
                domain.append(('ths_practitioner_id.employee_id', '=', practitioner_id))

            slots = request.env['calendar.event'].sudo().search_read(
                domain,
                ['start', 'stop', 'ths_practitioner_id', 'ths_room_id'],
                limit=100
            )

            return {
                'success': True,
                'slots': [{
                    'start': slot['start'].isoformat(),
                    'stop': slot['stop'].isoformat(),
                    'practitioner': slot['ths_practitioner_id'][1] if slot['ths_practitioner_id'] else None,
                    'location': slot['ths_room_id'][1] if slot['ths_room_id'] else None,
                } for slot in slots]
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/api/medical/appointments/book',
                type='json', auth='user', methods=['POST'], csrf=False)
    def book_appointment(self, **kwargs):
        """Book an appointment

        Expected params:
        - appointment_type_id: int
        - start: str (ISO datetime)
        - pet_ids: list of int (Changed from pet_id to pet_ids for Many2many)
        - practitioner_ar_id: int
        - location_ar_id: int (optional)
        - reason: str
        """
        try:
            data = request.jsonrequest

            # Validate required fields - updated for Many2many
            required = ['appointment_type_id', 'start', 'pet_ids', 'practitioner_ar_id']
            if not all(data.get(f) for f in required):
                return {'error': 'Missing required parameters'}

            # Get pets and validate - handle list of IDs
            pet_ids = data['pet_ids']
            if not isinstance(pet_ids, list) or not pet_ids:
                return {'error': 'pet_ids must be a non-empty list'}

            pets = request.env['res.partner'].sudo().browse(pet_ids)
            invalid_pets = pets.filtered(lambda p: not p.exists() or not p.is_pet)
            if invalid_pets:
                return {'error': f'Invalid pets: {invalid_pets.ids}'}

            # TODO: Handle multiple pets - for now take first pet's owner
            primary_pet = pets[0]
            owner = primary_pet.ths_pet_owner_id
            if not owner:
                return {'error': f'Pet {primary_pet.name} has no assigned owner'}

            # Create appointment
            appointment_vals = {
                'appointment_type_id': data['appointment_type_id'],
                'start': data['start'],
                'stop': (datetime.fromisoformat(data['start']) + timedelta(hours=0.5)).isoformat(),
                'ths_patient_ids': [(6, 0, pet_ids)],  # Many2many field syntax
                'partner_id': owner.id,
                'ths_practitioner_id': data['practitioner_ar_id'],
                'ths_room_id': data.get('location_ar_id'),
                'ths_reason_for_visit': data.get('reason', ''),
                'appointment_status': 'draft',
            }

            appointment = request.env['calendar.event'].sudo().create(appointment_vals)

            return {
                'success': True,
                'appointment_id': appointment.id,
                'name': appointment.name,
                'status': appointment.appointment_status
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/api/medical/pets/<int:pet_id>/history',
                type='json', auth='user', methods=['GET'], csrf=False)
    def get_pet_medical_history(self, pet_id, **kwargs):
        """Get medical history for a pet"""
        try:
            # Check access
            pet = request.env['res.partner'].sudo().browse(pet_id)
            if not pet.exists() or not pet.is_pet:
                return {'error': 'Invalid pet'}

            # Get encounters - search for pet in Many2many field
            encounters = request.env['ths.medical.base.encounter'].sudo().search_read(
                [('patient_ids', 'in', [pet_id])],  # Search in Many2many field
                ['name', 'date_start', 'practitioner_id', 'state',
                 'chief_complaint', 'ths_diagnosis_text', 'ths_plan'],
                order='date_start desc',
                limit=50
            )

            return {
                'success': True,
                'pet': {
                    'id': pet.id,
                    'name': pet.name,
                    'species': pet.ths_species_id.name if pet.ths_species_id else None,
                    'breed': pet.ths_breed_id.name if pet.ths_breed_id else None,
                },
                'encounters': encounters
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/api/medical/pending-items/<int:owner_id>',
                type='json', auth='user', methods=['GET'], csrf=False)
    def get_pending_items(self, owner_id, **kwargs):
        """Get pending billing items for an owner"""
        try:
            items = request.env['ths.pending.pos.item'].sudo().search_read(
                [('partner_id', '=', owner_id), ('state', '=', 'pending')],
                ['product_id', 'patient_id', 'qty', 'price_unit', 'create_date'],
                order='create_date desc'
            )

            total = sum(item['qty'] * item['price_unit'] for item in items)

            return {
                'success': True,
                'items': items,
                'total_amount': total
            }

        except Exception as e:
            return {'error': str(e)}
