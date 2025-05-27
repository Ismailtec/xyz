/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Button component to navigate to the Appointment Screen
export class AppointmentScreenButton extends Component {
    static template = "ths_medical_pos.AppointmentScreenButton";

    setup() {
        super.setup();
        this.pos = usePos();
        console.log("AppointmentScreenButton setup complete.");
    }

    async onClick() {
        console.log("Appointment Screen Button Clicked! Navigating...");
        // Use the showScreen method from the pos service (available via usePos)
        this.pos.showScreen('AppointmentScreen'); // Use the name registered for the screen
    }
}

// Add the button to the Product Screen's control buttons
patch(ProductScreen.prototype, {
     get controlButtons() {
        const originalButtons = super.controlButtons;
        // Avoid adding the button multiple times if patch runs again
        const hasButton = originalButtons.some(btn => btn.component === AppointmentScreenButton);

        if (!hasButton) {
            return [
                {
                    component: AppointmentScreenButton,
                    condition: () => true, // Always show for now
                    position: "before",
                    // Position near other relevant buttons, adjust reference as needed
                    reference: "PendingItemsButton", // Place near our other custom button
                },
                ...originalButtons,
            ];
        }
        return originalButtons;
     }
});