/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/popups/pending_items_list_popup.js");

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class PendingItemsListPopup extends Component {
    static template = "ths_medical_pos.PendingItemsListPopup";
    static props = {
        title: { type: String, optional: true },
        items: { type: Array, optional: true },
        close: Function,  // This is the function to close the popup
    };
    static defaultProps = {
        title: _t('Pending Medical Items'),
        items: [],
    };

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    async addItemToOrder(item) {
        console.log("Adding item to order:", item);

        const order = this.pos.get_order();
        const product = this.pos.db.product_by_id[item.product_id[0]];

        if (!product) {
            await this.popup.add("ErrorPopup", {
                title: _t('Product Not Found'),
                body: _t('Product %s not available in POS', item.product_id[1]),
            });
            return;
        }

        // Check if customer matches
        const currentPartner = order.get_partner();
        if (currentPartner && currentPartner.id !== item.partner_id[0]) {
            const { confirmed } = await this.popup.add("ConfirmPopup", {
                title: _t('Different Customer'),
                body: _t('This item belongs to %s but current customer is %s. Continue?',
                    item.partner_id[1], currentPartner.name),
            });
            if (!confirmed) {
                return;
            }
        }

        // Add to order with all details
        const options = {
            quantity: item.qty,
            price: item.price_unit,
            discount: item.discount || 0,
            extras: {
                pending_item_id: item.id,
                practitioner_id: item.practitioner_id,
                commission_pct: item.commission_pct,
                patient_id: item.patient_id,
                encounter_id: item.encounter_id,
            }
        };

        const orderline = order.add_product(product, options);

        // Set the description if provided
        if (item.description && orderline) {
            orderline.set_note(item.description);
        }

        // Mark as processed
        try {
            await this.orm.write('ths.pending.pos.item', [item.id], {
                state: 'processed',
            });

            this.notification.add(
                _t('Item added to order successfully'),
                { type: 'success' }
            );

            // Remove from list and refresh
            const index = this.props.items.findIndex(i => i.id === item.id);
            if (index > -1) {
                this.props.items.splice(index, 1);
            }

            if (this.props.items.length === 0) {
                this.props.close();
            }

        } catch (error) {
            console.error("Error updating pending item:", error);
            await this.popup.add("ErrorPopup", {
                title: _t('Error'),
                body: _t('Error updating item status'),
            });
        }
    }

    get itemsToShow() {
        return this.props.items || [];
    }

    cancel() {
        this.props.close();
    }
}

// Register the popup
registry.category("popups").add("PendingItemsListPopup", PendingItemsListPopup);