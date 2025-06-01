/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";

// Patch ProductScreen class to add PendingItemsButton and new methods
patch(ProductScreen, {
    components: {
        ...ProductScreen.components,
        PendingItemsButton,
    },

    setup() {
        this._super();
        console.log("Medical POS: ProductScreen patched successfully with medical components");
    },

    /**
     * Navigate to the appointment screen
     */
    showAppointmentScreen() {
        this.pos.showScreen("AppointmentScreen");
    },
});