/** @odoo-module */

/**
 * Button component for accessing pending medical items in POS
 *
 * FIXES APPLIED:
 * 1. Proper OWL 3 props validation
 * 2. Defensive notification service loading
 * 3. Better customer checking with proper error messages
 */
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
// Added required imports for Odoo 18 popup pattern
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { PendingItemsListPopup } from "@ths_medical_pos/popups/pending_items_list_popup";

export class PendingItemsButton extends Component {
    static template = "ths_medical_pos.PendingItemsButton";
    static props = {}; // Required for OWL 3 in Odoo 18
    static components = {}; // CRITICAL: Required for OWL 3 in Odoo 18

    setup() {
        // Initialize POS store hook and required services
        this.pos = usePos();
        this.dialog = useService("dialog"); // Use dialog service for Odoo 18 popup management

        // Defensive notification service loading
        try {
            this.notification = useService("notification");
        } catch (error) {
            console.error("Could not load notification service:", error);
            this.notification = {
                add: (message, options) => {
                    console.log("Fallback notification:", message, options);
                    alert(message); // Fallback to alert if notification service fails
                }
            };
        }

        this.orm = useService("orm");
    }

    /**
     * Handle button click with proper customer checking
     */
    async onClick() {
        // Logging for traceability
        console.log("Medical POS: Pending Items Button Clicked");

        const order = this.pos.get_order();
        if (!order) {
            console.error("No active order found");
            this.notification.add(
                _t('No active order found. Please try again.'),
                { type: 'danger', sticky: false, duration: 3000 }
            );
            return;
        }

        const client = order.get_partner();
        const domain = [['state', '=', 'pending']];
        let popupTitle = _t('Pending Medical Items');

        // Better customer checking
        if (client?.id) {
            domain.push(['partner_id', '=', client.id]);
            popupTitle = _t("Pending Items for %(partnerName)s", { partnerName: client.name });
            console.log(`Filtering for customer: ${client.name} (ID: ${client.id})`);
        } else {
            console.log("No customer selected, showing all pending items");
            // Note: We'll continue and show all items, but inform the user
        }

        try {
            // Fetch pending items from backend
            const fieldsToFetch = [
                'id', 'display_name', 'encounter_id', 'appointment_id',
                'partner_id', 'patient_id', 'product_id', 'description',
                'qty', 'price_unit', 'discount', 'practitioner_id',
                'commission_pct', 'state', 'notes',
            ];

            console.log("Making RPC call with domain:", domain);

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                domain,
                fieldsToFetch,
                { context: this.pos.user.context }
            );

            console.log("RPC call successful. Pending items fetched:", pendingItems);

            if (pendingItems && pendingItems.length > 0) {
                console.log('Attempting to open PendingItemsListPopup with items:', pendingItems.length);

                // Use makeAwaitable pattern for Odoo 18
                const payload = await makeAwaitable(this.dialog, PendingItemsListPopup, {
                    title: popupTitle,
                    items: pendingItems,
                });

                console.log("Popup opened successfully", payload);
            } else {
                // etter no-items message handling
                let message;
                if (client) {
                    message = _t('No pending medical items found for %(partnerName)s.', { partnerName: client.name });
                } else {
                    message = _t('No pending medical items found. Note: Select a customer to filter items for specific patients.');
                }

                // Use defensive notification
                this.notification.add(message, {
                    type: 'info',
                    sticky: false,
                    duration: 4000
                });
            }

        } catch (error) {
            console.error("Error fetching or showing pending medical items:", error);

            // More descriptive error messages
            let errorMessage;
            if (error.message && error.message.includes('timeout')) {
                errorMessage = _t('Request timeout. Please check your connection and try again.');
            } else if (error.message && error.message.includes('permission')) {
                errorMessage = _t('Access denied. Please check your permissions.');
            } else {
                errorMessage = _t('Error fetching pending items: %(error)s', { error: error.message || 'Unknown error' });
            }

            this.notification.add(errorMessage, { type: 'danger', sticky: true });
        }
    }
}

// Register component for use in POS components registry
registry.category("pos_components").add("PendingItemsButton", PendingItemsButton);

console.log("Loaded button file with proper error handling:", "pending_items_button.js");