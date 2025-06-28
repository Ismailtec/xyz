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
        onPartnerSelected: { type: Function, optional: true },
    };
    static components = { Dialog };

    setup() {
        this.dialog = useService("dialog");
        this.cancelLabel = _t("Cancel");
        this.notification = useService("notification");
        this.pos = usePos();

        // CRITICAL FIX: Clean encounter data to prevent duplicate keys
        this.cleanedEncounters = this.cleanEncounterData(this.props.encounters);

        console.log("EncounterSelectionPopup - Cleaned encounters:", this.cleanedEncounters);
    }

    cleanEncounterData(encounters) {
        return encounters.map((encounter, encounterIndex) => {
            // Create a clean copy of the encounter
            const cleanEncounter = { ...encounter };

            // CRITICAL FIX: Ensure patient_ids have unique keys and no undefined values
            if (cleanEncounter.patient_ids && Array.isArray(cleanEncounter.patient_ids)) {
                const uniquePatients = [];
                const seenIds = new Set();

                cleanEncounter.patient_ids.forEach((patient, index) => {
                    let patientId, patientName;

                    if (Array.isArray(patient) && patient.length >= 2) {
                        patientId = patient[0];
                        patientName = patient[1];
                    } else if (typeof patient === 'number') {
                        patientId = patient;
                        patientName = `Patient #${patient}`;
                    } else {
                        // Fallback for undefined/null patients
                        patientId = `fallback_${encounterIndex}_${index}`;
                        patientName = 'Unknown Patient';
                    }

                    // Ensure unique patient ID
                    if (!seenIds.has(patientId)) {
                        seenIds.add(patientId);
                        uniquePatients.push([patientId, patientName]);
                    }
                });

                cleanEncounter.patient_ids = uniquePatients;
            } else {
                cleanEncounter.patient_ids = [];
            }

            // Ensure all other fields are properly formatted
            if (!cleanEncounter.partner_id || !Array.isArray(cleanEncounter.partner_id)) {
                cleanEncounter.partner_id = [0, 'No Partner'];
            }

            if (!cleanEncounter.practitioner_id || !Array.isArray(cleanEncounter.practitioner_id)) {
                cleanEncounter.practitioner_id = null;
            }

            if (!cleanEncounter.room_id || !Array.isArray(cleanEncounter.room_id)) {
                cleanEncounter.room_id = null;
            }

            return cleanEncounter;
        });
    }

    confirmSelection = (encounter) => {
        console.log("confirmSelection called with encounter:", encounter);

        // Validate partner data
        if (!encounter.partner_id || !Array.isArray(encounter.partner_id) || encounter.partner_id.length < 2) {
            console.warn("Invalid partner data:", encounter.partner_id);
            this.notification.add(_t("No partner found for this encounter."), { type: 'warning' });
            return;
        }

        const partnerId = encounter.partner_id[0];
        const partnerName = encounter.partner_id[1];
        console.log("Extracted partner ID:", partnerId, "Name:", partnerName);

        // Get partner from POS models
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

        // Close popup with partner data
        this.props.close({
            confirmed: true,
            payload: {
                encounter_id: encounter.id,
                encounter_name: encounter.name,
                partner: partner,
                patient_ids: encounter.patient_ids,
                practitioner_id: encounter.practitioner_id,
                room_id: encounter.room_id,
            },
        });
    };

    cancel() {
        this.props.close({ confirmed: false });
    }

    // Getter for template to access cleaned encounters
    get encounters() {
        return this.cleanedEncounters;
    }
}