/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PendingItemsButton } from "@ths_medical_pos/components/pending_items_button/pending_items_button";
import { AppointmentCalendarButton } from "@ths_medical_pos/components/appointment_calendar_button/appointment_calendar_button";
import { AppointmentScreenButton } from "@ths_medical_pos/components/appointment_screen_button/appointment_screen_button";

// Patch ProductScreen to add medical POS components
patch(ProductScreen, {
    components: {
        ...ProductScreen.components,
        PendingItemsButton,
        AppointmentCalendarButton,
        AppointmentScreenButton,
    }
});

// Patch ProductScreen prototype to add medical functionality
patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        console.log("Medical POS: ProductScreen patched successfully with medical components");
    },

    /**
     * Navigate to the appointment screen
     */
    showAppointmentScreen() {
        this.pos.showScreen('AppointmentScreen');
    }
});