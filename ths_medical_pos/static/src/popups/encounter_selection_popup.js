/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class EncounterSelectionPopup extends Component {
    static template = "ths_medical_pos.EncounterSelectionPopup";
    static components = { Dialog };

    setup() {
        // Access the POS service using OWL 3 composables
        this.pos = useService("pos");
    }

    confirmSelection(encounter) {
        console.log("POS ENV", this.env); // Log full environment
        console.log("Encounter selected:", encounter); // Log the selected encounter object
        const partnerModel = this.pos.model?.get("res.partner");
        const partner = partnerModel?.get(encounter.partner_id) || null;

        console.log("Partner model:", partnerModel); // Log model access
        console.log("Resolved partner:", partner);   // Log partner record fetched

        this.props.resolve({
            confirmed: true,
            payload: {
                partner,
                encounter_id: encounter.id,
                encounter_name: encounter.name,
                patient_ids: encounter.patient_ids,
                practitioner_id: encounter.practitioner_id,
                room_id: encounter.room_id,
                pet_owner_id: encounter.pet_owner_id,
            },
        });
    }
}

registry.category("pos_popup").add("ths_medical_pos.EncounterSelectionPopup", EncounterSelectionPopup);

console.log("POS: Base EncounterSelectionPopup loaded");
