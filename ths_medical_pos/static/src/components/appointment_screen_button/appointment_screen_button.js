/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/components/appointment_screen_button/appointment_screen_button.js");

import { Component, useState, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { AppointmentDetailPopup } from "@ths_medical_pos/popups/appointment_detail_popup";
import { AppointmentCreatePopup } from "@ths_medical_pos/popups/appointment_create_popup";

export class AppointmentScreenButton extends Component {
    static template = "ths_medical_pos.AppointmentScreenButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
        this.orm = useService("orm");

        this.state = useState({
            todayAppointments: [],
            isLoading: false,
            showAppointmentsList: false,
        });

        onMounted(() => {
            this.loadTodayAppointments();
        });
    }

    async loadTodayAppointments() {
        this.state.isLoading = true;
        try {
            const today = new Date();
            const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
            const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59);

            const formatForOdoo = (date) => date.toISOString().slice(0, 19).replace('T', ' ');

            const domain = [
                ['ths_patient_id', '!=', false], // Only medical appointments
                ['start', '>=', formatForOdoo(startOfDay)],
                ['start', '<=', formatForOdoo(endOfDay)],
            ];

            const fieldsToFetch = [
                'id', 'display_name', 'start', 'stop', 'ths_status',
                'partner_id', 'ths_patient_id', 'ths_practitioner_id'
            ];

            const appointments = await this.orm.searchRead(
                'calendar.event',
                domain,
                fieldsToFetch,
                {
                    context: this.pos.user.context,
                    order: 'start ASC',
                    limit: 50
                }
            );

            this.state.todayAppointments = appointments || [];
            console.log(`Loaded ${this.state.todayAppointments.length} appointments for today`);

        } catch (error) {
            console.error("Error loading today's appointments:", error);
            this.notification.add(
                _t('Error loading appointments for today.'),
                { type: 'danger' }
            );
            this.state.todayAppointments = [];
        } finally {
            this.state.isLoading = false;
        }
    }

    async onClick() {
        console.log("Appointment Screen Button Clicked!");
        this.state.showAppointmentsList = !this.state.showAppointmentsList;

        if (this.state.showAppointmentsList && this.state.todayAppointments.length === 0) {
            await this.loadTodayAppointments();
        }
    }

    async onAppointmentClick(appointment) {
        console.log("Appointment clicked:", appointment);

        try {
            await this.popup.add(AppointmentDetailPopup, {
                title: _t("Appointment: %(name)s", { name: appointment.display_name }),
                eventId: appointment.id,
            });
        } catch (error) {
            console.error("Error opening appointment details:", error);
            this.notification.add(
                _t('Error opening appointment details.'),
                { type: 'danger' }
            );
        }
    }

    async onCreateNewAppointment() {
        console.log("Create new appointment clicked!");

        try {
            const result = await this.popup.add(AppointmentCreatePopup, {
                title: _t("New Appointment"),
                start: new Date(),
                end: null,
            });

            if (result && result.created) {
                this.notification.add(
                    _t("Appointment created successfully!"),
                    { type: 'success', duration: 3000 }
                );
                // Refresh the list
                await this.loadTodayAppointments();
            }
        } catch (error) {
            console.error("Error in create appointment flow:", error);
            this.notification.add(
                _t('Error creating appointment.'),
                { type: 'danger' }
            );
        }
    }

    async onRefreshAppointments() {
        console.log("Refresh appointments clicked!");
        await this.loadTodayAppointments();
        this.notification.add(
            _t("Appointments refreshed."),
            { type: 'info', duration: 2000 }
        );
    }

    formatAppointmentTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            const date = new Date(dateTimeStr);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            console.warn(`Could not format time: ${dateTimeStr}`, e);
            return dateTimeStr;
        }
    }

    getStatusBadgeClass(status) {
        switch (status) {
            case 'scheduled': return 'badge badge-info';
            case 'confirmed': return 'badge badge-success';
            case 'checked_in': return 'badge badge-warning';
            case 'in_progress': return 'badge badge-danger';
            case 'completed': return 'badge badge-secondary';
            case 'billed': return 'badge badge-dark';
            case 'cancelled_by_patient':
            case 'cancelled_by_clinic':
            case 'no_show': return 'badge badge-light text-dark';
            default: return 'badge badge-secondary';
        }
    }

    get appointmentCount() {
        return this.state.todayAppointments.length;
    }

    get hasAppointments() {
        return this.appointmentCount > 0;
    }
}

// Export the component for use in other modules
export { AppointmentScreenButton };