/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

/**
 * Button component for accessing pending medical items in POS
 * Displays pending items that need to be billed through POS
 */
export class PendingItemsButton extends Component {
    static template = "ths_medical_pos.PendingItemsButton";
    static props = {}; // Required for OWL 3 in Odoo 18
    static components = {}; // Required static property in OWL 3 - even if empty

    setup() {
        // Initialize POS store hook and required services
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Handle button click to fetch and display pending items
     * Filters items by current customer if one is selected
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
            const items = await this.orm.searchRead("ths.pending.pos.item", domain, [
                "id", "display_name", "encounter_id", "appointment_id",
                "partner_id", "patient_id", "product_id", "description",
                "qty", "price_unit", "discount", "practitioner_id",
                "commission_pct", "state",
            ]);

            if (items.length) {
                // Use dialog service to show pending items list
                await this.dialog.add("PendingItemsListPopup", {
                    title: popupTitle,
                    items,
                });
            } else {
                // Show notification when no items found
                this.notification.add(
                    client
                        ? _t("No pending items for %(partner)s", { partner: client.name })
                        : _t("No pending medical items found."),
                    { type: "warning" }
                );
            }
        } catch (error) {
            console.error("Error fetching pending items:", error);
            this.notification.add(_t("Failed to fetch pending items."), { type: "danger" });
        }
    }
}

// Register component for use in POS
registry.category("pos_components").add("PendingItemsButton", PendingItemsButton);