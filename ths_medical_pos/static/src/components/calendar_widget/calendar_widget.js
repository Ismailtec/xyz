/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.js");

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class MedicalCalendarWidget extends Component {
    static template = "ths_medical_pos.MedicalCalendarWidget";
    static props = {};

    setup() {
        this.pos = usePos();
        this.calendarRef = useRef("calendar");

        onMounted(() => {
            this.initializeCalendar();
        });
    }

    async initializeCalendar() {
        if (window.FullCalendar && this.calendarRef.el) {
            const calendar = new window.FullCalendar.Calendar(this.calendarRef.el, {
                initialView: 'dayGridMonth',
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay'
                },
                events: async (info, successCallback, failureCallback) => {
                    try {
                        const events = await this.fetchEvents(info.start, info.end);
                        successCallback(events);
                    } catch (error) {
                        failureCallback(error);
                    }
                },
                eventClick: (info) => {
                    this.onEventClick(info.event);
                }
            });
            calendar.render();
        }
    }

    async fetchEvents(start, end) {
        const domain = [
            ['start', '>=', start.toISOString()],
            ['stop', '<=', end.toISOString()],
            ['ths_patient_id', '!=', false]
        ];

        const events = await this.env.services.orm.searchRead(
            'calendar.event',
            domain,
            ['name', 'start', 'stop', 'ths_patient_id', 'appointment_status'],
            { limit: 100 }
        );

        return events.map(event => ({
            id: event.id,
            title: event.name,
            start: event.start,
            end: event.stop,
            color: this.getStatusColor(event.appointment_status),
            extendedProps: {
                patient: event.ths_patient_id,
                status: event.appointment_status
            }
        }));
    }

    getStatusColor(status) {
        const colors = {
            'scheduled': '#007bff',
            'confirmed': '#28a745',
            'checked_in': '#ffc107',
            'in_progress': '#fd7e14',
            'completed': '#6c757d',
            'cancelled': '#dc3545',
            'no_show': '#6c757d'
        };
        return colors[status] || '#007bff';
    }

    onEventClick(event) {
        console.log("Appointment clicked:", event);
        // You can show appointment details or navigate
    }
}

registry.category("pos_widgets").add("MedicalCalendarWidget", MedicalCalendarWidget);