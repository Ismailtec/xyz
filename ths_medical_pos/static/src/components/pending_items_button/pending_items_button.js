/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
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
        const order = this.pos.get_order();
        const client = order?.get_partner?.();
        const domain = [['state', '=', 'pending']];
        let popupTitle = _t('Pending Medical Items');

        if (client?.id) {
            domain.push(['partner_id', '=', client.id]);
            popupTitle = _t("Pending Items for %(partnerName)s", { partnerName: client.name });
        }

        try {
            const items = await this.orm.searchRead("ths.pending.pos.item", domain, [
                "id", "display_name", "encounter_id", "appointment_id",
                "partner_id", "patient_id", "product_id", "description",
                "qty", "price_unit", "discount", "practitioner_id",
                "commission_pct", "state",
            ]);

            if (items.length) {
                await this.popup.add(PendingItemsListPopup, {
                    title: popupTitle,
                    items,
                });
            } else {
                this.notification.add(
                    client
                        ? _t("No pending items for %(partner)s", { partner: client.name })
                        : _t("No pending medical items found."),
                    { type: "warning" }
                );
            }
        } catch (error) {
            console.error("Error fetching pending items", error);
            this.notification.add(_t("Failed to fetch pending items."), { type: "danger" });
        }
    }
}


registry.category("pos_components").add("PendingItemsButton", PendingItemsButton);