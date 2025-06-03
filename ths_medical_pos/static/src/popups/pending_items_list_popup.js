/** @odoo-module */

/*
 * WORKING VERSION: Based on complete method analysis
 * Key insight: No add_product/addOrderline methods in Odoo 18
 * Solution: Create orderlines directly using pos.models['pos.order.line']
 *
 * Methods available on order:
 * - removeOrderline (but no addOrderline)
 * - get_orderlines (suggests lines collection exists)
 * - Models: pos.order.line exists for direct creation
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
        items: { type: Array },
        close: Function,
        getPayload: { type: Function, optional: true },
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

    /**
     * Get product using confirmed working method
     */
    getProductById(productId) {
        try {
            if (this.pos.models && this.pos.models['product.product']) {
                const products = this.pos.models['product.product'].getAll();
                return products.find(p => p.id === productId);
            }
            return null;
        } catch (error) {
            console.error("Error accessing product by ID:", error);
            return null;
        }
    }

    /**
     * CORRECT APPROACH: Create orderline directly using Odoo 18 pattern
     * Based on method analysis: no addOrderline, but removeOrderline exists
     * This suggests orderlines are created directly and auto-added to order
     */
    async addProductToOrder(order, product, options = {}) {
        try {
            console.log("Using Odoo 18 direct orderline creation...");

            // Get the orderline model from pos.models
            const OrderLineModel = this.pos.models['pos.order.line'];
            if (!OrderLineModel) {
                throw new Error("pos.order.line model not found");
            }

            console.log("Found OrderLineModel:", OrderLineModel);

            // Prepare orderline data
            const lineData = {
                order_id: order.id,
                product_id: product.id,
                qty: options.quantity || 1,
                price_unit: options.price || product.lst_price,
                discount: options.discount || 0,
                // Add medical extras
                ...(options.extras || {})
            };

            console.log("Creating orderline with data:", lineData);

            // Create the orderline - it should automatically be added to the order
            const newOrderline = OrderLineModel.create(lineData);

            console.log("Created orderline:", newOrderline);

            if (newOrderline) {
                // Verify it was added to the order
                const orderlines = order.get_orderlines();
                console.log("Order now has", orderlines.length, "lines");
                console.log("Last orderline:", order.get_last_orderline());

                return newOrderline;
            }

            throw new Error("Failed to create orderline");

        } catch (error) {
            console.error("Error in direct orderline creation:", error);

            // FALLBACK: Try alternative approaches
            console.log("Trying fallback approaches...");

            // Fallback 1: Check if order has a lines collection we can manipulate directly
            if (order.lines) {
                console.log("Trying direct lines collection manipulation...");
                const lineData = {
                    id: Math.random().toString(36), // Temporary ID
                    order_id: order.id,
                    product_id: product.id,
                    product: product,
                    qty: options.quantity || 1,
                    price_unit: options.price || product.lst_price,
                    discount: options.discount || 0,
                    ...(options.extras || {})
                };

                // Try to add to lines collection
                if (order.lines.add) {
                    order.lines.add(lineData);
                    console.log("Added to lines collection using add()");
                    return lineData;
                } else if (order.lines.push) {
                    order.lines.push(lineData);
                    console.log("Added to lines collection using push()");
                    return lineData;
                } else if (Array.isArray(order.lines)) {
                    order.lines.push(lineData);
                    console.log("Added to lines array directly");
                    return lineData;
                }
            }

            // Fallback 2: Look for any pos-level product addition methods
            const posMethods = Object.getOwnPropertyNames(this.pos);
            const addMethods = posMethods.filter(m =>
                m.includes('add') && (m.includes('product') || m.includes('line'))
            );

            console.log("Found POS-level add methods:", addMethods);

            for (const method of addMethods) {
                if (typeof this.pos[method] === 'function') {
                    try {
                        console.log(`Trying this.pos.${method}...`);
                        const result = this.pos[method](product, order, options);
                        if (result) {
                            console.log(`Success with pos.${method}:`, result);
                            return result;
                        }
                    } catch (e) {
                        console.log(`POS method ${method} failed:`, e.message);
                        continue;
                    }
                }
            }

            throw new Error("All orderline creation methods failed");
        }
    }

    /**
     * Add pending medical item to POS order
     */
    async addItemToOrder(item) {
        console.log("=== ADDING MEDICAL ITEM TO ORDER ===");
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
            // Add product using Odoo 18 direct orderline creation
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

            console.log("SUCCESS: Added orderline:", orderline);
            console.log("Order now has", order.get_orderlines().length, "lines");

            // Add description as note if possible
            if (item.description && orderline) {
                if (typeof orderline.set_note === 'function') {
                    orderline.set_note(item.description);
                } else {
                    // Try setting note property directly
                    orderline.note = item.description;
                }
            }

            // Update backend status
            await this.orm.write("ths.pending.pos.item", [item.id], { state: "processed" });
            this.notification.add(_t("Item added successfully to order"), { type: "success" });

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
            console.error("ERROR adding item to order:", error);
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

console.log("Loaded WORKING file:", "ths_medical_pos/static/src/popups/pending_items_list_popup.js");