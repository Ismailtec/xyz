// File: ths_medical_pos_vet/static/src/popups/encounter_selection_popup.js

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { EncounterSelectionPopup } from "@ths_medical_pos/popups/encounter_selection_popup"; // Base class
import { patch } from "@web/core/utils/patch";

patch(EncounterSelectionPopup.prototype, {
    setup() {
        super.setup();

        this.membershipByPetId = {};
        for (const m of this.pos.vet_pet_memberships || []) {
            this.membershipByPetId[m.pet_id] = m.membership_status;
        }

        this.speciesById = {};
        for (const s of this.pos.ths_species || []) {
            this.speciesById[s.id] = s.name;
        }
    },

    getEnhancedPatientName(patientId) {
        const partner = this.pos.db.get_partner_by_id(patientId);
        if (!partner) return "";

        const species = this.speciesById[partner.species_id] || "Unknown";
        const name = partner.name || "Unnamed";

        const membership = this.membershipByPetId[partner.id];
        const badge = membership === "active" ? "🌟" : membership === "expired" ? "⚠️" : "";

        return `${name} (${species}) ${badge}`;
    },

    get formattedEncounters() {
        return (this.props.encounters || []).map(encounter => {
            const formatted = { ...encounter };
            if (Array.isArray(formatted.patient_ids)) {
                formatted.patient_ids = formatted.patient_ids
                    .map(pid => this.getEnhancedPatientName(pid))
                    .filter(Boolean);
            }
            return formatted;
        });
    },
});

// Register if used as a standalone popup (optional)
//registry.category("pos_popups").add("EncounterSelectionPopupVet", EncounterSelectionPopup);
