/** @odoo-module **/

import { AppointmentBookingGanttRenderer } from "@appointment/views/gantt/gantt_renderer";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(AppointmentBookingGanttRenderer.prototype, {

    /**
     * @override
     */
    setup() {
        super.setup();
    },

    getPopoverButtons(record) {
        var buttons = super.getPopoverButtons(record);
        return [buttons[0],
                {
                    class: "o_appointment_booking_confirm_status btn btn-sm btn-primary",
                    onClick: () => {
                        if (this.model.metaData.canEdit && record.appointment_status) {
                            const newAppointmentStatus = document.querySelector('.o_appointment_booking_status').selectedOptions[0].value;
                            this.orm.write("calendar.event", [record.id], {
                                active: newAppointmentStatus !== 'cancelled',
                                appointment_status: 'invoice',
                            }).then(() => this.model.fetchData());
                        }
                    },
                    text: _t('Invoice'),
                },
                buttons[1]
        ]
    }
});