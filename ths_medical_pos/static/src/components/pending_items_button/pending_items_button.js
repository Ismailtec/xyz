/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/components/pending_items_button/pending_items_button.js");

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { PendingItemsListPopup } from "@ths_medical_pos/popups/pending_items_list_popup";

export class PendingItemsButton extends Component {
    static template = "ths_medical_pos.PendingItemsButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    async onClick() {
        console.log("Pending Items Button Clicked!");

        const order = this.pos.get_order();
        const client = order.get_partner();

        let popupTitle = _t('Pending Medical Items (All)');
        let filterDomain = [['state', '=', 'pending']];

        if (client) {
            console.log(`Filtering pending items for customer: ${client.name} (ID: ${client.id})`);
            filterDomain.push(['partner_id', '=', client.id]);
            popupTitle = _t("Pending Items for %(partnerName)s", { partnerName: client.name });
        }

        try {
            const fieldsToFetch = [
                'id', 'display_name', 'encounter_id', 'appointment_id',
                'partner_id', 'patient_id', 'product_id', 'description',
                'qty', 'price_unit', 'discount', 'practitioner_id',
                'commission_pct', 'state',
            ];

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                filterDomain,
                fieldsToFetch,
                { limit: 100 }
            );

            if (pendingItems && pendingItems.length > 0) {
                // Use the new popup system
                await this.popup.add(PendingItemsListPopup, {
                    title: popupTitle,
                    items: pendingItems,
                });
            } else {
                const message = client ?
                    _t('No pending medical items found for %(partnerName)s.', { partnerName: client.name }) :
                    _t('No pending medical items found.');
                this.notification.add(message, { type: 'warning' });
            }

        } catch (error) {
            console.error("Error fetching pending items:", error);
            this.notification.add(
                _t('Error fetching pending items. Check connection or logs.'),
                { type: 'danger' }
            );
        }
    }
}

// Export the component for use in other modules
export { PendingItemsButton };