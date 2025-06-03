/** @odoo-module */

/**
 * IMPORTANT: This follows Odoo 18 OWL 3 patching methodology using @web/core/utils/patch.
 * This is the LATEST required approach for extending existing POS screens in Odoo 18.
 * The patch system allows extending components without breaking inheritance chains.
 */
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";

/**
 * Patch ProductScreen to add medical functionality for base medical practices
 * Adds PendingItemsButton component to the ProductScreen interface
 */
patch(ProductScreen, {
    // REQUIRED: Components must be extended, not replaced, to maintain compatibility
    components: {
        ...ProductScreen.components, // Preserve existing components
        PendingItemsButton, // Add our medical button component
    },

    /**
     * Override setup to add medical-specific initialization
     * Must call super.setup() to maintain parent functionality
     */
    setup() {
        super.setup(); // REQUIRED: Call parent setup first
        console.log("Medical POS: ProductScreen patched successfully with medical components");
    },

    /**
     * Navigate to the appointment screen (for future implementation)
     * Base method for general medical practices
     */
    showAppointmentScreen() {
        console.log("Medical POS: Navigating to appointment screen");
        this.pos.showScreen("AppointmentScreen");
    },
});
