/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { PendingItemsListPopup } from "@ths_medical_pos/popups/pending_items_list_popup"; // Import the popup
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation"; // Import translator

export class PendingItemsButton extends Component {
    static template = "ths_medical_pos.PendingItemsButton";

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        // No need to import popup service explicitly when using this.pos.showPopup
        console.log("PendingItemsButton setup complete.");
    }

    async onClick() {
        console.log("Pending Items Button Clicked!");
        try {
            const fieldsToFetch = [
                'id',
                'display_name',
                'encounter_id', // Fetch as [id, name]
                'appointment_id', // Fetch as [id, name]
                'partner_id', // Customer/Owner [id, name]
                'patient_id', // Patient [id, name]
                'product_id', // Fetch as [id, name]
                'description',
                'qty',
                'price_unit',
                'discount',
                'practitioner_id', // Provider [id, name]
                'commission_pct',
                'state',
            ];
            const domain = [['state', '=', 'pending']];

            console.log("Making RPC call to fetch pending items...");

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                domain,
                fieldsToFetch
                // { context: this.pos.user.context } // Add context if needed
            );

            console.log("RPC call successful. Pending items fetched:", pendingItems);

            if (pendingItems && pendingItems.length > 0) {
                // Show the popup with the fetched items
                await this.pos.showPopup('PendingItemsListPopup', {
                     title: _t('Pending Medical Items'), // Use translator
                     items: pendingItems,
                });
                // The popup promise resolves when it's closed (confirm or cancel)
                // We don't need to do anything with the result here for now
                console.log("Popup closed.");

            } else {
                this.notification.add(
                    _t('No pending medical items found.'), // Use translator
                    { type: 'warning', sticky: false, duration: 3000 }
                );
            }

        } catch (error) {
            console.error("Error fetching or showing pending medical items:", error);
             this.notification.add(
                 _t('Error fetching pending items. Check connection or logs.'), // Use translator
                 { type: 'danger', sticky: true }
             );
        }
    }
}

// Patch ProductScreen (remains the same as before)
patch(ProductScreen.prototype, {
     get controlButtons() {
        const originalButtons = super.controlButtons;
        const hasPendingItemsButton = originalButtons.some(btn => btn.component === PendingItemsButton);

        if (!hasPendingItemsButton) {
             return [
                {
                    component: PendingItemsButton,
                    condition: () => true,
                    position: "before",
                    reference: "SetFiscalPositionButton", // Adjust reference if needed
                },
                ...originalButtons,
            ];
        }
        return originalButtons;
     }
});