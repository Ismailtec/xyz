/** @odoo-module */

/**
 * IMPORTANT: This follows Odoo 18 OWL 3 patching methodology using @web/core/utils/patch.
 * This is the LATEST required approach for extending existing POS screens in Odoo 18.
 * The patch system allows extending components without breaking inheritance chains.
 */
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

/**
 * Patch ProductScreen to add medical functionality for base medical practices
 * Adds PendingItemsButton component to the ProductScreen interface
 */

patch(ProductScreen, {
    // REQUIRED: Components must be extended, not replaced
    components: {
        ...ProductScreen.components,
        PendingItemsButton,
    },

    setup() {
        super.setup();
        console.log("Medical POS: ProductScreen patched successfully with medical components");
    },


    async loadEncounterPendingItems(encounterId) {
        try {
            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                [
                    ['encounter_id', '=', encounterId],
                    ['state', '=', 'pending']
                ],
                ['product_id', 'qty', 'price_unit', 'description', 'practitioner_id', 'commission_pct'],
                { limit: 100 }
            );

            if (pendingItems.length > 0) {
                this.notification.add(
                    _t('%d pending items found for this encounter.', pendingItems.length),
                    { type: 'info' }
                );

                this.showPendingItems();
            }
        } catch (error) {
            console.error("Error loading encounter pending items:", error);
        }
    },

    // TODO: Add encounter service history popup in POS
    // TODO: Implement encounter-based product recommendations
    // TODO: Add encounter payment plan selection in POS
    // TODO: Implement encounter insurance validation in POS
    // TODO: Add encounter mobile POS integration
    // TODO: Implement encounter offline mode support
});
