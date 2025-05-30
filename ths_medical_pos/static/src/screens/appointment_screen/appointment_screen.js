/** @odoo-module */

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";

/**
 * Appointment Screen Component for Medical POS
 * Displays a full calendar view of medical appointments with drag-drop functionality
 * Requires FullCalendar library to be loaded in assets
 */
export class AppointmentScreen extends Component {
    static template = "ths_medical_pos.AppointmentScreen";

    setup() {
        // Latest Odoo 18 POS hook pattern
        this.pos = usePos();

        // Latest Odoo 18 service injection patterns - CORRECT USAGE
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialogService = useService("dialog"); // CORRECT: dialog service usage in Odoo 18

        // DOM reference for calendar container
        this.calendarRef = useRef("calendar-container");
        this.calendarInstance = null;

        // Component state using latest OWL 3 patterns
        this.state = useState({
            appointments: [],
            isLoading: false,
            calendarView: 'timeGridWeek',
            calendarDate: new Date(),
            selectedPractitionerIds: [],
            selectedRoomIds: [],
        });

        // Latest OWL 3 lifecycle hooks
        onWillStart(async () => {
            await this.fetchAppointments();
        });

        onMounted(() => {
            // Use requestAnimationFrame for DOM-ready operations
            requestAnimationFrame(() => {
                this.initializeCalendar();
            });
        });

        onWillUnmount(() => {
            this.destroyCalendar();
        });
    }

    /**
     * Initialize FullCalendar with latest configuration
     * Uses modern FullCalendar v6+ API patterns
     */
    initializeCalendar() {
        if (!window.FullCalendar) {
            console.error("FullCalendar library not loaded in assets");
            this.notification.add(_t("Calendar library failed to load."), {
                type: 'danger'
            });
            return;
        }

        if (!this.calendarRef.el) {
            console.error("Calendar container element not found");
            return;
        }

        this.destroyCalendar(); // Ensure clean state

        try {
            const calendarEl = this.calendarRef.el;

            this.calendarInstance = new window.FullCalendar.Calendar(calendarEl, {
                // Latest FullCalendar configuration patterns
                initialView: this.state.calendarView,
                initialDate: this.state.calendarDate,

                // Modern header toolbar configuration
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
                },

                // View-specific configurations
                views: {
                    timeGridWeek: {
                        slotMinTime: '08:00:00',
                        slotMaxTime: '18:00:00',
                        slotDuration: '00:30:00'
                    },
                    dayGridMonth: {
                        dayMaxEvents: 3
                    }
                },

                // Event data source
                events: this.mapAppointmentsToCalendar(this.state.appointments),

                // Latest interaction patterns
                navLinks: true,
                editable: true,
                selectable: true,
                selectMirror: true,
                dayMaxEvents: true,

                // Event handlers using latest patterns
                eventClick: (info) => this.onEventClick(info.event),
                dateClick: (info) => this.onDateClick(info),
                select: (info) => this.onDateSelect(info),
                eventDrop: (info) => this.onEventChange(info),
                eventResize: (info) => this.onEventChange(info),

                // Localization using latest patterns
                locale: this.env.services.user.context.lang?.replace(/_/g, '-') || 'en-US',
                timeZone: 'local',

                // Modern styling
                height: 'auto',
                aspectRatio: 1.8,
            });

            this.calendarInstance.render();

        } catch (error) {
            console.error("Calendar initialization failed:", error);
            this.notification.add(
                _t("Failed to initialize calendar: %(error)s", {
                    error: error.message || error
                }),
                { type: 'danger' }
            );
        }
    }

    /**
     * Safely destroy calendar instance
     */
    destroyCalendar() {
        if (this.calendarInstance) {
            try {
                this.calendarInstance.destroy();
            } catch (error) {
                console.warn("Error destroying calendar:", error);
            } finally {
                this.calendarInstance = null;
            }
        }
    }

    /**
     * Map Odoo appointments to FullCalendar event format
     * Uses latest appointment data structure
     */
    mapAppointmentsToCalendar(appointments) {
        return appointments.map(appointment => ({
            id: appointment.id,
            title: appointment.display_name || appointment.name,
            start: appointment.start,
            end: appointment.stop,
            allDay: appointment.allday || false,

            // Extended properties for medical context
            extendedProps: {
                odoo_id: appointment.id,
                status: appointment.ths_status,
                patient: appointment.ths_patient_id?.[1] || null,
                practitioner: appointment.ths_practitioner_id?.[1] || null,
                room: appointment.ths_room_id?.[1] || null,
                owner: appointment.partner_id?.[1] || null,
            },

            // Status-based styling
            backgroundColor: this.getStatusColor(appointment.ths_status),
            borderColor: this.getStatusColor(appointment.ths_status),
            textColor: this.getTextColor(appointment.ths_status),
        }));
    }

    /**
     * Get color based on appointment status
     * Uses modern medical appointment status colors
     */
    getStatusColor(status) {
        const statusColors = {
            'scheduled': '#3498db',    // Blue
            'confirmed': '#2ecc71',    // Green
            'checked_in': '#f39c12',   // Orange
            'in_progress': '#e74c3c',  // Red
            'completed': '#95a5a6',    // Gray
            'billed': '#34495e',       // Dark gray
            'cancelled_by_patient': '#bdc3c7',
            'cancelled_by_clinic': '#bdc3c7',
            'no_show': '#ecf0f1',
        };
        return statusColors[status] || '#3498db';
    }

    /**
     * Get text color for readability
     */
    getTextColor(status) {
        const lightStatuses = ['no_show', 'cancelled_by_patient', 'cancelled_by_clinic'];
        return lightStatuses.includes(status) ? '#2c3e50' : '#ffffff';
    }

    /**
     * Fetch appointments using latest ORM patterns
     * Implements efficient domain filtering and field selection
     */
    async fetchAppointments() {
        this.state.isLoading = true;

        try {
            const domain = this.buildAppointmentDomain();
            const fields = [
                'id', 'display_name', 'name', 'start', 'stop', 'duration',
                'partner_id', 'ths_patient_id', 'ths_practitioner_id',
                'ths_room_id', 'ths_status', 'allday'
            ];

            const appointments = await this.orm.searchRead(
                'calendar.event',
                domain,
                fields,
                {
                    context: this.env.services.user.context,
                    order: 'start ASC'
                }
            );

            this.state.appointments = appointments || [];

            // Update calendar if initialized
            if (this.calendarInstance) {
                this.calendarInstance.removeAllEventSources();
                this.calendarInstance.addEventSource(
                    this.mapAppointmentsToCalendar(appointments)
                );
            }

        } catch (error) {
            console.error("Failed to fetch appointments:", error);
            this.notification.add(_t("Error loading appointments."), { type: 'danger' });
            this.state.appointments = [];
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Build domain for appointment filtering
     * Uses latest domain construction patterns
     */
    buildAppointmentDomain() {
        // Get date range from calendar view
        let startDate, endDate;

        if (this.calendarInstance?.view) {
            startDate = this.calendarInstance.view.activeStart;
            endDate = this.calendarInstance.view.activeEnd;
        } else {
            // Default to current week
            const now = new Date();
            startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7);
            endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 14);
        }

        const formatForOdoo = (date) => date.toISOString().slice(0, 19).replace('T', ' ');

        let domain = [
            ['start', '<=', formatForOdoo(endDate)],
            ['stop', '>=', formatForOdoo(startDate)],
            // Remove vet-specific filtering - this should be in vet extension
        ];

        // Apply filters
        if (this.state.selectedPractitionerIds.length > 0) {
            domain.push(['ths_practitioner_id', 'in', this.state.selectedPractitionerIds]);
        }

        if (this.state.selectedRoomIds.length > 0) {
            domain.push(['ths_room_id', 'in', this.state.selectedRoomIds]);
        }

        return domain;
    }

    /**
     * Handle calendar event click using ACTUAL Odoo 18 dialog patterns
     */
    async onEventClick(event) {
        const appointmentId = event.extendedProps?.odoo_id;
        if (!appointmentId) {
            console.error("Missing appointment ID in event");
            return;
        }

        try {
            // CORRECT Odoo 18 pattern: Import registered components from registry
            const { AppointmentDetailPopup } = registry.category("popups").get("AppointmentDetailPopup");

            // CORRECT Odoo 18 dialog service usage
            this.dialogService.add(AppointmentDetailPopup, {
                title: _t("Appointment: %(name)s", { name: event.title }),
                eventId: appointmentId,
            });
        } catch (error) {
            console.error("Failed to open appointment details:", error);
            this.notification.add(_t("Error opening appointment details."), { type: 'danger' });
        }
    }

    /**
     * Handle date click for new appointment creation
     */
    async onDateClick(info) {
        await this.createNewAppointment(info.dateStr);
    }

    /**
     * Handle date range selection
     */
    async onDateSelect(info) {
        await this.createNewAppointment(info.startStr, info.endStr);
    }

    /**
     * Handle event drag/resize using latest ORM update patterns
     */
    async onEventChange(info) {
        const appointmentId = info.event.extendedProps?.odoo_id;
        if (!appointmentId) {
            console.error("Cannot update: Missing appointment ID");
            info.revert();
            return;
        }

        const updateData = {
            start: info.event.start.toISOString().slice(0, 19).replace('T', ' '),
            stop: info.event.end?.toISOString().slice(0, 19).replace('T', ' ') || null,
        };

        try {
            await this.orm.write('calendar.event', [appointmentId], updateData);
            this.notification.add(_t("Appointment updated successfully."), {
                type: 'success',
                duration: 2000
            });
        } catch (error) {
            console.error("Failed to update appointment:", error);
            this.notification.add(_t("Failed to save changes."), { type: 'danger' });
            info.revert();
        }
    }

    /**
     * Create new appointment using ACTUAL Odoo 18 dialog patterns
     */
    async createNewAppointment(start = null, end = null) {
        try {
            // CORRECT Odoo 18 pattern: Get component from registry
            const { AppointmentCreatePopup } = registry.category("popups").get("AppointmentCreatePopup");

            // CORRECT Odoo 18 dialog service usage
            const result = await this.dialogService.add(AppointmentCreatePopup, {
                title: _t("Create New Appointment"),
                start: start,
                end: end,
            });

            if (result?.created) {
                await this.fetchAppointments();
            }
        } catch (error) {
            console.error("Failed to create appointment:", error);
            this.notification.add(_t("Error creating appointment."), { type: 'danger' });
        }
    }

    /**
     * Navigate back to ProductScreen using latest navigation patterns
     */
    back() {
        this.pos.showScreen('ProductScreen');
    }

    /**
     * Refresh appointments data
     */
    async refreshAppointments() {
        await this.fetchAppointments();
        this.notification.add(_t("Appointments refreshed."), {
            type: 'info',
            duration: 1500
        });
    }
}

// Register the screen component in the POS screens registry
registry.category("pos_screens").add("AppointmentScreen", AppointmentScreen);