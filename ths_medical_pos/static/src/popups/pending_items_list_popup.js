/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks"; // Import useService hook

export class PendingItemsListPopup extends AbstractAwaitablePopup {
    static template = "ths_medical_pos.PendingItemsListPopup";
    static defaultProps = {
        confirmText: _t("Ok"),
        cancelText: _t("Close"),
        title: _t("Pending Items"),
        items: [],
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.notification = useService("notification"); // Use notification service
        console.log("PendingItemsListPopup setup with items:", this.props.items);
    }

    get itemsToShow() {
        return this.props.items || [];
    }

    formatCurrency(amount) {
        return this.pos.format_currency(amount);
    }

    // Updated Action when an item row (or its button) is clicked
    async selectItem(item) {
        console.log("Attempting to add item:", item);

        const order = this.pos.get_order();
        if (!order) {
            this.notification.add(_t("No active order found."), { type: 'danger' });
            return;
        }

        const productId = item.product_id[0];
        const product = this.pos.db.get_product_by_id(productId);

        if (!product) {
            console.error(`Product with ID ${productId} not found in POS DB.`);
            this.notification.add(
                _t("Product '%(productName)s' not available in POS.", { productName: item.product_id[1] }),
                { type: 'danger', sticky: true }
            );
            // Maybe remove item from list or disable it? For now, just notify.
            return;
        }

        console.log(`Adding product: ${product.display_name} to order.`);

        // Prepare options for add_product
        // Ensure keys match expected options for add_product and include custom data under 'extras'
        const options = {
            quantity: item.qty,
            price: item.price_unit, // Set specific price from pending item
            discount: item.discount || 0,
            description: item.description || product.display_name, // Use specific description or fallback
            // Standard place to pass extra context/data
            extras: {
                ths_pending_item_id: item.id,
                ths_patient_id: item.patient_id ? item.patient_id[0] : null, // Pass ID
                ths_provider_id: item.practitioner_id ? item.practitioner_id[0] : null, // Pass ID
                ths_commission_pct: item.commission_pct || 0,
                // Pass original price if needed for calculations later
                // base_price: item.price_unit
            },
             // If merge: false is needed to prevent merging with identical lines, add it
             // merge: false,
        };

        try {
            // Add the product to the order
            // add_product might be async depending on version/config
            await order.add_product(product, options);
            console.log("Product added successfully with options:", options);

            this.notification.add(
                _t("Added '%(productName)s' to order.", { productName: product.display_name }),
                { type: 'success', sticky: false, duration: 2000 }
            );

            // Close the popup after successfully adding the item
            this.confirm();

        } catch (error) {
            console.error("Error adding product to order:", error);
            this.notification.add(
                _t("Failed to add item '%(productName)s'.", { productName: product.display_name }),
                { type: 'danger', sticky: true }
            );
            // Optionally, re-throw or handle specific errors if needed
        }
    }

    cancel() {
        super.cancel();
    }
}