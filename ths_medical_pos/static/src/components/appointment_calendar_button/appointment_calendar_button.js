/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/components/appointment_calendar_button/appointment_calendar_button.js");

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { AppointmentCreatePopup } from "@ths_medical_pos/static/src/popups/appointment_create_popup";

export class AppointmentCalendarButton extends Component {
    static template = "ths_medical_pos.AppointmentCalendarButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
        this.action = useService("action");
    }

    async onClick() {
        console.log("Appointment Calendar Button Clicked!");

        try {
            // Open calendar view for appointments
            await this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'calendar.event',
                name: _t('Appointments Calendar'),
                views: [[false, 'calendar'], [false, 'list'], [false, 'form']],
                target: 'current',
                domain: [
                    ['ths_patient_id', '!=', false], // Only medical appointments
                ],
                context: {
                    'default_ths_status': 'scheduled',
                    'calendar_default_mode': 'week',
                },
            });
        } catch (error) {
            console.error("Error opening calendar view:", error);
            this.notification.add(
                _t('Error opening appointments calendar.'),
                { type: 'danger' }
            );
        }
    }

    async onCreateAppointment() {
        console.log("Create Appointment clicked!");

        try {
            const result = await this.popup.add(AppointmentCreatePopup, {
                title: _t("New Appointment"),
                start: new Date(), // Default to current time
                end: null, // Will be calculated based on default duration
            });

            if (result && result.created) {
                this.notification.add(
                    _t("Appointment created successfully!"),
                    { type: 'success', duration: 3000 }
                );
            }
        } catch (error) {
            console.error("Error in create appointment flow:", error);
            this.notification.add(
                _t('Error creating appointment.'),
                { type: 'danger' }
            );
        }
    }
}

// Export the component for use in other modules
export { AppointmentCalendarButton };