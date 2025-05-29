/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/popups/appointment_detail_popup.js");

import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatDateTime } from "@web/core/l10n/dates";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class AppointmentDetailPopup extends Component {
    static template = "ths_medical_pos.AppointmentDetailPopup";
    static props = {
        title: { type: String, optional: true },
        eventId: { type: Number, optional: true },
        close: Function,
    };
    static defaultProps = {
        title: _t("Appointment Details"),
        eventId: null,
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            isLoading: true,
            eventData: null,
            isPaying: false,
        });

        onWillStart(async () => {
            if (this.props.eventId) {
                await this.loadEventDetails(this.props.eventId);
            } else {
                console.error("AppointmentDetailPopup: No eventId provided.");
                this.state.isLoading = false;
                this.notification.add(_t("Cannot load details: Missing appointment ID."), { type: 'danger' });
            }
        });
    }

    async loadEventDetails(eventId) {
        this.state.isLoading = true;
        try {
            const fieldsToRead = [
                'id', 'display_name', 'start', 'stop', 'duration',
                'partner_id',
                'ths_patient_id',
                'ths_practitioner_id',
                'ths_room_id',
                'ths_status',
                'ths_reason_for_visit',
                'appointment_type_id',
                'ths_is_walk_in',
                'allday',
            ];

            const eventDataArr = await this.orm.read(
                'calendar.event',
                [eventId],
                fieldsToRead,
                { context: this.pos.user.context }
            );

            if (eventDataArr && eventDataArr.length > 0) {
                this.state.eventData = eventDataArr[0];
            } else {
                console.error(`Event with ID ${eventId} not found.`);
                this.notification.add(_t("Appointment not found."), { type: 'danger' });
                this.state.eventData = null;
            }
        } catch (error) {
            console.error("Error loading appointment details:", error);
            this.notification.add(_t("Error loading appointment details."), { type: 'danger' });
            this.state.eventData = null;
        } finally {
            this.state.isLoading = false;
        }
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

    getStatusClass(status) {
        switch (status) {
            case 'scheduled': return 'bg-info text-dark';
            case 'confirmed': return 'bg-success';
            case 'checked_in': return 'bg-warning text-dark';
            case 'in_progress': return 'bg-danger';
            case 'completed': return 'bg-secondary';
            case 'billed': return 'bg-dark';
            case 'cancelled_by_patient':
            case 'cancelled_by_clinic':
            case 'no_show': return 'bg-light text-dark';
            default: return 'bg-secondary';
        }
    }

    async onEditClick() {
        if (!this.props.eventId) {
            console.error("Appointment ID is missing, cannot edit.");
            this.notification.add(_t("Cannot edit: Missing appointment ID."), {
                type: 'danger',
                sticky: false,
            });
            return;
        }

        const appointmentId = this.props.eventId;
        const modelName = 'calendar.event';

        try {
            this.props.close();

            await this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: modelName,
                res_id: appointmentId,
                views: [[false, 'form']],
                target: 'current',
                context: {
                    'form_view_initial_mode': 'edit',
                },
            });

        } catch (error) {
            console.error("Error trying to open appointment for editing:", error);
            this.notification.add(_t("Failed to open appointment for editing."), {
                type: 'danger',
                sticky: false,
            });
        }
    }

    async onPayClick() {
        if (!this.state.eventData || !this.state.eventData.id) {
            this.notification.add(_t("Cannot proceed: Appointment data not loaded."), { type: 'danger' });
            return;
        }
        if (this.state.isPaying) return;

        const order = this.pos.get_order();
        if (!order) {
            this.notification.add(_t("No active order found. Create or select an order first."), { type: 'danger' });
            return;
        }

        const appointmentOwnerId = this.state.eventData.partner_id ? this.state.eventData.partner_id[0] : null;
        if (appointmentOwnerId) {
            const currentPartner = order.get_partner();
            if (!currentPartner || currentPartner.id !== appointmentOwnerId) {
                const owner = this.pos.db.partner_by_id[appointmentOwnerId];
                if (owner) {
                    order.set_partner(owner);
                    this.notification.add(_t("Customer set to '%(partnerName)s' based on appointment.", { partnerName: owner.name }), { type: 'info', duration: 2500 });
                } else {
                    this.notification.add(_t("Could not find appointment owner (ID: %(ownerId)s) in POS partners. Please set customer manually.", { ownerId: appointmentOwnerId }), { type: 'warning', sticky: true });
                    return;
                }
            }
        } else {
            this.notification.add(_t("Appointment has no linked owner. Please select a customer for the order."), { type: 'warning', sticky: true });
            return;
        }

        this.state.isPaying = true;

        try {
            const appointmentId = this.state.eventData.id;

            const fieldsToFetch = [
                'id', 'product_id', 'qty', 'price_unit', 'discount', 'description',
                'patient_id', 'practitioner_id', 'commission_pct', 'encounter_id'
            ];
            const domain = [
                ['encounter_id.appointment_id', '=', appointmentId],
                ['state', '=', 'pending']
            ];

            const pendingItems = await this.orm.searchRead('ths.pending.pos.item', domain, fieldsToFetch, { context: this.pos.user.context });

            if (!pendingItems || pendingItems.length === 0) {
                this.notification.add(_t("No pending billable items found for this appointment."), { type: 'warning' });
                this.state.isPaying = false;
                this.props.close();
                return;
            }

            let itemsAddedCount = 0;
            let errorsEncountered = false;

            for (const item of pendingItems) {
                const product = this.pos.db.product_by_id[item.product_id[0]];
                if (!product) {
                    console.error(`Product ID ${item.product_id[0]} from pending item ${item.id} not found in POS.`);
                    this.notification.add(
                        _t("Product '%(productName)s' not available in POS. Skipping item.", { productName: item.product_id[1] }),
                        { type: 'danger' }
                    );
                    errorsEncountered = true;
                    continue;
                }

                const options = {
                    quantity: item.qty,
                    price: item.price_unit,
                    discount: item.discount || 0,
                    description: item.description || product.display_name,
                    extras: {
                        ths_pending_item_id: item.id,
                        ths_patient_id: item.patient_id ? item.patient_id[0] : null,
                        ths_provider_id: item.practitioner_id ? item.practitioner_id[0] : null,
                        ths_commission_pct: item.commission_pct || 0,
                    },
                    merge: false
                };

                try {
                    order.add_product(product, options);
                    itemsAddedCount++;
                } catch (error) {
                    console.error(`Error adding pending item ${item.id} to order:`, error);
                    this.notification.add(
                        _t("Failed to add item '%(productName)s'.", { productName: product.display_name }),
                        { type: 'danger' }
                    );
                    errorsEncountered = true;
                }
            }

            if (itemsAddedCount > 0) {
                this.notification.add(
                    _t("Added %(count)s item(s) to the order.", { count: itemsAddedCount }),
                    { type: errorsEncountered ? 'warning' : 'success', duration: 3000 }
                );
            } else if (!errorsEncountered) {
                this.notification.add(_t("No new items were added to the order."), { type: 'info' });
            }

            this.props.close();

        } catch (error) {
            console.error("Error during Pay action:", error);
            this.notification.add(_t("An error occurred while adding items to the order."), { type: 'danger' });
        } finally {
            this.state.isPaying = false;
        }
    }

    cancel() {
        this.props.close();
    }
}

// Register the popup component
registry.category("popups").add("AppointmentDetailPopup", AppointmentDetailPopup);