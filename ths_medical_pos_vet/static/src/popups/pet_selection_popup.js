/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class PetSelectionPopup extends Component {
    static template = "ths_medical_pos_vet.PetSelectionPopup";
    static components = { Dialog };

    static props = {
        title: String,
        partner: Object,
        encounter: { type: Object, optional: true },
        close: Function,
    };

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");

        this.state = useState({
            selectedPets: [],
            selectedPractitioner: null,
            selectedRoom: null,
            practitioners: [],
            rooms: [],
            ownerPets: [],
        });

        this.loadInitialData();
    }

    loadInitialData() {
        const allPartners = this.pos.models["res.partner"].getAll();
        const allResources = this.pos.models["appointment.resource"].getAll();

        if (this.props.partner) {
            this.state.ownerPets = allPartners.filter(p =>
                p.ths_pet_owner_id?.[0] === this.props.partner.id &&
                p.ths_partner_type_id?.[1] === "Pet"
            );
        }

        this.state.practitioners = allResources.filter(r => r.ths_resource_category === "practitioner");
        this.state.rooms = allResources.filter(r => r.ths_resource_category === "location");

        if (this.props.encounter) {
            this.state.selectedPets = this.props.encounter.patient_ids || [];
            this.state.selectedPractitioner = this.props.encounter.practitioner_id?.[0] || null;
            this.state.selectedRoom = this.props.encounter.room_id?.[0] || null;
        }
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

    confirm() {
        this.props.close({
            confirmed: true,
            payload: {
                patient_ids: this.state.selectedPets,
                practitioner_id: this.state.selectedPractitioner,
                room_id: this.state.selectedRoom,
            }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}
