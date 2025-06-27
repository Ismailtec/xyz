/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class EncounterSelectionPopup extends Component {
    static template = "ths_medical_pos.EncounterSelectionPopup";
    static props = {
        title: String,
        encounters: Array,
        close: Function,
        // Add callback function to handle partner selection in parent
        onPartnerSelected: { type: Function, optional: true },
    };
    static components = { Dialog };

    setup() {
        this.dialog = useService("dialog");
        this.cancelLabel = _t("Cancel");
        this.notification = useService("notification");
        this.pos = usePos(); // Correct Odoo 18 POS hook usage

        // Debug: Log the encounters data structure
        console.log("EncounterSelectionPopup - Encounters received:", this.props.encounters);
        if (this.props.encounters.length > 0) {
            console.log("Sample encounter structure:", this.props.encounters[0]);

            // Debug each encounter's structure
            this.props.encounters.forEach((encounter, index) => {
                console.log(`Encounter ${index + 1} (${encounter.name}):`);
                console.log(`  ID: ${encounter.id}`);
                console.log(`  partner_id:`, encounter.partner_id);
                console.log(`  patient_ids:`, encounter.patient_ids);
                console.log(`  practitioner_id:`, encounter.practitioner_id);
                console.log(`  room_id:`, encounter.room_id);
                console.log(`  state:`, encounter.state);
            });
        }
    }

    confirmSelection = (encounter) => {
        console.log("confirmSelection called with encounter:", encounter);

        // Handle partner_id - should now come properly formatted
        if (!encounter.partner_id || !Array.isArray(encounter.partner_id) || encounter.partner_id.length < 2) {
            console.warn("Invalid partner data:", encounter.partner_id);
            this.notification.add(_t("No partner found for this encounter."), { type: 'warning' });
            return;
        }

        const partnerId = encounter.partner_id[0];
        const partnerName = encounter.partner_id[1];
        console.log("Extracted partner ID:", partnerId, "Name:", partnerName);

        // Get partner from POS models using correct Odoo 18 API
        const partner = this.pos.models["res.partner"].get(partnerId);
        console.log("Partner found in POS models:", partner);

        if (!partner) {
            this.notification.add(_t("Partner not found in POS cache: %s", partnerName), {
                type: 'danger'
            });
            return;
        }

        // Success notification
        this.notification.add(_t("Selected encounter: %s for partner: %s", encounter.name, partner.name), {
            type: 'success',
        });

        // Close this popup and send partner data back to parent
        this.props.close({
            confirmed: true,
            payload: {
                encounter_id: encounter.id,
                encounter_name: encounter.name,
                partner: partner,  // Pass the actual partner object
                patient_ids: encounter.patient_ids,
                practitioner_id: encounter.practitioner_id,
                room_id: encounter.room_id,
            },
        });
    };

    cancel() {
        this.props.close({ confirmed: false });
    }
}