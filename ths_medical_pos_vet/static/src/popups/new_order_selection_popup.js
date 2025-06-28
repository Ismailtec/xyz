/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * New Order Selection Popup for Veterinary Practice
 * Shows when a pet owner is selected for a new order
 * Allows selection of pets, practitioner, and room
 */
export class NewOrderSelectionPopup extends Component {
    static template = "ths_medical_pos_vet.NewOrderSelectionPopup";
    static props = {
        title: String,
        partner_id: Number,
        partner_name: String,
        existing_encounter: { type: [Number, { value: false }], optional: true },
        pets: Array,
        practitioners: Array,
        rooms: Array,
        selected_pets: { type: Array, optional: true },
        selected_practitioner: { type: [Number, { value: false }], optional: true },
        selected_room: { type: [Number, { value: false }], optional: true },
        close: Function,
    };
    static components = { Dialog };

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            selectedPets: this.props.selected_pets || [],
            selectedPractitioner: this.props.selected_practitioner || false,
            selectedRoom: this.props.selected_room || false,
            isLoading: false,
        });

        console.log("NewOrderSelectionPopup setup with props:", this.props);
    }

    /**
     * Get pets display with species information
     */
    getPetDisplayName(pet) {
        let displayName = pet.name;
        if (pet.ths_species_id && Array.isArray(pet.ths_species_id) && pet.ths_species_id.length > 1) {
            displayName += ` (${pet.ths_species_id[1]})`;
        }
        return displayName;
    }

    /**
     * Toggle pet selection
     */
    togglePetSelection(petId) {
        const index = this.state.selectedPets.indexOf(petId);
        if (index > -1) {
            this.state.selectedPets.splice(index, 1);
        } else {
            this.state.selectedPets.push(petId);
        }
    }

    /**
     * Check if pet is selected
     */
    isPetSelected(petId) {
        return this.state.selectedPets.includes(petId);
    }

    /**
     * Set selected practitioner
     */
    selectPractitioner(practitionerId) {
        this.state.selectedPractitioner = practitionerId;
    }

    /**
     * Set selected room
     */
    selectRoom(roomId) {
        this.state.selectedRoom = roomId;
    }

    /**
     * Confirm selection and create/update encounter
     */
    async confirm() {
        if (this.state.isLoading) return;

        this.state.isLoading = true;

        try {
            console.log("Confirming selection with data:", {
                partner_id: this.props.partner_id,
                selected_pets: this.state.selectedPets,
                selected_practitioner: this.state.selectedPractitioner,
                selected_room: this.state.selectedRoom,
            });

            // Call backend method to process the popup result
            const encounter = await this.orm.call(
                'pos.order',
                '_process_new_order_popup_result',
                [{
                    partner_id: this.props.partner_id,
                    selected_pets: this.state.selectedPets,
                    selected_practitioner: this.state.selectedPractitioner,
                    selected_room: this.state.selectedRoom,
                }]
            );

            if (encounter) {
                console.log("Encounter created/updated:", encounter);

                // Get current order and set medical context
                const currentOrder = this.pos.get_order();
                if (currentOrder) {
                    currentOrder.encounter_id = encounter.id;
                    currentOrder.encounter_name = encounter.name;

                    // Set the order fields from encounter
                    currentOrder.patient_ids = this.state.selectedPets;
                    currentOrder.practitioner_id = this.state.selectedPractitioner;
                    currentOrder.room_id = this.state.selectedRoom;

                    console.log("Medical context set on order:", {
                        encounter_id: encounter.id,
                        patient_ids: this.state.selectedPets,
                        practitioner_id: this.state.selectedPractitioner,
                        room_id: this.state.selectedRoom,
                    });
                }

                this.notification.add(
                    _t("Medical context set successfully for %s", this.props.partner_name),
                    { type: 'success' }
                );

                // Close popup with success
                this.props.close({
                    confirmed: true,
                    encounter_id: encounter.id,
                    encounter_name: encounter.name,
                    selected_pets: this.state.selectedPets,
                    selected_practitioner: this.state.selectedPractitioner,
                    selected_room: this.state.selectedRoom,
                });
            } else {
                throw new Error("Failed to create/update encounter");
            }

        } catch (error) {
            console.error("Error processing new order popup:", error);
            this.notification.add(
                _t("Failed to process order setup: %s", error.message),
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Cancel and close popup
     */
    cancel() {
        this.props.close({ confirmed: false });
    }

    /**
     * Skip encounter setup and proceed with basic order
     */
    skip() {
        // Just proceed without setting encounter context
        this.props.close({
            confirmed: true,
            skipped: true
        });
    }
}