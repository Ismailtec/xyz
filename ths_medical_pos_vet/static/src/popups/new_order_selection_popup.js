/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";

export class NewOrderSelectionPopup extends Component {
    static template = "ths_medical_pos_vet.NewOrderSelectionPopup";
    static components = { Dialog };

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

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");

        this.state = useState({
            selectedPets: this.props.selected_pets || [],
            selectedPractitioner: this.props.selected_practitioner || false,
            selectedRoom: this.props.selected_room || false,
        });
    }

    getPetDisplayName(pet) {
        let displayName = pet.name;
        if (pet.ths_species_id && Array.isArray(pet.ths_species_id) && pet.ths_species_id.length > 1) {
            displayName += ` (${pet.ths_species_id[1]})`;
        }
        return displayName;
    }

    togglePetSelection(petId) {
        const index = this.state.selectedPets.indexOf(petId);
        if (index > -1) {
            this.state.selectedPets.splice(index, 1);
        } else {
            this.state.selectedPets.push(petId);
        }
    }

    isPetSelected(petId) {
        return this.state.selectedPets.includes(petId);
    }

    selectPractitioner(practitionerId) {
        this.state.selectedPractitioner = practitionerId;
    }

    selectRoom(roomId) {
        this.state.selectedRoom = roomId;
    }

    confirm() {
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            currentOrder.encounter_id = this.props.existing_encounter || null;
            currentOrder.patient_ids = this.state.selectedPets;
            currentOrder.practitioner_id = this.state.selectedPractitioner;
            currentOrder.room_id = this.state.selectedRoom;
        }

        this.notification.add(
            _t("Medical context set successfully for %s", this.props.partner_name),
            { type: 'success' }
        );

        this.props.close({
            confirmed: true,
            encounter_id: this.props.existing_encounter || null,
            selected_pets: this.state.selectedPets,
            selected_practitioner: this.state.selectedPractitioner,
            selected_room: this.state.selectedRoom,
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }

    skip() {
        this.props.close({ confirmed: true, skipped: true });
    }
}
