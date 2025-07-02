/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {PartnerList} from "@point_of_sale/app/screens/partner_list/partner_list";
import {EncounterSelectionPopup} from "@ths_medical_pos/popups/encounter_selection_popup";
import {_t} from "@web/core/l10n/translation";

patch(PartnerList.prototype, {

    getPartners() {
        const allPartners = super.getPartners();
        const types = this.pos.models["ths.partner.type"]?.getAll() || [];

        return allPartners.filter(partner => {
            // Defensive check: if ths_partner_type_id doesn't exist, skip this partner
            if (!partner.hasOwnProperty('ths_partner_type_id') || !partner.ths_partner_type_id) {
                return false;
            }

            const typeId = Array.isArray(partner.ths_partner_type_id) ?
                partner.ths_partner_type_id[0] :
                partner.ths_partner_type_id;

            const type = types.find(t => t.id === typeId);

            // Defensive check: if type doesn't exist or doesn't have is_customer field, return false
            if (!type || !type.hasOwnProperty('is_customer')) {
                return false;
            }

            return type.is_customer === true;
        });
    },

    async clickPartner(partner) {
        return await super.clickPartner(partner);
    },

    async openEncounterSelectionPopup() {
        try {
            const encounters = this.pos.models["ths.medical.base.encounter"]?.getAll() || [];

            if (!encounters.length) {
                this.notification.add(_t("No medical encounters found."), {type: 'info'});
                return;
            }

            // Format encounters for display
            const formattedEncounters = encounters.map(encounter => {
                const formatted = {...encounter};

                // Format patient names for display
                if (encounter.patient_ids) {
                    formatted.patient_ids = this.pos.formatPatientIds(encounter.patient_ids);
                }

                // Add partner name for display
                if (encounter.partner_id && Array.isArray(encounter.partner_id)) {
                    formatted.partner_name = encounter.partner_id[1];
                }

                // Add practitioner name for display
                if (encounter.practitioner_id && Array.isArray(encounter.practitioner_id)) {
                    formatted.practitioner_name = encounter.practitioner_id[1];
                }

                // Add room name for display
                if (encounter.room_id && Array.isArray(encounter.room_id)) {
                    formatted.room_name = encounter.room_id[1];
                }

                // Add state display
                formatted.state_display = encounter.state === 'done' ? 'Done' : 'In Progress';

                return formatted;
            });

            const result = await this.dialog.add(EncounterSelectionPopup, {
                title: _t("Select Medical Encounter"),
                encounters: formattedEncounters,
            });

            if (result.confirmed && result.payload?.partner) {
                const partner = result.payload.partner;
                this.pos.get_order().set_partner(partner);
                await this.clickPartner(partner);

                const order = this.pos.get_order();
                if (order) {
                    order.medical_context = {
                        encounter_id: result.payload.encounter_id,
                        encounter_name: result.payload.encounter_name,
                        patient_ids: result.payload.patient_ids,
                        practitioner_id: result.payload.practitioner_id,
                        room_id: result.payload.room_id,
                    };
                }
            }
        } catch (error) {
            console.error("Error in encounter selection:", error);
            this.notification.add(_t("Error opening encounter selection"), {type: 'danger'});
        }
    },
});

console.log("Medical POS: Partner list extended with encounter selection");