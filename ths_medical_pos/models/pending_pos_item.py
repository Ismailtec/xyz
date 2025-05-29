# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ThsPendingPosItem(models.Model):
    """
    Model to store pending medical items that need to be billed through POS
    These items are created during medical encounters and later processed in POS
    """
    _name = 'ths.pending.pos.item'
    _description = 'Pending POS Item for Medical Billing'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # Core identification fields
    display_name = fields.Char(
        string='Description',
        compute='_compute_display_name',
        store=True,
        help="Auto-generated display name for the pending item"
    )

    # Product and pricing information
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain=[('available_in_pos', '=', True)],
        help="Product or service to be billed"
    )
    qty = fields.Float(
        string='Quantity',
        default=1.0,
        required=True,
        help="Quantity of the product/service"
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        help="Unit price for the item"
    )
    discount = fields.Float(
        string='Discount (%)',
        default=0.0,
        help="Discount percentage to apply"
    )
    description = fields.Text(
        string='Notes',
        help="Additional notes or description for the item"
    )

    # Medical context fields
    encounter_id = fields.Many2one(
        'ths.medical.encounter',
        string='Medical Encounter',
        help="The medical encounter this item belongs to"
    )
    appointment_id = fields.Many2one(
        'calendar.event',
        string='Appointment',
        related='encounter_id.appointment_id',
        store=True,
        help="Related appointment"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        help="The customer/owner who will be billed"
    )
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        domain=[('ths_partner_type_id.name', '=', 'Pet')],
        help="The patient (pet) this item relates to"
    )
    practitioner_id = fields.Many2one(
        'hr.employee',
        string='Practitioner',
        domain=[('ths_is_medical', '=', True)],
        help="Medical practitioner who provided the service"
    )

    # Commission and financial tracking
    commission_pct = fields.Float(
        string='Commission %',
        default=0.0,
        help="Commission percentage for the practitioner"
    )

    # Processing status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True,
        help="Processing status of the pending item")

    # POS integration fields
    pos_order_line_id = fields.Many2one(
        'pos.order.line',
        string='POS Order Line',
        help="POS order line created from this pending item"
    )
    processed_date = fields.Datetime(
        string='Processed Date',
        help="Date when item was processed in POS"
    )
    processed_by = fields.Many2one(
        'res.users',
        string='Processed By',
        help="User who processed the item in POS"
    )

    # Computed fields
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        help="Total amount after discount"
    )

    @api.depends('product_id', 'qty', 'price_unit', 'partner_id')
    def _compute_display_name(self):
        """Compute display name for the pending item"""
        for record in self:
            if record.product_id and record.partner_id:
                record.display_name = f"{record.product_id.name} - {record.partner_id.name} (Qty: {record.qty})"
            elif record.product_id:
                record.display_name = f"{record.product_id.name} (Qty: {record.qty})"
            else:
                record.display_name = "Pending Item"

    @api.depends('qty', 'price_unit', 'discount')
    def _compute_total_amount(self):
        """Compute total amount after applying discount"""
        for record in self:
            subtotal = record.qty * record.price_unit
            discount_amount = subtotal * (record.discount / 100.0)
            record.total_amount = subtotal - discount_amount

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Set default price when product changes"""
        if self.product_id:
            self.price_unit = self.product_id.list_price

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Set owner as partner when patient changes"""
        if self.patient_id and self.patient_id.ths_pet_owner_id:
            self.partner_id = self.patient_id.ths_pet_owner_id

    def action_mark_processed(self):
        """Mark item as processed"""
        self.ensure_one()
        if self.state != 'pending':
            raise ValidationError(_("Only pending items can be marked as processed."))

        self.write({
            'state': 'processed',
            'processed_date': fields.Datetime.now(),
            'processed_by': self.env.user.id,
        })
        return True

    def action_mark_cancelled(self):
        """Mark item as cancelled"""
        self.ensure_one()
        if self.state == 'processed':
            raise ValidationError(_("Processed items cannot be cancelled."))

        self.state = 'cancelled'
        return True

    def action_reset_to_pending(self):
        """Reset item back to pending status"""
        self.ensure_one()
        self.write({
            'state': 'pending',
            'processed_date': False,
            'processed_by': False,
            'pos_order_line_id': False,
        })
        return True

    @api.model
    def create_from_encounter(self, encounter_id, items_data):
        """
        Create pending items from medical encounter data

        :param encounter_id: ID of the medical encounter
        :param items_data: List of dictionaries with item data
        :return: Created pending items recordset
        """
        encounter = self.env['ths.medical.encounter'].browse(encounter_id)
        if not encounter.exists():
            raise ValidationError(_("Medical encounter not found."))

        pending_items = self.env['ths.pending.pos.item']

        for item_data in items_data:
            vals = {
                'encounter_id': encounter.id,
                'partner_id': encounter.owner_id.id,
                'patient_id': encounter.patient_id.id,
                'practitioner_id': encounter.practitioner_id.id,
                **item_data  # Merge with provided item data
            }
            pending_items |= self.create(vals)

        return pending_items

    @api.model
    def get_pending_for_partner(self, partner_id, limit=100):
        """
        Get pending items for a specific partner (for POS integration)

        :param partner_id: Partner ID to filter by
        :param limit: Maximum number of records to return
        :return: List of dictionaries with item data
        """
        domain = [
            ('partner_id', '=', partner_id),
            ('state', '=', 'pending')
        ]

        pending_items = self.search(domain, limit=limit, order='create_date desc')

        return pending_items.read([
            'id', 'display_name', 'product_id', 'qty', 'price_unit',
            'discount', 'description', 'patient_id', 'practitioner_id',
            'commission_pct', 'encounter_id', 'total_amount'
        ])

    @api.model
    def get_all_pending(self, limit=100):
        """
        Get all pending items (for POS integration)

        :param limit: Maximum number of records to return
        :return: List of dictionaries with item data
        """
        domain = [('state', '=', 'pending')]

        pending_items = self.search(domain, limit=limit, order='create_date desc')

        return pending_items.read([
            'id', 'display_name', 'product_id', 'qty', 'price_unit',
            'discount', 'description', 'partner_id', 'patient_id',
            'practitioner_id', 'commission_pct', 'encounter_id', 'total_amount'
        ])

    def _check_access_rights(self, operation, raise_exception=True):
        """Override to ensure proper access control"""
        # Allow POS users to read and write pending items
        if operation in ('read', 'write') and self.env.user.has_group('point_of_sale.group_pos_user'):
            return True
        return super()._check_access_rights(operation, raise_exception)
