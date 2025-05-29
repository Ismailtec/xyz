/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/screens/appointment_screen/appointment_screen.js");

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime, formatDate } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Domain } from "@web/core/domain"; // Import Domain utility

// !!! IMPORTANT !!!
// This code ASSUMES the FullCalendar v5+ library (window.FullCalendar) is loaded globally
// into the POS assets via your manifest file (using index.global.min.js).

export class AppointmentScreen extends Component {
    static template = "ths_medical_pos.AppointmentScreen";
    static hideOrderSelector = true;

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.calendarRef = useRef("calendar-container");
        this.calendarInstance = null;

        this.state = useState({
            appointments: [],
            isLoading: false,
            calendarView: 'timeGridWeek',
            calendarDate: new Date(),
            selectedPractitionerIds: [],
            selectedRoomIds: [],
        });

        onWillStart(async () => {
            await this.fetchAppointments();
        });

        onMounted(() => {
            requestAnimationFrame(() => {
                this.initializeCalendar();
            });
        });

        onWillUnmount(() => {
            if (this.calendarInstance) {
                this.calendarInstance.destroy();
                this.calendarInstance = null;
            }
        });
    }

    initializeCalendar() {
        if (!window.FullCalendar) {
            console.error("FullCalendar library is not loaded! Check manifest assets.");
            this.notification.add(_t("Calendar library failed to load."), { type: 'danger', sticky: true });
            return;
        }

        if (!this.calendarRef.el) {
            console.error("Calendar container element not found in template!");
            this.notification.add(_t("Calendar container failed to load."), { type: 'danger', sticky: true });
            return;
        }

        if (this.calendarInstance) {
            this.calendarInstance.destroy();
        }

        const calendarEl = this.calendarRef.el;
        const self = this;

        try {
            this.calendarInstance = new window.FullCalendar.Calendar(calendarEl, {
                initialView: self.state.calendarView,
                initialDate: self.state.calendarDate,
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
                },
                views: {
                    timeGridWeek: {},
                    dayGridMonth: {},
                    timeGridDay: {},
                    listWeek: {}
                },
                events: self.mapOdooEventsToFullCalendar(self.state.appointments),
                navLinks: true,
                editable: true,
                selectable: true,
                selectMirror: true,
                dayMaxEvents: true,
                eventClick: (info) => self.onEventClick(info.event),
                dateClick: (info) => self.onDateClick(info),
                select: (info) => self.onDateSelect(info),
                eventDrop: (info) => self.onEventDropOrResize(info.event, info.oldEvent, info.delta, info.revert),
                eventResize: (info) => self.onEventDropOrResize(info.event, info.oldEvent, info.endDelta, info.revert),
                locale: this.env.services.user.context.lang?.replace(/_/g, '-') || 'en',
                timeZone: 'local',
                contentHeight: 'auto',
            });

            this.calendarInstance.render();
        } catch (error) {
            console.error("Error initializing FullCalendar:", error);
            this.notification.add(_t("Failed to initialize calendar view: %(error)s", { error: error.message || error }), { type: 'danger' });
        }
    }

    mapOdooEventsToFullCalendar(odooEvents) {
        return odooEvents.map(event => ({
            id: event.id,
            title: event.display_name,
            start: event.start,
            end: event.stop,
            allDay: event.allday,
            extendedProps: {
                odoo_id: event.id,
                status: event.ths_status,
                patient: event.ths_patient_id ? event.ths_patient_id[1] : null,
                provider: event.ths_practitioner_id ? event.ths_practitioner_id[1] : null,
                room: event.ths_room_id ? event.ths_room_id[1] : null,
            },
            backgroundColor: this.getColorForStatus(event.ths_status),
            borderColor: this.getColorForStatus(event.ths_status),
        }));
    }

    getColorForStatus(status) {
        switch (status) {
            case 'scheduled': return '#3a87ad';
            case 'confirmed': return '#468847';
            case 'checked_in': return '#f89406';
            case 'in_progress': return '#b94a48';
            case 'completed': return '#777777';
            case 'billed': return '#333333';
            case 'cancelled_by_patient':
            case 'cancelled_by_clinic':
            case 'no_show': return '#cccccc';
            default: return '#3a87ad';
        }
    }

    async fetchAppointments() {
        this.state.isLoading = true;
        try {
            const domain = this._getAppointmentDomain(true);
            const fieldsToFetch = [
                'id', 'display_name', 'start', 'stop', 'duration', 'partner_id',
                'ths_patient_id', 'ths_practitioner_id', 'ths_room_id',
                'ths_status', 'allday',
            ];
            const fetchedAppointments = await this.orm.searchRead(
                'calendar.event',
                domain,
                fieldsToFetch,
                { context: this.env.services.user.context }
            );
            this.state.appointments = fetchedAppointments;

            if (this.calendarInstance) {
                this.calendarInstance.removeAllEventSources();
                this.calendarInstance.addEventSource(this.mapOdooEventsToFullCalendar(this.state.appointments));
            }

        } catch (error) {
            console.error("Error fetching appointments:", error);
            this.notification.add(_t("Error fetching appointments."), { type: 'danger' });
            this.state.appointments = [];
            if (this.calendarInstance) {
                this.calendarInstance.removeAllEventSources();
            }
        } finally {
            this.state.isLoading = false;
        }
    }

    _getAppointmentDomain(includeFilters = false) {
        let start, end;
        const view = this.calendarInstance?.view;
        if (view) {
            start = view.activeStart;
            end = view.activeEnd;
        } else {
            start = new Date(this.state.calendarDate);
            start.setDate(start.getDate() - 7);
            start.setHours(0,0,0,0);
            end = new Date(this.state.calendarDate);
            end.setDate(end.getDate() + 7);
            end.setHours(23,59,59,999);
        }

        const formatForOdoo = (date) => {
            if (!date) return false;
            return date.toISOString().slice(0, 19).replace('T', ' ');
        }

        const odooStartDate = formatForOdoo(start);
        const odooEndDate = formatForOdoo(end);

        if (!odooStartDate || !odooEndDate) {
            console.error("Could not determine date range for fetching appointments.");
            return [];
        }

        let domainList = [
            '&',
            ['start', '<=', odooEndDate],
            ['stop', '>=', odooStartDate],
        ];

        if (includeFilters) {
            if (this.state.selectedPractitionerIds && this.state.selectedPractitionerIds.length > 0) {
                domainList.push(['ths_practitioner_id', 'in', this.state.selectedPractitionerIds]);
            }
            if (this.state.selectedRoomIds && this.state.selectedRoomIds.length > 0) {
                domainList.push(['ths_room_id', 'in', this.state.selectedRoomIds]);
            }
        }

        const finalDomain = Domain.and(domainList);
        return finalDomain;
    }

    onPractitionerFilterChange(selectedIds) {
        this.state.selectedPractitionerIds = selectedIds;
        this.fetchAppointments();
    }

    onRoomFilterChange(selectedIds) {
        this.state.selectedRoomIds = selectedIds;
        this.fetchAppointments();
    }

    async onEventClick(event) {
        const odooEventId = event.extendedProps?.odoo_id;
        if (!odooEventId) {
            console.error("Could not get Odoo event ID from clicked calendar event.");
            this.notification.add(_t("Could not identify the clicked appointment."), { type: 'danger' });
            return;
        }

        const { AppointmentDetailPopup } = await import("@ths_medical_pos/static/src/popups/appointment_detail_popup");
        await this.pos.popup.add(AppointmentDetailPopup, {
            title: _t("Appointment: ") + event.title,
            eventId: odooEventId
        });
    }

    onDateClick(info) {
        this.createNewAppointment(info.dateStr);
    }

    onDateSelect(info) {
        this.createNewAppointment(info.startStr, info.endStr);
    }

    async onEventDropOrResize(event, oldEvent, delta, revertFunc) {
        const odooEventId = event.extendedProps?.odoo_id;
        if (!odooEventId) {
            console.error("Cannot update event: Missing Odoo ID.");
            if (typeof revertFunc === 'function') revertFunc();
            return;
        }

        const valuesToUpdate = {
            start: event.start.toISOString(),
            stop: event.end ? event.end.toISOString() : null,
        };

        this.notification.add(_t("Saving changes..."), {type:'info', sticky: false, duration: 1500});

        try {
            await this.orm.write('calendar.event', [odooEventId], valuesToUpdate);
            this.notification.add(_t("Appointment updated successfully."), {type:'success', sticky: false, duration: 3000});
            await this.fetchAppointments();

        } catch (error) {
            console.error("Error updating appointment:", error);
            this.notification.add(_t("Failed to save changes: %(message)s", { message: error.message || error }), { type: 'danger', sticky: true });
            if (typeof revertFunc === 'function') {
                revertFunc();
            } else {
                this.notification.add(_t("Refetching appointments to revert change."), { type: 'warning'});
                await this.fetchAppointments();
            }
        }
    }

    async createNewAppointment(start = null, end = null) {
        const { AppointmentCreatePopup } = await import("@ths_medical_pos/static/src/popups/appointment_create_popup");
        await this.pos.popup.add(AppointmentCreatePopup, {
            title: _t("Create New Appointment"),
            start: start,
            end: end,
            onConfirm: async () => {
                await this.fetchAppointments();
            }
        });
    }

    formatDisplayDateTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            const formattedStr = dateTimeStr.includes('T') ? dateTimeStr : dateTimeStr.replace(' ', 'T');
            return formatDateTime(formattedStr);
        } catch (e) {
            console.warn(`Could not format date: ${dateTimeStr}`, e);
            return dateTimeStr;
        }
    }

    back() {
        this.pos.showScreen('ProductScreen');
    }
}

registry.category("pos_screens").add("AppointmentScreen", AppointmentScreen);