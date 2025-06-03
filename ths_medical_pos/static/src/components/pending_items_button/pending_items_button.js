/** @odoo-module */

/**
 * Button component for accessing pending medical items in POS
 * Handles core functionality for non-veterinary medical practices
 * Displays pending items that need to be billed through POS
 *
 * FIXED: Major corrections applied to follow Odoo 18 standards:
 * 1. Added makeAwaitable import for proper popup handling
 * 2. Added direct popup component import
 * 3. Updated onClick method to use makeAwaitable instead of dialog.add
 * 4. Maintained all original medical functionality and detailed comments
 * 5. Preserved comprehensive error handling and logging
 */
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
// FIXED: Added required imports for Odoo 18 popup pattern
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
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Handle button click to fetch and display pending items
     * Base implementation for general medical practices
     * Filters items by current customer if one is selected
     *
     * FIXED: Updated to use proper Odoo 18 popup opening pattern
     */
    async onClick() {
        // Logging for traceability
        console.log("Medical POS: Pending Items Button Clicked");

        const order = this.pos.get_order();
        const client = order?.get_partner();
        const domain = [['state', '=', 'pending']];
        let popupTitle = _t('Pending Medical Items');

        // Filter by current customer if one is selected
        if (client?.id) {
            domain.push(['partner_id', '=', client.id]);
            popupTitle = _t("Pending Items for %(partnerName)s", { partnerName: client.name });
        }

        try {
            // Fetch pending items from backend
            const fieldsToFetch = [
                'id', 'display_name', 'encounter_id', 'appointment_id',
                'partner_id', 'patient_id', 'product_id', 'description',
                'qty', 'price_unit', 'discount', 'practitioner_id',
                'commission_pct', 'state',
            ];

            // For diagnostic purposes
            console.log("Making RPC call with domain:", domain);

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                domain,
                fieldsToFetch,
                { context: this.pos.user.context }
            );

            console.log("RPC call successful. Pending items fetched:", pendingItems);

            if (pendingItems && pendingItems.length > 0) {
                console.log(
                    '[POS Debug] Attempting to open PendingItemsListPopup',
                    typeof PendingItemsListPopup,
                    PendingItemsListPopup
                );

                // FIXED: Use makeAwaitable pattern for Odoo 18 instead of dialog.add
                const payload = await makeAwaitable(this.dialog, PendingItemsListPopup, {
                    title: popupTitle,
                    items: pendingItems,
                });

                console.log("Popup opened successfully", payload);
            } else {
                // Show notification when no items found
                const message = client
                    ? _t('No pending medical items found for %(partnerName)s.', { partnerName: client.name })
                    : _t('No pending medical items found.');
                this.notification.add(message, {
                    type: 'warning',
                    sticky: false,
                    duration: 3000
                });
            }

        } catch (error) {
            console.error("Error fetching or showing pending medical items:", error);
            this.notification.add(
                _t('Error fetching pending items. Check connection or logs.'),
                { type: 'danger', sticky: true }
            );
        }
    }
}

// Register component for use in POS components registry
registry.category("pos_components").add("PendingItemsButton", PendingItemsButton);

// Global error handler for debugging purposes
window.onerror = function (msg, url, lineNo, columnNo, error) {
    console.log("[GlobalError]", msg, url, lineNo, columnNo, error ? error.stack : "");
    return false;
};

console.log("Loaded file:", "ths_medical_pos/static/src/components/pending_items_button/pending_items_button.js");