/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

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
        this.orm = useService("orm");
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

    async loadInitialData() {
        try {
            // Load owner's pets
            if (this.props.partner) {
                const pets = await this.orm.searchRead(
                    'res.partner',
                    [
                        ('ths_pet_owner_id', '=', this.props.partner.id),
                        ('ths_partner_type_id.name', '=', 'Pet')
                    ],
                    ['id', 'name', 'ths_species_id']
                );
                this.state.ownerPets = pets;
            }

            // Load practitioners and rooms
            const [practitioners, rooms] = await Promise.all([
                this.orm.searchRead(
                    'appointment.resource',
                    [('ths_resource_category', '=', 'practitioner')],
                    ['id', 'name']
                ),
                this.orm.searchRead(
                    'appointment.resource',
                    [('ths_resource_category', '=', 'location')],
                    ['id', 'name']
                )
            ]);

            this.state.practitioners = practitioners;
            this.state.rooms = rooms;

            // Pre-fill from encounter if provided
            if (this.props.encounter) {
                this.state.selectedPets = this.props.encounter.patient_ids || [];
                this.state.selectedPractitioner = this.props.encounter.practitioner_id?.[0] || null;
                this.state.selectedRoom = this.props.encounter.room_id?.[0] || null;
            }

        } catch (error) {
            console.error("Error loading pet selection data:", error);
            this.notification.add(_t("Error loading selection data"), { type: 'danger' });
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

    async confirm() {
        const result = {
            confirmed: true,
            payload: {
                patient_ids: this.state.selectedPets,
                practitioner_id: this.state.selectedPractitioner,
                room_id: this.state.selectedRoom,
            }
        };

        this.props.close(result);
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}