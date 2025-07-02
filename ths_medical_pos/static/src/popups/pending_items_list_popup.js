/** @odoo-module */

import {Component} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import {useService} from "@web/core/utils/hooks";

export class PendingItemsListPopup extends Component {
    constructor(...args) {
        console.log('PendingItemsListPopup: constructed with', args);
        super(...args);
    }

    static template = "ths_medical_pos.PendingItemsListPopup";
    static components = {Dialog};

    static props = {
        title: {type: String, optional: true},
        items: {type: Array, optional: true},
        close: Function,
        getPayload: {type: Function, optional: true},
    };

    static defaultProps = {
        title: _t("Pending Medical Items"),
        items: [],
    };

    setup() {
        console.log("PendingItemsListPopup: setup called");
        this.pos = usePos();
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    getProductById(productId) {
        try {
            // Use preloaded product data
            return this.pos.models["product.product"].get(productId);
        } catch (error) {
            console.error("Error accessing product by ID:", error);
            return null;
        }
    }

    async addProductToOrder(order, product, options = {}) {
        try {
            console.log("=== ERROR-FREE ODOO 18 ORDERLINE CREATION ===");
            console.log("Order lines before:", order.get_orderlines().length);

            const OrderLineModel = this.pos.models['pos.order.line'];
            if (!OrderLineModel) {
                throw new Error("pos.order.line model not found");
            }

            // Prepare complete orderline data - keep what works
            const lineData = {
                order_id: order,
                product_id: product,
                qty: options.quantity || 1,
                price_unit: options.price || product.lst_price || 0,
                discount: options.discount || 0,
                // Add medical extras
                ...(options.extras || {})
            };

            console.log("Creating orderline with data:", lineData);

            // WORKING METHOD: Use only OrderLineModel.create()
            const newOrderline = OrderLineModel.create(lineData);
            console.log("Created orderline instance:", newOrderline);

            // Verify it was added correctly
            const linesAfter = order.get_orderlines();
            console.log("Order lines after create():", linesAfter.length);

            if (linesAfter.length > 0) {
                const lastLine = order.get_last_orderline();
                console.log("Last orderline:", lastLine);

                if (lastLine && lastLine.product_id && lastLine.product_id.id === product.id) {
                    console.log("✅ SUCCESS: Orderline automatically added to order by create()!");
                    return lastLine;
                }
            }

            throw new Error("OrderLineModel.create() did not add line to order as expected");

        } catch (error) {
            console.error("❌ ERROR in addProductToOrder:", error);
            throw error;
        }
    }

    async setOrderlineNoteSafely(orderline, description) {
        if (!description || !orderline) {
            return;
        }

        try {
            // Method 1: Try direct property setting first (least reactive)
            if (orderline.note !== undefined) {
                orderline.note = description;
                console.log("✅ Set note via direct property");
                return;
            }

            // Method 2: Try setNote if available, with delay to avoid reactive conflicts
            if (typeof orderline.setNote === 'function') {
                setTimeout(() => {
                    try {
                        orderline.setNote(description);
                        console.log("✅ Set note via setNote (delayed)");
                    } catch (delayedError) {
                        console.log("⚠️ Delayed setNote failed:", delayedError.message);
                    }
                }, 100);
                return;
            }

            console.log("ℹ️ No note setting method available on orderline");

        } catch (error) {
            console.log("⚠️ Could not set note safely:", error.message);
        }
    }

    async addItemToOrder(item) {
        console.log("=== ADDING MEDICAL ITEM TO ORDER WITH ENCOUNTER INTEGRATION ===");
        console.log("Item:", item);

        const order = this.pos.get_order();
        const product = this.getProductById(item.product_id?.[0]);

        if (!product) {
            this.notification.add(
                _t("Product %s not found in POS", item.product_id?.[1] || "Unknown"),
                {type: "danger"}
            );
            return;
        }

        // Check customer
        const currentPartner = order.get_partner();
        if (currentPartner && currentPartner.id !== item.partner_id?.[0]) {
            this.notification.add(
                _t("Item is for %s, current customer is %s. Proceeding anyway.",
                    item.partner_id?.[1], currentPartner.name),
                {type: "warning"}
            );
        }

        try {
            const orderline = await this.addProductToOrder(order, product, {
                quantity: item.qty,
                price: item.price_unit,
                discount: item.discount || 0,
                extras: {
                    ths_pending_item_id: item.id,
                    ths_patient_id: item.patient_id?.[0],
                    ths_provider_id: item.practitioner_id?.[0],
                    ths_commission_pct: item.commission_pct || 0,
                    encounter_id: item.encounter_id?.[0],
                },
            });

            if (!orderline) {
                throw new Error("Failed to create orderline");
            }

            // Update order header with encounter data if not already set
            if (item.encounter_id?.[0] && !order.encounter_id) {
                order.encounter_id = item.encounter_id[0];

                // Get encounter data from preloaded data
                const encounter = this.pos.models["ths.medical.base.encounter"].get(item.encounter_id[0]);
                if (encounter) {
                    order.patient_ids = encounter.patient_ids_formatted || [];
                    order.practitioner_id = encounter.practitioner_id || null;
                    order.room_id = encounter.room_id || null;
                }
            }

            await this.setOrderlineNoteSafely(orderline, item.description);

            console.log("⚠️ NOTE: Item will be marked as 'processed' only when order is paid/finalized");
            this.notification.add(_t("Item added to order and linked to encounter"), {type: "success"});

            // Remove from popup - update preloaded data
            this.pos.models["ths.pending.pos.item"].delete(item.id);
            const index = this.props.items.findIndex(i => i.id === item.id);
            if (index !== -1) {
                this.props.items.splice(index, 1);
            }

            // Close popup if empty
            if (!this.props.items.length) {
                this.props.close();
            }

        } catch (error) {
            console.error("❌ ERROR adding item to order:", error);
            this.notification.add(
                _t("Could not add item to order: %s", error.message),
                {type: "danger"}
            );
        }
    }

    cancel() {
        this.props.close();
    }

    close() {
        this.props.close();
    }

    get itemsToShow() {
        return this.props.items;
    }

    formatCurrency(amount) {
        try {
            if (this.pos && this.pos.format_currency_no_symbol) {
                return this.pos.currency.symbol + " " + this.pos.format_currency_no_symbol(amount);
            } else if (this.pos && this.pos.currency) {
                const formattedAmount = parseFloat(amount || 0).toFixed(this.pos.currency.decimal_places || 2);
                return this.pos.currency.symbol + " " + formattedAmount;
            } else {
                return parseFloat(amount || 0).toFixed(2);
            }
        } catch (error) {
            console.error("Error formatting currency:", error);
            return parseFloat(amount || 0).toFixed(2);
        }
    }
}

console.log("Loaded pending_items_list_popup.js", "pending_items_list_popup.js");

// TODO: Add encounter timeline display in pending items popup
// TODO: Implement pending item grouping by service type
// TODO: Add pending item batch selection functionality
// TODO: Implement pending item quick edit from popup