/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { EncounterSelectionPopup } from "@ths_medical_pos/components/encounter_selection_popup/encounter_selection_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerList.prototype, {
    async openEncounterSelectionPopup() {
        try {
            console.log("=== LOADING ENCOUNTERS DIRECTLY ===");

            // Load encounters directly with searchRead - much simpler!
            const encounters = await this.pos.data.searchRead(
                'ths.medical.base.encounter',
                [
                    ['partner_id', '!=', false],
                    ['state', 'in', ['draft', 'in_progress', 'done']]
                ],
                ['id', 'name', 'encounter_date', 'partner_id', 'patient_ids', 'practitioner_id', 'room_id', 'state'],
                {
                    order: 'encounter_date desc',
                    limit: 50
                }
            );

            console.log("Raw encounters from searchRead:", encounters);

            if (!encounters || encounters.length === 0) {
                this.notification.add(_t("No medical encounters found."), { type: 'info' });
                return;
            }

            // Format the data properly for display
            const formattedEncounters = await Promise.all(encounters.map(async (encounter) => {
                console.log(`Formatting encounter ${encounter.name}:`, encounter);

                // Get patient names if patient_ids are just IDs
                let patientNames = [];
                if (encounter.patient_ids && encounter.patient_ids.length > 0) {
                    // If patient_ids are just numbers, get names from res.partner
                    if (typeof encounter.patient_ids[0] === 'number') {
                        try {
                            const patients = await this.pos.data.searchRead(
                                'res.partner',
                                [['id', 'in', encounter.patient_ids]],
                                ['id', 'name']
                            );
                            patientNames = patients.map(p => [p.id, p.name]);
                        } catch (error) {
                            console.error("Error loading patient names:", error);
                            patientNames = encounter.patient_ids.map(id => [id, `Patient #${id}`]);
                        }
                    } else {
                        // Already in correct format
                        patientNames = encounter.patient_ids;
                    }
                }

                return {
                    ...encounter,
                    // Keep partner_id, practitioner_id, room_id AS-IS (they come correctly as [id, name])
                    // Only fix patient_ids
                    patient_ids: patientNames
                };
            }));

            console.log("Formatted encounters:", formattedEncounters);

            // Open encounter selection popup
            const result = await this.dialog.add(EncounterSelectionPopup, {
                title: _t("Select Medical Encounter"),
                encounters: formattedEncounters,
            });

            console.log("Result from encounter selection:", result);

            // Handle the result with simplified partner setting
            if (result.confirmed && result.payload && result.payload.partner) {
                const partner = result.payload.partner;

                console.log("Setting partner:", partner);

                // Method 1: Use the simple partner setting method the user mentioned
                this.pos.get_order().set_partner(partner);

                // Method 2: Also try the standard partner list method
                this.clickPartner(partner);

                // Success notification
                this.notification.add(_t("Partner selected from encounter: %s", partner.name), {
                    type: 'success',
                });

                // Add medical context to the order
                const order = this.pos.get_order();
                if (order) {
                    order.medical_context = {
                        encounter_id: result.payload.encounter_id,
                        encounter_name: result.payload.encounter_name,
                        patient_ids: result.payload.patient_ids,
                        practitioner_id: result.payload.practitioner_id,
                        room_id: result.payload.room_id,
                    };

                    console.log("Medical context added to order:", order.medical_context);
                }
            }

        } catch (error) {
            console.error("Error in openEncounterSelectionPopup:", error);
            this.notification.add(_t("Error: %s", error.message), { type: 'danger' });
        }
    },
});