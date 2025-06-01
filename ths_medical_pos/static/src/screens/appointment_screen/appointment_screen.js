/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.js");

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        console.log("Medical POS Store: Setup completed with medical appointments support");
    },

    /**
     * Open the medical appointments gantt view
     */
    async manageMedicalAppointments() {
        console.log("Medical POS: Opening medical appointments gantt view");

        // Clear any order transfer state
        this.orderToTransferUuid = null;

        // Set the screen to ActionScreen with medical appointments action
        this.showScreen("ActionScreen", { actionName: "ManageMedicalAppointments" });

        try {
            // Call the backend method to get the gantt action
            const action = await this.data.call("calendar.event", "action_open_medical_gantt_view", [false], {
                context: {
                    default_ths_status: 'scheduled',
                    appointment_booking_gantt_show_all_resources: true,
                    active_model: 'appointment.type'
                },
            });

            // Execute the action to open the gantt view
            await this.action.doAction(action);

            console.log("Medical POS: Successfully opened medical gantt view");
        } catch (error) {
            console.error("Medical POS: Error opening medical appointments gantt view:", error);
            this.notification.add(
                "Error opening medical appointments view. Please try again.",
                { type: 'danger' }
            );
        }
    },
});