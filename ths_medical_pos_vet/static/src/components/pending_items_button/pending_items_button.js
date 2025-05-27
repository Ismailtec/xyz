/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button"; // Import original
import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain"; // Import Domain utility

patch(PendingItemsButton.prototype, {
    // Override the onClick method
    async onClick() {
        console.log("Vet Pending Items Button Clicked!"); // Vet specific log

        const order = this.pos.get_order();
        const client = order.get_partner(); // Get the currently selected customer (Pet Owner)

        let popupTitle = _t('Pending Medical Items (All)');
        let filterDomain = [['state', '=', 'pending']]; // Base domain

        if (client) {
            console.log(`Filtering pending items for customer: ${client.name} (ID: ${client.id})`);
            // Add customer filter - IMPORTANT: 'partner_id' on ths.pending.pos.item refers to the Owner
            const ownerFilter = ['partner_id', '=', client.id];
            // Combine domains using Domain.and()
            filterDomain = Domain.and([filterDomain, [ownerFilter]]);
            popupTitle = _t("Pending Items for %(partnerName)s", { partnerName: client.name });
        } else {
            console.log("No customer selected, fetching all pending items.");
            // Optionally show a warning or prompt to select customer first
            // this.notification.add(_t("Select a customer to filter pending items."), { type: 'info' });
        }

        try {
            const fieldsToFetch = [
                'id', 'display_name', 'encounter_id', 'appointment_id',
                'partner_id', 'patient_id', 'product_id', 'description',
                'qty', 'price_unit', 'discount', 'practitioner_id',
                'commission_pct', 'state',
            ];

            console.log("Making RPC call with domain:", filterDomain); // Log the final domain

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                filterDomain,
                fieldsToFetch,
                // Add context if needed, e.g., for company checks
                 //{ context: this.pos.user.context }
            );

            console.log("RPC call successful. Pending items fetched:", pendingItems);

            if (pendingItems && pendingItems.length > 0) {
                // Show the popup (it will use the patched vet template automatically)
                await this.pos.showPopup('PendingItemsListPopup', {
                     title: popupTitle, // Pass potentially filtered title
                     items: pendingItems,
                });
                console.log("Vet Popup closed.");

            } else {
                 const message = client ?
                    _t('No pending medical items found for %(partnerName)s.', { partnerName: client.name }) :
                    _t('No pending medical items found.');
                this.notification.add(message, { type: 'warning', sticky: false, duration: 3000 });
            }

        } catch (error) {
            console.error("Vet: Error fetching or showing pending medical items:", error);
             this.notification.add(
                 _t('Error fetching pending items. Check connection or logs.'),
                 { type: 'danger', sticky: true }
             );
        }
    }
});

// NOTE: We don't need to patch ProductScreen again here, as the original
// PendingItemsButton component is already placed by ths_medical_pos.
// This patch modifies the *behavior* of that existing button instance.