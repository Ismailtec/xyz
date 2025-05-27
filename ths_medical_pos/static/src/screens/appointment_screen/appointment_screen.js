/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen"; // Base screen reference (optional)
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl"; // Owl imports
import { useService } from "@web/core/utils/hooks"; // Odoo services hook
import { _t } from "@web/core/l10n/translation"; // Translation utility
import { formatDateTime, formatDate } from "@web/core/l10n/dates"; // Date formatting utilities
import { registry } from "@point_of_sale/app/store/registry"; // POS registry for screens/components
import { AppointmentDetailPopup } from "@ths_medical_pos/popups/appointment_detail_popup"; // Import the detail popup
import { AppointmentCreatePopup } from "@ths_medical_pos/popups/appointment_create_popup"; // Import the create popup
import { Domain } from "@web/core/domain"; // Import Domain utility

// !!! IMPORTANT !!!
// This code ASSUMES the FullCalendar v5+ library (window.FullCalendar) is loaded globally
// into the POS assets via your manifest file (using index.global.min.js).

export class AppointmentScreen extends Component {
    static template = "ths_medical_pos.AppointmentScreen"; // Links to the XML template

    setup() {
        super.setup();
        this.pos = usePos(); // Access POS state and methods
        this.orm = useService("orm"); // Access Odoo ORM for RPC calls
        this.notification = useService("notification"); // Odoo notification service
        this.calendarRef = useRef("calendar-container"); // Reference to the div in the XML template
        this.calendarInstance = null; // Variable to hold the FullCalendar object

        // Reactive state for the component
        this.state = useState({
            appointments: [], // Holds fetched appointment data
            isLoading: false, // Loading indicator flag
            calendarView: 'timeGridWeek', // Default calendar view (e.g., timeGridWeek, dayGridMonth)
            calendarDate: new Date(), // Default date for the calendar (today)
            // --- ADD FILTER STATE ---
            selectedPractitionerIds: [], // Array of selected practitioner IDs
            selectedRoomIds: [],       // Array of selected room IDs
        });

        console.log("AppointmentScreen setup.");
        // Log loaded resources for debugging filters later
        console.log("Loaded Practitioners:", this.pos.employees); // Check data/fields loaded
        console.log("Loaded Rooms:", this.pos.models['ths.treatment.room']); // Check data loaded

        // Fetch initial data before the component mounts
        onWillStart(async () => {
            await this.fetchAppointments();
        });

        // When the component is mounted to the DOM, initialize the calendar
        onMounted(() => {
             // Use requestAnimationFrame to ensure the DOM element is ready
            requestAnimationFrame(() => {
                this.initializeCalendar();
                console.log("AppointmentScreen mounted, calendar initialized.");
            });
        });

        // When the component is about to be unmounted, destroy the calendar instance
        onWillUnmount(() => {
            if (this.calendarInstance) {
                this.calendarInstance.destroy();
                this.calendarInstance = null;
                console.log("AppointmentScreen unmounted, calendar destroyed.");
            }
        });
    }

    // Method to initialize the FullCalendar instance
    initializeCalendar() {
        // Check if the FullCalendar library is loaded
        if (!window.FullCalendar) {
             console.error("FullCalendar library is not loaded! Check manifest assets.");
             this.notification.add(_t("Calendar library failed to load."), { type: 'danger', sticky: true });
             return;
        }
        // Check if the container element exists in the template
        if (!this.calendarRef.el) {
             console.error("Calendar container element (t-ref='calendar-container') not found in template!");
              this.notification.add(_t("Calendar container failed to load."), { type: 'danger', sticky: true });
             return;
        }
        // If an instance already exists (e.g., on re-render), destroy it first
        if (this.calendarInstance) {
             this.calendarInstance.destroy();
        }

        const calendarEl = this.calendarRef.el;
        const self = this; // Keep reference to 'this' for callbacks

        try {
             // Create the FullCalendar instance
             this.calendarInstance = new window.FullCalendar.Calendar(calendarEl, {
                // === Core Options ===
                initialView: self.state.calendarView, // Use state for initial view
                initialDate: self.state.calendarDate, // Use state for initial date
                headerToolbar: { // Define standard controls
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek' // View switcher
                },
                views: { // Ensure standard views are available
                    timeGridWeek: { /* options like slot duration, business hours etc. */ },
                    dayGridMonth: { /* options */ },
                    timeGridDay: { /* options */ },
                    listWeek: { /* options */ }
                },
                // === Data ===
                events: self.mapOdooEventsToFullCalendar(self.state.appointments), // Map fetched data
                // === Interaction Callbacks ===
                navLinks: true, // Click day/week names to navigate
                editable: true, // Allow drag & drop / resizing (requires backend save logic)
                selectable: true, // Allow selecting time slots (requires backend create logic)
                selectMirror: true,
                dayMaxEvents: true, // allow "more" link

                // Define actions for clicking events, dates, etc.
                // Pass the FullCalendar event object AND the revert function (for drop/resize)
                eventClick: (info) => self.onEventClick(info.event),
                dateClick: (info) => self.onDateClick(info),
                select: (info) => self.onDateSelect(info),
                eventDrop: (info) => self.onEventDropOrResize(info.event, info.oldEvent, info.delta, info.revert), // Pass revert
                eventResize: (info) => self.onEventDropOrResize(info.event, info.oldEvent, info.endDelta, info.revert), // Pass revert

                // === TimeZone & Locale ===
                 // Attempt to use Odoo's user language setting for locale
                locale: this.env.session.user_context.lang?.replace(/_/g, '-') || 'en',
                timeZone: 'local', // Use browser's local time zone (usually best for POS)

                // === Appearance ===
                contentHeight: 'auto', // Adjust height dynamically

                // === Other Options ===
                // Add more FullCalendar options here as needed
             });

             // Render the calendar
             this.calendarInstance.render();
             console.log("FullCalendar rendered.");

        } catch (error) {
            console.error("Error initializing FullCalendar:", error);
            this.notification.add(_t("Failed to initialize calendar view: %(error)s", { error: error.message || error }), { type: 'danger' });
        }
    }

    // Helper method to convert Odoo event data into FullCalendar event object format
    mapOdooEventsToFullCalendar(odooEvents) {
        return odooEvents.map(event => ({
            id: event.id, // Use Odoo ID as FullCalendar event ID
            title: event.display_name,
            start: event.start, // Expecting ISO 8601 or similar compatible string from Odoo
            end: event.stop,
            allDay: event.allday,
            // Store original Odoo data and computed values in extendedProps
            extendedProps: {
                odoo_id: event.id,
                status: event.ths_status,
                patient: event.ths_patient_id ? event.ths_patient_id[1] : null,
                provider: event.ths_practitioner_id ? event.ths_practitioner_id[1] : null,
                room: event.ths_room_id ? event.ths_room_id[1] : null,
                // Include any other data needed for popups or logic
            },
            // Set colors based on status using helper function
            backgroundColor: this.getColorForStatus(event.ths_status),
            borderColor: this.getColorForStatus(event.ths_status),
        }));
    }

    // Helper method to determine event color based on status
    getColorForStatus(status) {
        // (Keep existing color logic)
        switch (status) {
            case 'scheduled': return '#3a87ad'; // Blueish
            case 'confirmed': return '#468847'; // Greenish
            case 'checked_in': return '#f89406'; // Orange
            case 'in_progress': return '#b94a48'; // Reddish
            case 'completed': return '#777777'; // Grey
            case 'billed': return '#333333'; // Dark Grey/Black
            case 'cancelled_by_patient':
            case 'cancelled_by_clinic':
            case 'no_show': return '#cccccc'; // Light Grey
            default: return '#3a87ad'; // Default color
        }
    }

    // Method to fetch appointment data from Odoo backend
    async fetchAppointments() {
        this.state.isLoading = true; // Show loading indicator
        console.log("Fetching appointments...");
        try {
             // Pass true to indicate domain might have changed due to filters
            const domain = this._getAppointmentDomain(true);
            const fieldsToFetch = [ // List all fields needed for display and mapping
                'id', 'display_name', 'start', 'stop', 'duration', 'partner_id',
                'ths_patient_id', 'ths_practitioner_id', 'ths_room_id',
                'ths_status', 'allday',
            ];
            const fetchedAppointments = await this.orm.searchRead(
                'calendar.event', // Odoo model to fetch from
                domain,
                fieldsToFetch,
                { context: this.pos.user.context } // Include user context
            );
            console.log("Appointments fetched:", fetchedAppointments);
            this.state.appointments = fetchedAppointments; // Update component state

            // If calendar is already initialized, update its events
            if (this.calendarInstance) {
                 console.log("Updating FullCalendar events...");
                 // Remove old events and add the new ones
                 this.calendarInstance.removeAllEventSources();
                 this.calendarInstance.addEventSource(this.mapOdooEventsToFullCalendar(this.state.appointments));
            }

        } catch (error) {
            console.error("Error fetching appointments:", error);
            this.notification.add(_t("Error fetching appointments."), { type: 'danger' });
            this.state.appointments = []; // Clear data on error
            if (this.calendarInstance) { // Clear calendar events on error
                 this.calendarInstance.removeAllEventSources();
            }
        } finally {
            this.state.isLoading = false; // Hide loading indicator
        }
    }

    // Helper method to generate the domain for fetching appointments
    _getAppointmentDomain(includeFilters = false) {
        // Gets the visible date range from the FullCalendar instance if available
        let start, end;
        const view = this.calendarInstance?.view;
        if (view) {
             // Use FullCalendar's view properties
             start = view.activeStart;
             end = view.activeEnd;
             console.log(`Calendar view range: ${start?.toISOString()} - ${end?.toISOString()}`);
        } else { // Fallback for initial load or if instance not ready
             start = new Date(this.state.calendarDate); // Use state date as reference
             start.setDate(start.getDate() - 7); start.setHours(0,0,0,0);
             end = new Date(this.state.calendarDate);
             end.setDate(end.getDate() + 7); end.setHours(23,59,59,999);
             console.log(`Fallback date range: ${start.toISOString()} - ${end.toISOString()}`);
        }

        // Convert JS dates to Odoo compatible UTC string (YYYY-MM-DD HH:MM:SS)
        const formatForOdoo = (date) => {
            if (!date) return false;
             // Convert to UTC string suitable for Odoo backend query
             // Subtracting offset can be unreliable, toISOString() is already UTC
            return date.toISOString().slice(0, 19).replace('T', ' ');
        }

        const odooStartDate = formatForOdoo(start);
        const odooEndDate = formatForOdoo(end);

        if (!odooStartDate || !odooEndDate) {
             console.error("Could not determine date range for fetching appointments.");
             return []; // Return empty domain if dates are invalid
        }

        let domainList = [ // Use list to build domain parts
             '&',
                 ['start', '<=', odooEndDate], // Event starts before or exactly when the period ends
                 ['stop', '>=', odooStartDate],  // Event ends after or exactly when the period starts
        ];

        // --- ADD FILTER LOGIC ---
        if (includeFilters) {
             if (this.state.selectedPractitionerIds && this.state.selectedPractitionerIds.length > 0) {
                 console.log("Applying practitioner filter:", this.state.selectedPractitionerIds);
                 domainList.push(['ths_practitioner_id', 'in', this.state.selectedPractitionerIds]);
             }
             if (this.state.selectedRoomIds && this.state.selectedRoomIds.length > 0) {
                 console.log("Applying room filter:", this.state.selectedRoomIds);
                 domainList.push(['ths_room_id', 'in', this.state.selectedRoomIds]);
             }
        }
        // --- END FILTER LOGIC ---

        // Combine domain parts using Domain.and() utility if multiple filters added
        const finalDomain = Domain.and(domainList);
        console.log("Appointment fetch domain:", finalDomain);
        return finalDomain;
    }


    // --- Placeholder Filter Handlers ---
    // These would be called by actual filter UI components later
    onPractitionerFilterChange(selectedIds) {
         console.log("Practitioner filter changed:", selectedIds);
         this.state.selectedPractitionerIds = selectedIds;
         this.fetchAppointments(); // Refetch data when filter changes
    }
    onRoomFilterChange(selectedIds) {
        console.log("Room filter changed:", selectedIds);
         this.state.selectedRoomIds = selectedIds;
         this.fetchAppointments(); // Refetch data when filter changes
    }


    // --- Interaction Handlers ---

    // Called when a calendar event is clicked
    onEventClick(event) {
        const odooEventId = event.extendedProps?.odoo_id;
        console.log("Event Clicked in Screen, Odoo ID:", odooEventId);
        if (!odooEventId) {
            console.error("Could not get Odoo event ID from clicked calendar event.");
            this.notification.add(_t("Could not identify the clicked appointment."), { type: 'danger' });
            return;
        }
        // Show the detail popup
        this.pos.showPopup('AppointmentDetailPopup', {
            title: _t("Appointment: ") + event.title,
            eventId: odooEventId
        });
    }

    // Called when an empty date/time slot is clicked
    onDateClick(info) {
         console.log("Date Clicked in Screen:", info);
         // Trigger create new appointment popup, passing clicked date as start
         // Use info.dateStr which is usually an ISO string
         this.createNewAppointment(info.dateStr);
    }

     // Called when a range of dates/times is selected (dragged)
     onDateSelect(info) {
         console.log("Dates Selected in Screen:", info);
          // Trigger create new appointment popup, passing selection start/end
          // Use info.startStr and info.endStr (ISO strings)
         this.createNewAppointment(info.startStr, info.endStr);
    }

     // Called when an event is moved (drag-and-drop) or resized
     async onEventDropOrResize(event, oldEvent, delta, revertFunc) {
         console.log("Event Moved/Resized in Screen:", event.id, event.startStr, event.endStr);
         const odooEventId = event.extendedProps?.odoo_id;
         if (!odooEventId) {
             console.error("Cannot update event: Missing Odoo ID.");
             if (typeof revertFunc === 'function') revertFunc(); // Revert visual change
             return;
         }

         // Prepare data for backend update (use ISO strings directly from FullCalendar event object)
         const valuesToUpdate = {
             // Use .toISOString() for reliability and UTC representation
             start: event.start.toISOString(),
             stop: event.end ? event.end.toISOString() : null, // Handle potential null end date
             // allday: event.allDay // Update if allday status changed
         };

         this.notification.add(_t("Saving changes..."), {type:'info', sticky: false, duration: 1500});
         console.log("Calling ORM Write:", 'calendar.event', [odooEventId], valuesToUpdate);

         try {
            // Call ORM Write to update backend
            await this.orm.write('calendar.event', [odooEventId], valuesToUpdate);
            this.notification.add(_t("Appointment updated successfully."), {type:'success', sticky: false, duration: 3000});
            // Refetch events to ensure calendar reflects backend state accurately,
            // including any potential overlaps or validation changes from backend.
            await this.fetchAppointments();

         } catch (error) {
            console.error("Error updating appointment:", error);
            this.notification.add(_t("Failed to save changes: %(message)s", { message: error.message || error }), { type: 'danger', sticky: true });
            // Revert the event visually in FullCalendar if the save fails
            if (typeof revertFunc === 'function') {
                revertFunc();
                 console.log("Reverted calendar event change visually.");
            } else {
                 // If revert function isn't available, refetch to reset view
                 this.notification.add(_t("Refetching appointments to revert change."), { type: 'warning'});
                 await this.fetchAppointments();
            }
         }
    }

    // Method to open the creation popup
    async createNewAppointment(start = null, end = null) {
        console.log("Triggering 'Create New Appointment' popup...", {start, end});

        const { confirmed, payload } = await this.pos.showPopup('AppointmentCreatePopup', {
            title: _t("Create New Appointment"),
            start: start, // Pass start string (ISO format from FullCalendar)
            end: end,     // Pass end string (ISO format from FullCalendar)
        });

        if (confirmed) {
            console.log("Appointment creation confirmed by popup:", payload);
            // Refresh the calendar view to show the new appointment
            await this.fetchAppointments();
        } else {
            console.log("Appointment creation cancelled.");
        }
    }

    // Helper method to format date/time for display (if needed beyond template)
    formatDisplayDateTime(dateTimeStr) {
         if (!dateTimeStr) return "";
         // Use Odoo's formatter, handles localization based on user settings
         try {
             // Add 'T' separator if missing for proper parsing by formatDateTime
             const formattedStr = dateTimeStr.includes('T') ? dateTimeStr : dateTimeStr.replace(' ', 'T');
             return formatDateTime(formattedStr);
         } catch (e) {
              console.warn(`Could not format date: ${dateTimeStr}`, e);
              return dateTimeStr; // Fallback
         }
    }
}

// Register the screen component with the POS registry
registry.category("pos_screens").add("AppointmentScreen", AppointmentScreen);