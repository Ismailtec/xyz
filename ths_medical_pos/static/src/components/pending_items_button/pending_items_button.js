/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

/**
 * Button component for accessing pending medical items in POS.
 * Handles core functionality for non-veterinary medical practices.
 * Displays pending items that need to be billed through POS.
 */
export class PendingItemsButton extends Component {
    static template = "ths_medical_pos.PendingItemsButton";
    static props = {}; // Required for OWL 3 in Odoo 18
    static components = {}; // Required for OWL 3 in Odoo 18

    setup() {
        // Initialize POS store hook and required services
        this.pos = usePos();
        this.dialog = useService("dialog"); // Use dialog service to open popups
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Handle button click to fetch and display pending items.
     * Filters items by current customer if one is selected.
     */
    async onClick() {
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

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                domain,
                fieldsToFetch,
                { context: this.pos.user.context }
            );

            if (pendingItems && pendingItems.length > 0) {
                // Use dialog service to show pending items list popup
                this.dialog.add("PendingItemsListPopup", {
                    title: popupTitle,
                    items: pendingItems,
                    close: () => {}, // Optional: pass a close function if needed
                });
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
            this.notification.add(
                _t('Error fetching pending items. Check connection or logs.'),
                { type: 'danger', sticky: true }
            );
        }
    }
}

// Register component for use in POS components registry
registry.category("pos_components").add("PendingItemsButton", PendingItemsButton);
