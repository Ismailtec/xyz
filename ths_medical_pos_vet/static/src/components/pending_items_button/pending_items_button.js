/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";
import { _t } from "@web/core/l10n/translation";

/**
 * IMPORTANT: This follows Odoo 18 OWL 3 component patching methodology.
 * This is the LATEST approach for extending existing components in veterinary modules.
 * Patches allow extending base medical functionality with vet-specific features.
 *
 * Veterinary-specific extension of PendingItemsButton
 * Extends base medical functionality to handle Pet/Owner relationships
 * Adds veterinary-specific UI adaptations and filtering logic
 */
patch(PendingItemsButton.prototype, {
    /**
     * FIXED: Override onClick method to add veterinary-specific behavior
     * Enhanced to work with the updated base medical functionality
     * Adds Pet/Owner context for veterinary practices
     */
    async onClick() {
        console.log("Vet POS: Pending Items Button Clicked - Enhanced for Veterinary");

        const order = this.pos.get_order();
        if (!order) {
            console.error("No active order found");
            this.notification.add(
                _t('No active order found. Please try again.'),
                { type: 'danger', sticky: false, duration: 3000 }
            );
            return;
        }

        const client = order.get_partner(); // This would be the Pet Owner in vet context

        let popupTitle = _t('Pending Medical Items (All Pets)');
        let filterDomain = [['state', '=', 'pending']]; // Base domain from parent

        // Veterinary-specific filtering: Filter by Pet Owner if selected
        if (client?.id) {
            console.log(`Vet POS: Filtering pending items for Pet Owner: ${client.name} (ID: ${client.id})`);
            // In vet context, partner_id refers to the Pet Owner who pays the bills
            const ownerFilter = ['partner_id', '=', client.id];
            filterDomain = [...filterDomain, ownerFilter];
            popupTitle = _t("Pending Items for %(ownerName)s's Pets", { ownerName: client.name });
        } else {
            console.log("Vet POS: No Pet Owner selected, fetching all pending items for all pets.");
        }

        try {
            // Veterinary-specific fields - includes both Pet and Owner information
            const fieldsToFetch = [
                'id', 'display_name', 'encounter_id', 'appointment_id',
                'partner_id', 'patient_id', 'product_id', 'description', // Core fields
                'qty', 'price_unit', 'discount', 'practitioner_id',      // Billing fields
                'commission_pct', 'state',                               // Business fields
            ];

            console.log("Vet POS: Making RPC call with veterinary domain:", filterDomain);

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                filterDomain,
                fieldsToFetch,
                { context: this.pos.user.context }
            );

            console.log("Vet POS: RPC call successful. Pending items fetched:", pendingItems);

            if (pendingItems && pendingItems.length > 0) {
                console.log('Vet POS: Attempting to open PendingItemsListPopup with veterinary adaptations');

                // FIXED: Use the updated makeAwaitable pattern from base module
                const { makeAwaitable } = await import("@point_of_sale/app/store/make_awaitable_dialog");
                const { PendingItemsListPopup } = await import("@ths_medical_pos/popups/pending_items_list_popup");

                const payload = await makeAwaitable(this.dialog, PendingItemsListPopup, {
                    title: popupTitle, // Veterinary-specific title
                    items: pendingItems,
                });

                console.log("Vet POS: Popup opened successfully with veterinary adaptations");
            } else {
                // Veterinary-specific no-items message
                let message;
                if (client) {
                    message = _t('No pending medical items found for %(ownerName)s\'s pets.', { ownerName: client.name });
                } else {
                    message = _t('No pending medical items found for any pets. Note: Select a pet owner to filter items for specific pets.');
                }

                this.notification.add(message, {
                    type: 'info',
                    sticky: false,
                    duration: 4000
                });
            }

        } catch (error) {
            console.error("Vet POS: Error fetching or showing pending medical items:", error);

            // FIXED: Enhanced error handling with veterinary context
            let errorMessage;
            if (error.message && error.message.includes('timeout')) {
                errorMessage = _t('Request timeout. Please check your connection and try again.');
            } else if (error.message && error.message.includes('permission')) {
                errorMessage = _t('Access denied. Please check your permissions for veterinary records.');
            } else {
                errorMessage = _t('Error fetching pending veterinary items: %(error)s', { error: error.message || 'Unknown error' });
            }

            this.notification.add(errorMessage, { type: 'danger', sticky: true });
        }
    }
});

// NOTE: No additional registry registration needed - this patches the existing component
// The base component is already registered in ths_medical_pos module

console.log("Loaded FIXED vet button patch - compatible with updated base module:", "pending_items_button.js");