/** @odoo-module */

/*
 * IMPORTANT: This component follows Odoo 18 OWL 3 standards with mandatory static properties.
 * All OWL 3 components MUST have static template, props, and components properties defined.
 * This is the LATEST required methodology for Odoo 18 POS popup components.
 *
 * Popup component for displaying and managing pending medical items
 * Base implementation for general medical practices (non-veterinary)
 */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog"; // Required: For OWL 3 popup content rendering
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class PendingItemsListPopup extends Component {
    constructor(...args) {
        console.log('PendingItemsListPopup: constructed with', args);
        super(...args);
    }
    static template = "ths_medical_pos.PendingItemsListPopup";
    static components = { Dialog }; // CRITICAL: OWL 3 requirement for rendering Dialog
    // REQUIRED: Props definition for OWL 3 validation
    static props = {
        title: { type: String, optional: true },
        items: { type: Array },
        close: Function,
    };
    static defaultProps = {
        title: _t("Pending Medical Items"),
        items: [],
    };

    setup() {
        console.log("PendingItemsListPopup: setup called");
        // Initialize POS store and required services using Odoo 18 hooks
        this.pos = usePos();
        this.dialog = useService("dialog"); // Use dialog service for nested popups in Odoo 18
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Add a pending medical item to the current POS order
     * Handles product validation, customer verification, and order line creation
     */
    async addItemToOrder(item) {
        const order = this.pos.get_order();
        const product = this.pos.db.product_by_id[item.product_id?.[0]];

        // Validate product exists in POS
        if (!product) {
            await this.dialog.add("ErrorPopup", {
                title: _t("Product Not Found"),
                body: _t("Product %s not found in POS", item.product_id?.[1]),
            });
            return;
        }

        // Check if current customer matches item's customer
        const currentPartner = order.get_partner();
        if (currentPartner && currentPartner.id !== item.partner_id?.[0]) {
            const { confirmed } = await this.dialog.add("ConfirmPopup", {
                title: _t("Different Customer"),
                body: _t("Item is for %s, current customer is %s. Continue?",
                        item.partner_id?.[1], currentPartner.name),
            });
            if (!confirmed) return;
        }

        // Add product to order with medical-specific extras
        const orderline = order.add_product(product, {
            quantity: item.qty,
            price: item.price_unit,
            discount: item.discount || 0,
            extras: {
                ths_pending_item_id: item.id,
                ths_patient_id: item.patient_id?.[0],
                ths_provider_id: item.practitioner_id?.[0],
                ths_commission_pct: item.commission_pct || 0,
                encounter_id: item.encounter_id?.[0], // Include encounter reference for medical tracking
            },
            merge: false, // Don't merge with existing lines to maintain medical traceability
        });

        // Add description as order line note if available
        if (item.description && orderline) {
            orderline.set_note(item.description);
        }

        try {
            // Mark item as processed in backend
            await this.orm.write("ths.pending.pos.item", [item.id], { state: "processed" });
            this.notification.add(_t("Item added successfully"), { type: "success" });

            // Remove processed item from popup list
            const index = this.props.items.findIndex(i => i.id === item.id);
            if (index !== -1) {
                this.props.items.splice(index, 1);
            }

            // Close popup if no more items
            if (!this.props.items.length) {
                this.props.close();
            }

        } catch (error) {
            // Note: ErrorPopup uses the dialog service for nested popups in Odoo 18
            await this.dialog.add("ErrorPopup", {
                title: _t("Update Error"),
                body: _t("Could not update item status."),
            });
        }
    }

    /**
     * Close the popup
     */
    cancel() {
        this.props.close();
    }

    /**
     * Get items to display in the popup
     */
    get itemsToShow() {
        return this.props.items;
    }

    /**
     * Format currency amount using POS formatting
     */
    formatCurrency(amount) {
        return this.pos.format_currency(amount);
    }
}

console.log(
    "Registering PendingItemsListPopup in popups registry",
    typeof PendingItemsListPopup
);
// REQUIRED: Register popup in Odoo 18 registry system
registry.category("popups").add("PendingItemsListPopup", PendingItemsListPopup);

console.log("Loaded file:", "ths_medical_pos/static/src/popups/pending_items_list_popup.js");