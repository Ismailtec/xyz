/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AppointmentBookingGanttRenderer } from "@appointment/views/gantt/gantt_renderer";

/**
 * Medical extension of the Appointment Booking Gantt Renderer
 * Extends status handling for medical appointment statuses
 */
patch(AppointmentBookingGanttRenderer.prototype, {
    /**
     * @override
     * Extended to handle medical appointment statuses with proper colors
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        const { record } = pill;

        if (!record.appointment_type_id) {
            return enrichedPill;
        }

        const now = luxon.DateTime.now();
        let color = false;

        // Handle unified appointment_status (including medical statuses)
        if (!record.active) {
            color = false; // Archived
        } else {
            switch (record.appointment_status) {
                case 'scheduled':
                case 'confirmed':
                    color = now.diff(record.start, ['minutes']).minutes > 15 ? 2 : 4; // orange if late, light blue if not
                    break;
                case 'checked_in':
                    color = 6; // yellow - patient is here
                    break;
                case 'in_progress':
                    color = 9; // dark blue - consultation ongoing
                    break;
                case 'completed':
                    color = 8; // light green - completed but not billed
                    break;
                case 'billed':
                    color = 10; // green - fully processed
                    break;
                case 'booked':
                    color = now.diff(record.start, ['minutes']).minutes > 15 ? 2 : 4; // orange if late, light blue if not
                    break;
                case 'attended':
                    color = 10; // green - legacy status
                    break;
                case 'cancelled_by_patient':
                case 'cancelled_by_clinic':
                    color = 1; // red - cancelled
                    break;
                case 'no_show':
                    color = 1; // red - no show
                    break;
                case 'request':
                    color = record.start < now ? 2 : 8; // orange if past, blue if future
                    break;
                default:
                    color = 8; // default blue
            }
        }

        if (color) {
            enrichedPill.className += ` o_gantt_color_${color}`;
        }

        return enrichedPill;
    },

    /**
     * @override
     * Extended to handle medical field context in popover
     */
    async getPopoverProps(pill) {
        const popoverProps = await super.getPopoverProps(pill);
        const { record } = pill;

        // Add medical-specific context for popover template
        Object.assign(popoverProps.context, {
            // Medical fields for popover display
            ths_practitioner_name: record.ths_practitioner_id ? record.ths_practitioner_id[1] : '',
            ths_room_name: record.ths_room_id ? record.ths_room_id[1] : '',
            ths_patient_name: record.ths_patient_id ? record.ths_patient_id[1] : '',
            // Status information
            medical_appointment: !!record.appointment_type_id,
            appointment_status_display: this._getStatusDisplayText(record.appointment_status),
        });

        return popoverProps;
    },

    /**
     * Get display text for appointment status
     */
    _getStatusDisplayText(status) {
        const statusMap = {
            'request': 'Request',
            'booked': 'Booked',
            'scheduled': 'Scheduled',
            'confirmed': 'Confirmed',
            'checked_in': 'Checked In',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'billed': 'Billed',
            'attended': 'Checked-In', // Legacy
            'cancelled_by_patient': 'Cancelled (Patient)',
            'cancelled_by_clinic': 'Cancelled (Clinic)',
            'no_show': 'No Show'
        };
        return statusMap[status] || status;
    },

    /**
     * @override
     * Extended popover buttons for medical appointments
     */
    getPopoverButtons(record) {
        const buttons = super.getPopoverButtons(record);

        // Update the save button text based on medical context
        if (record.appointment_type_id && this.model.metaData.canEdit && record.appointment_status) {
            buttons[0].text = "Save Status & Close";
        }

        return buttons;
    }
});