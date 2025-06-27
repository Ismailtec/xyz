/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { EncounterSelectionPopup } from "@ths_medical_pos/components/encounter_selection_popup/encounter_selection_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerList.prototype, {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.pos = usePos();

        // Load partner types if they're missing
        this.ensurePartnerTypesLoaded();
    },

    async ensurePartnerTypesLoaded() {
        // Check if partner types are loaded
        if (!this.pos.models["ths.partner.type"] || this.pos.models["ths.partner.type"].getAll().length === 0) {
            console.log("Partner types not loaded via models, trying fallback...");
            try {
                const partnerTypes = await this.pos.data.call(
                    'pos.session',
                    'get_partner_types_for_pos',
                    [this.pos.session.id]
                );

                console.log("Loaded partner types via fallback:", partnerTypes);

                // Apply partner types to partners manually
                if (partnerTypes.length > 0) {
                    const typeMap = {};
                    partnerTypes.forEach(type => {
                        typeMap[type.id] = type.name;
                    });

                    const partners = this.pos.models["res.partner"].getAll();
                    partners.forEach(partner => {
                        if (partner.raw && partner.raw.ths_partner_type_id && !Array.isArray(partner.ths_partner_type_id)) {
                            const typeId = partner.raw.ths_partner_type_id;
                            const typeName = typeMap[typeId];
                            if (typeName) {
                                partner.ths_partner_type_id = [typeId, typeName];
                                console.log(`Applied partner type ${typeName} to ${partner.name}`);
                            }
                        }
                    });
                }
            } catch (error) {
                console.error("Error loading partner types via fallback:", error);
            }
        }
    },

    async openEncounterSelectionPopup() {
        try {
            let encounters = [];

            // Try to get encounters from loaded models first
            const encounterModel = this.pos.models["ths.medical.base.encounter"];

            if (encounterModel && encounterModel.getAll().length > 0) {
                encounters = encounterModel.getAll();
                console.log("Got encounters from loaded models:", encounters.length);
            } else {
                // Fallback: get encounters via RPC call
                console.log("Encounter model not loaded, trying fallback...");

                try {
                    encounters = await this.pos.data.call(
                        'pos.session',
                        'get_encounters_for_pos',
                        [this.pos.session.id]
                    );
                    console.log("Got encounters via fallback:", encounters.length);
                } catch (rpcError) {
                    console.error("Fallback encounter loading failed:", rpcError);
                    this.notification.add(_t("Unable to load encounters. Please check your medical POS configuration."), {
                        type: 'warning'
                    });
                    return;
                }
            }

            if (!encounters || encounters.length === 0) {
                this.notification.add(_t("No medical encounters found."), { type: 'info' });
                return;
            }

            // Open encounter selection popup
            const result = await this.dialog.add(EncounterSelectionPopup, {
                title: _t("Select Medical Encounter"),
                encounters: encounters,
            });

            console.log("Result from encounter selection:", result);

            // Handle the result
            if (result.confirmed && result.payload && result.payload.partner) {
                const partner = result.payload.partner;

                // Use the parent component's clickPartner method
                this.clickPartner(partner);

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

                this.notification.add(_t("Partner selected from encounter: %s", partner.name), {
                    type: 'success',
                });
            }

        } catch (error) {
            console.error("Error in openEncounterSelectionPopup:", error);
            this.notification.add(_t("Error: %s", error.message), { type: 'danger' });
        }
    },
});