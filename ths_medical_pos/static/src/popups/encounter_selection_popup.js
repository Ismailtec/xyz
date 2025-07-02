/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Dialog} from "@web/core/dialog/dialog";
import {Component} from "@odoo/owl";
import {usePos} from "@point_of_sale/app/store/pos_hook";

export class EncounterSelectionPopup extends Component {
    static template = "ths_medical_pos.EncounterSelectionPopup";
    static components = {Dialog};

    setup() {
        // Access the POS service using OWL 3 composable
        this.pos = usePos();
    }

    confirmSelection(encounter) {
        console.log("Encounter selected:", encounter);
        const partner = this.pos.models["res.partner"]?.get(encounter.partner_id[0]) || null;

        console.log("Resolved partner:", partner);

        this.props.resolve({
            confirmed: true,
            payload: {
                partner,
                encounter_id: encounter.id,
                encounter_name: encounter.name,
                patient_ids: encounter.patient_ids,
                practitioner_id: encounter.practitioner_id,
                room_id: encounter.room_id,
            },
        });
    }
}

registry.category("pos_popup").add("ths_medical_pos.EncounterSelectionPopup", EncounterSelectionPopup);

console.log("POS: Base EncounterSelectionPopup loaded");
