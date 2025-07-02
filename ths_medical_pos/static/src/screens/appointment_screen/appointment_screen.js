/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/screens/appointment_screen.js");

import {patch} from "@web/core/utils/patch";
import {PosStore} from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        console.log("Medical POS Store: Setup completed with medical appointments support");
    },

    /**
     * Open the medical appointments gantt view
     * Similar to pos_restaurant_appointment's manageBookings method
     */
    async manageMedicalAppointments() {
        console.log("Medical POS: Opening medical appointments gantt view");

        // Clear any order transfer state
        this.orderToTransferUuid = null;

        // Set the screen to ActionScreen with medical appointments action
        this.showScreen("ActionScreen", {actionName: "ManageMedicalAppointments"});

        try {
            // Call the backend method to get the gantt action using preloaded models approach
            const action = await this.data.call("calendar.event", "action_open_medical_gantt_view", [false], {
                context: {
                    // Pass any relevant context
                    default_appointment_status: 'draft',
                    appointment_booking_gantt_show_all_resources: true,
                    active_model: 'appointment.type'
                },
            });

            // Execute the action to open the gantt view
            await this.action.doAction(action);

            console.log("Medical POS: Successfully opened medical gantt view");
        } catch (error) {
            console.error("Medical POS: Error opening medical appointments gantt view:", error);

            // Use notification service if available
            if (this.notification) {
                this.notification.add(
                    "Error opening medical appointments view. Please try again.",
                    {type: 'danger'}
                );
            } else {
                console.error("Notification service not available");
            }
        }
    },

    /**
     * Get daily appointments for display in POS
     */
    getDailyAppointments(date = null) {
        const appointments = this.models["calendar.event"]?.getAll() || [];

        if (!date) {
            date = new Date().toISOString().split('T')[0]; // Today's date
        }

        return appointments.filter(appointment => {
            if (!appointment.start) return false;

            const appointmentDate = new Date(appointment.start).toISOString().split('T')[0];
            return appointmentDate === date &&
                appointment.appointment_status !== 'cancelled_by_patient' &&
                appointment.appointment_status !== 'cancelled_by_clinic';
        }).map(appointment => {
            // Helper function to format patient names
            const formatPatientNames = (patientIds) => {
                if (!patientIds || !Array.isArray(patientIds)) {
                    return [];
                }
                return patientIds.map(patient => {
                    if (Array.isArray(patient) && patient.length >= 2) {
                        return patient[1]; // [id, name] format
                    } else if (patient && typeof patient === 'object' && patient.name) {
                        return patient.name; // {id: x, name: y} format
                    }
                    return 'Unknown Patient';
                });
            };

            // Format for display
            return {
                id: appointment.id,
                name: appointment.name || 'Unnamed Appointment',
                start_time: new Date(appointment.start).toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit'
                }),
                partner_name: Array.isArray(appointment.partner_id) ? appointment.partner_id[1] : 'Unknown',
                practitioner_name: Array.isArray(appointment.ths_practitioner_id) ? appointment.ths_practitioner_id[1] : 'No Practitioner',
                room_name: Array.isArray(appointment.ths_room_id) ? appointment.ths_room_id[1] : 'No Room',
                status: appointment.appointment_status || 'draft',
                encounter_id: Array.isArray(appointment.encounter_id) ? appointment.encounter_id[0] : appointment.encounter_id,
                // FIX 1: Use local helper function instead of this.formatPatientIds
                patient_names: formatPatientNames(appointment.ths_patient_ids || [])
            };
        }).sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
});

console.log("Medical POS: Appointment screen functionality loaded");