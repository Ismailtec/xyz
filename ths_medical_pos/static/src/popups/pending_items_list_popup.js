/** @odoo-module */

/*
 *
 * ANALYSIS OF USER LOGS:
 * ✅ OrderLineModel.create() works perfectly (2→3 lines, no duplication)
 * ❌ BUT: triggers "pl.payment_method_id is undefined" in customer display system
 *
 * SOLUTION: Keep working orderline creation, avoid triggering payment errors
 */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class PendingItemsListPopup extends Component {
    constructor(...args) {
        console.log('PendingItemsListPopup: constructed with', args);
        super(...args);
    }

    static template = "ths_medical_pos.PendingItemsListPopup";
    static components = { Dialog };

    static props = {
        title: { type: String, optional: true },
        items: { type: Array, optional: true }, // Made optional to allow default value
        close: Function,
        getPayload: { type: Function, optional: true },
    };

    static defaultProps = {
        title: _t("Pending Medical Items"),
        items: [], // Now valid since items is optional
    };

    setup() {
        console.log("PendingItemsListPopup: setup called");
        this.pos = usePos();
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Get product using POS database - the reliable method
     */
    getProductById(productId) {
        try {
            if (this.pos.db && typeof this.pos.db.get_product_by_id === 'function') {
                console.log("Using pos.db.get_product_by_id...");
                return this.pos.db.get_product_by_id(productId);
            }

            if (this.pos.models && this.pos.models['product.product']) {
                console.log("Using pos.models['product.product']...");
                const products = this.pos.models['product.product'].getAll();
                return products.find(p => p.id === productId);
            }

            console.error("Product not found with ID:", productId);
            return null;
        } catch (error) {
            console.error("Error accessing product by ID:", error);
            return null;
        }
    }

    /**
     * WORKING: OrderLineModel.create() with error prevention
     */
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

    /**
     * SAFE note setting that avoids triggering payment errors
     */
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
                // Use setTimeout to avoid immediate reactive update conflicts
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

            // Method 3: Try set_note if available
            if (typeof orderline.set_note === 'function') {
                setTimeout(() => {
                    try {
                        orderline.set_note(description);
                        console.log("✅ Set note via set_note (delayed)");
                    } catch (delayedError) {
                        console.log("⚠️ Delayed set_note failed:", delayedError.message);
                    }
                }, 100);
                return;
            }

            console.log("ℹ️ No note setting method available on orderline");

        } catch (error) {
            console.log("⚠️ Could not set note safely:", error.message);
            // Don't throw - note is not critical
        }
    }

    /**
     * Add pending medical item to POS order - FIXED TRACEABILITY VERSION
     * Now properly handles the new traceability logic where items are only marked
     * as 'processed' when the order is finalized, not when added to cart
     */
    async addItemToOrder(item) {
        console.log("=== ADDING MEDICAL ITEM TO ORDER WITH ENCOUNTER INTEGRATION ===");
        console.log("Item:", item);

        const order = this.pos.get_order();
        const product = this.getProductById(item.product_id?.[0]);

        if (!product) {
            this.notification.add(
                _t("Product %s not found in POS", item.product_id?.[1] || "Unknown"),
                { type: "danger" }
            );
            return;
        }

        console.log("Found product:", product);
        console.log("Current order:", order);
        console.log("Order has", order.get_orderlines().length, "existing lines");

        // Check customer
        const currentPartner = order.get_partner();
        if (currentPartner && currentPartner.id !== item.partner_id?.[0]) {
            this.notification.add(
                _t("Item is for %s, current customer is %s. Proceeding anyway.",
                   item.partner_id?.[1], currentPartner.name),
                { type: "warning" }
            );
        }

        try {
            // Use the WORKING approach - OrderLineModel.create() only
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

            console.log("✅ SUCCESS: Added orderline:", orderline);
            console.log("Order now has", order.get_orderlines().length, "lines");

            // SAFE note setting - avoid triggering payment errors
            await this.setOrderlineNoteSafely(orderline, item.description);

            // Update backend status ONLY AFTER successful addition
            // Do NOT update backend status immediately
            // Items will be marked as 'processed' only when order is finalized/paid
            console.log("⚠️ NOTE: Item will be marked as 'processed' only when order is paid/finalized");
            //await this.orm.write("ths.pending.pos.item", [item.id], { state: "processed" });
            this.notification.add(_t("Item added to order and linked to encounter"), { type: "success" });

            // Remove from popup
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
                { type: "danger" }
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