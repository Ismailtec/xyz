/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";
import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";

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
     * Override onClick method to add veterinary-specific behavior
     * Enhances base medical functionality with Pet/Owner context
     */
    async onClick() {
        console.log("Vet POS: Pending Items Button Clicked - Enhanced for Veterinary");

        const order = this.pos.get_order();
        const client = order.get_partner(); // This would be the Pet Owner in vet context

        let popupTitle = _t('Pending Medical Items (All Pets)');
        let filterDomain = [['state', '=', 'pending']]; // Base domain from parent

        // Veterinary-specific filtering: Filter by Pet Owner if selected
        if (client) {
            console.log(`Vet POS: Filtering pending items for Pet Owner: ${client.name} (ID: ${client.id})`);
            // In vet context, partner_id refers to the Pet Owner who pays the bills
            const ownerFilter = ['partner_id', '=', client.id];
            // Use Domain.and() for proper domain combination in Odoo 18
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
                // Use dialog service to show veterinary-adapted popup
                await this.dialog.add('PendingItemsListPopup', {
                    title: popupTitle, // Veterinary-specific title
                    items: pendingItems,
                });
                console.log("Vet POS: Popup opened successfully with veterinary adaptations");
            } else {
                // Veterinary-specific no-items message
                const message = client
                    ? _t('No pending medical items found for %(ownerName)s\'s pets.', { ownerName: client.name })
                    : _t('No pending medical items found for any pets.');

                this.notification.add(message, {
                    type: 'warning',
                    sticky: false,
                    duration: 3000
                });
            }

        } catch (error) {
            console.error("Vet POS: Error fetching or showing pending medical items:", error);
            this.notification.add(
                _t('Error fetching pending items. Check connection or logs.'),
                { type: 'danger', sticky: true }
            );
        }
    }
});

// NOTE: No additional registry registration needed - this patches the existing component
// The base component is already registered in ths_medical_pos module