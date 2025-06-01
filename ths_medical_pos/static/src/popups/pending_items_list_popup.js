/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class PendingItemsListPopup extends Component {
    static template = "ths_medical_pos.PendingItemsListPopup";

    static props = {
        title: { type: String, optional: true },
        items: { type: Array },
        close: Function,
    };

    static defaultProps = {
        title: _t("Pending Medical Items"),
        items: [],
    };

    static services = ["popup", "notification", "orm"];

    setup() {
        this.pos = usePos();
    }

    async addItemToOrder(item) {
        const order = this.pos.get_order();
        const product = this.pos.db.product_by_id[item.product_id?.[0]];

        if (!product) {
            this.popup.add("ErrorPopup", {
                title: _t("Product Not Found"),
                body: _t("Product %s not found in POS", item.product_id?.[1]),
            });
            return;
        }

        const currentPartner = order.get_partner();
        if (currentPartner && currentPartner.id !== item.partner_id?.[0]) {
            const { confirmed } = await this.popup.add("ConfirmPopup", {
                title: _t("Different Customer"),
                body: _t("Item is for %s, current customer is %s. Continue?", item.partner_id?.[1], currentPartner.name),
            });
            if (!confirmed) return;
        }

        const orderline = order.add_product(product, {
            quantity: item.qty,
            price: item.price_unit,
            discount: item.discount || 0,
            extras: {
                pending_item_id: item.id,
                practitioner_id: item.practitioner_id,
                commission_pct: item.commission_pct,
                patient_id: item.patient_id,
                encounter_id: item.encounter_id,
            },
        });

        if (item.description && orderline) {
            orderline.set_note(item.description);
        }

        try {
            await this.orm.write("ths.pending.pos.item", [item.id], { state: "processed" });
            this.notification.add(_t("Item added successfully"), { type: "success" });

            const index = this.props.items.findIndex(i => i.id === item.id);
            if (index !== -1) {
                this.props.items.splice(index, 1);
            }
            if (!this.props.items.length) this.props.close();

        } catch (error) {
            console.error("Error marking item as processed", error);
            this.popup.add("ErrorPopup", {
                title: _t("Update Error"),
                body: _t("Could not update item status."),
            });
        }
    }

    cancel() {
        this.props.close();
    }

    get itemsToShow() {
        return this.props.items;
    }

    formatCurrency(amount) {
        return this.pos.format_currency(amount);
    }
}

// Register popup for <PendingItemsListPopup/>
registry.category("popups").add("PendingItemsListPopup", PendingItemsListPopup);