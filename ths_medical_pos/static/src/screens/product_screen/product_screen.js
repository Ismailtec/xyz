/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/screens/product_screen/product_screen.js");

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { registry } from "@web/core/registry";
import { PendingItemsButton } from "@ths_medical_pos/static/src/components/pending_items_button/pending_items_button";
import { AppointmentCalendarButton } from "@ths_medical_pos/static/src/components/appointment_calendar_button/appointment_calendar_button";
import { AppointmentScreenButton } from "@ths_medical_pos/static/src/components/appointment_screen_button/appointment_screen_button";

// Patch ProductScreen to add medical POS components
patch(ProductScreen, {
    components: {
        ...ProductScreen.components,
        PendingItemsButton,
        AppointmentCalendarButton,
        AppointmentScreenButton,
    }
});

// Patch ProductScreen prototype to add setup functionality
patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        console.log("Medical POS: ProductScreen patched successfully with medical components");
    }
});

registry.category("pos_screens").add("ProductScreen", ProductScreen);