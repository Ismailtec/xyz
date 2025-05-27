/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState, onWillStart } from "@odoo/owl"; // Ensure onWillStart is imported
import { useService } from "@web/core/utils/hooks";
import { formatDateTime } from "@web/core/l10n/dates";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup"; // Optional: For showing detailed errors

// Import logger if needed for detailed logging
// import { _logger } from "@web/core/utils/logger"; // Uncomment if _logger is used elsewhere and needed
import { session } from "@web/session"; // For user context if needed by ORM calls

const TICKET_SCREEN_CONFIRMATION_KEY = "reload_ticket_screen_confirmation";

export class AppointmentDetailPopup extends AbstractAwaitablePopup {
    static template = "ths_medical_pos.AppointmentDetailPopup";
    static defaultProps = {
        closePopup: () => {},
        cancelText: _t("Close"),
        title: _t("Appointment Details"),
        eventId: null, // Expect eventId to be passed
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        // No need to explicitly get 'action' service here, accessed via this.env.services.action

        this.state = useState({
            isLoading: true,
            eventData: null,
            isPaying: false, // Flag to prevent double click on Pay
        });

        // Fetch full event details when the popup is about to start
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
                'partner_id', // Owner
                'ths_patient_id', // Pet/Patient
                'ths_practitioner_id', // Provider
                'ths_room_id', // Room
                'ths_status',
                'ths_reason_for_visit',
                'appointment_type_id',
                'ths_is_walk_in',
                'allday', // Important for display/calendar logic
                // Add any other fields you want to display
            ];
            // Use orm.read which is efficient for fetching fields for known IDs
            const eventDataArr = await this.orm.read(
                'calendar.event', // Assuming 'calendar.event' is correct
                [eventId], // Expecting a single ID
                fieldsToRead,
                 { context: session.user_context } // Pass user context
            );

            if (eventDataArr && eventDataArr.length > 0) {
                this.state.eventData = eventDataArr[0];
                console.log("Fetched event details:", this.state.eventData);
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

    // Helper to format datetime strings
    formatDisplayDateTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
             // Add 'T' separator if missing for proper parsing by formatDateTime
             const formattedStr = dateTimeStr.includes('T') ? dateTimeStr : dateTimeStr.replace(' ', 'T');
             return formatDateTime(formattedStr);
         } catch (e) {
              console.warn(`Could not format date: ${dateTimeStr}`, e);
              return dateTimeStr; // Fallback
         }
    }

    // Helper to get CSS class for status badge (example)
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

    // --- Edit Action ---
    /**
     * Handles the click event for the 'Edit' button.
     * Opens the current appointment record in its form view in edit mode.
     */
    async onEditClick() {
        // Use the eventId passed in props, as it's the basis for this popup
        if (!this.props.eventId) {
            console.error("Appointment ID (props.eventId) is missing, cannot edit.");
            this.notification.add(_t("Cannot edit: Missing appointment ID."), {
                type: 'danger',
                sticky: false,
            });
            return;
        }

        const appointmentId = this.props.eventId;
        // Assuming the model is 'calendar.event'. Change if necessary.
        const modelName = 'calendar.event';

        try {
            // Close the current popup first
            await this.cancel(); // This closes the popup

            // Use the action service to open the record in edit mode in the main view
            await this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: modelName,
                res_id: appointmentId,
                views: [[false, 'form']], // Load the default form view
                target: 'current', // Open in the main content area, replacing the POS interface
                context: {
                    'form_view_initial_mode': 'edit', // Ensure it opens directly in edit mode
                    // 'create': false, // Optionally disable creation from this specific view context
                },
            });

        } catch (error) {
            console.error("Error trying to open appointment for editing:", error);
            this.notification.add(_t("Failed to open appointment for editing."), {
                type: 'danger',
                sticky: false,
            });
            // Note: The popup is already closed at this point by this.cancel()
        }
    }


    // --- Pay Action ---
    async onPayClick() {
        if (!this.state.eventData || !this.state.eventData.id) {
            this.notification.add(_t("Cannot proceed: Appointment data not loaded."), { type: 'danger' });
            return;
        }
        if (this.state.isPaying) return; // Prevent double click

        const order = this.pos.get_order();
        if (!order) {
            // If no order, create one? Or prompt? Let's prompt for now.
            this.notification.add(_t("No active order found. Create or select an order first."), { type: 'danger' });
            // Alternatively, create a new order:
            // this.pos.add_new_order();
            // order = this.pos.get_order();
            // if (!order) { ... error ... }
            return;
        }

        // Ensure the order's partner matches the appointment's owner, or set it
        const appointmentOwnerId = this.state.eventData.partner_id ? this.state.eventData.partner_id[0] : null;
        if (appointmentOwnerId) {
             const currentPartner = order.get_partner();
             if (!currentPartner || currentPartner.id !== appointmentOwnerId) {
                 const owner = this.pos.db.get_partner_by_id(appointmentOwnerId);
                 if (owner) {
                      order.set_partner(owner);
                      this.notification.add(_t("Customer set to '%(partnerName)s' based on appointment.", { partnerName: owner.name }), { type: 'info', duration: 2500 });
                 } else {
                      this.notification.add(_t("Could not find appointment owner (ID: %(ownerId)s) in POS partners. Please set customer manually.", { ownerId: appointmentOwnerId }), { type: 'warning', sticky: true });
                      // Don't proceed if owner cannot be set correctly? Or allow proceeding? Let's stop for safety.
                      return;
                 }
             }
        } else {
             this.notification.add(_t("Appointment has no linked owner. Please select a customer for the order."), { type: 'warning', sticky: true });
             // Stop if no owner linked to appointment?
             return;
        }


        this.state.isPaying = true;
        // _logger.info(`Pay action clicked for appointment ${this.props.eventId}`); // Uncomment if logger is set up

        try {
            // Find related Encounter ID (needed if pending items aren't directly linked to appointment)
            const appointmentId = this.state.eventData.id;

            // Fetch 'pending' items linked to this appointment's encounter(s)
             const fieldsToFetch = [
                'id', 'product_id', 'qty', 'price_unit', 'discount', 'description',
                'patient_id', 'practitioner_id', 'commission_pct', 'encounter_id' // Include encounter_id for logging/debugging
             ];
             const domain = [
                 // Link via encounter which is linked to appointment
                 ['encounter_id.appointment_id', '=', appointmentId],
                 ['state', '=', 'pending']
             ];

             const pendingItems = await this.orm.searchRead('ths.pending.pos.item', domain, fieldsToFetch, { context: session.user_context });

             if (!pendingItems || pendingItems.length === 0) {
                 this.notification.add(_t("No pending billable items found for this appointment."), { type: 'warning' });
                 this.state.isPaying = false;
                 // Consider not closing the popup if nothing found, or confirm explicitly?
                 // For now, let's still close as the action was "attempted".
                 this.confirm(); // Close popup
                 return;
             }

             // _logger.info(`Found ${pendingItems.length} pending items to add.`); // Uncomment if logger is set up

             let itemsAddedCount = 0;
             let errorsEncountered = false;

            // Add each pending item to the current POS order
            for (const item of pendingItems) {
                 const product = this.pos.db.get_product_by_id(item.product_id[0]);
                 if (!product) {
                    // _logger.error(`Product ID ${item.product_id[0]} from pending item ${item.id} not found in POS.`); // Uncomment if logger is set up
                    console.error(`Product ID ${item.product_id[0]} from pending item ${item.id} not found in POS.`);
                    this.notification.add(
                         _t("Product '%(productName)s' not available in POS. Skipping item.", { productName: item.product_id[1] }),
                         { type: 'danger' }
                    );
                    errorsEncountered = true;
                    continue; // Skip this item
                }

                const options = {
                    quantity: item.qty,
                    price: item.price_unit, // Use specific price
                    discount: item.discount || 0,
                    description: item.description || product.display_name, // Use specific description
                    extras: { // Pass necessary data to backend processing
                        ths_pending_item_id: item.id,
                        ths_patient_id: item.patient_id ? item.patient_id[0] : null,
                        ths_provider_id: item.practitioner_id ? item.practitioner_id[0] : null,
                        ths_commission_pct: item.commission_pct || 0,
                    },
                    merge: false // Prevent merging lines with same product but different provider/commission
                };

                try {
                     console.log(`Adding product ${product.id} to order with options:`, options);
                     await order.add_product(product, options);
                     itemsAddedCount++;
                } catch (error) {
                     console.error(`Error adding pending item ${item.id} (Product ${product.id}) to order:`, error);
                     this.notification.add(
                          _t("Failed to add item '%(productName)s'.", { productName: product.display_name }),
                          { type: 'danger' }
                     );
                     errorsEncountered = true;
                }
            } // End loop through items

            // Provide feedback and close
             if (itemsAddedCount > 0) {
                  this.notification.add(
                     _t("Added %(count)s item(s) to the order.", { count: itemsAddedCount }),
                     { type: errorsEncountered ? 'warning' : 'success', duration: 3000 }
                  );
             } else if (!errorsEncountered) {
                  // This case might not be reached due to the check above, but included for completeness
                  this.notification.add(_t("No new items were added to the order."), { type: 'info' });
             }

            // Close the popup, allowing user to review the order before payment
            this.confirm(); // Close popup

        } catch (error) {
            console.error("Error during Pay action:", error);
            this.notification.add(_t("An error occurred while adding items to the order."), { type: 'danger' });
            // Popup might still need closing in case of error before confirm() is reached
            // However, closing here might hide context. Let's rely on finally.
        } finally {
            this.state.isPaying = false; // Re-enable button
        }
    }


    cancel() {
        super.cancel(); // Closes the popup
    }
}

// Register the popup component
odoo.define_registry.category("pos_popups").add("AppointmentDetailPopup", AppointmentDetailPopup); // Use define_registry for Odoo 18+