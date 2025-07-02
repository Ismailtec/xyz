/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {PartnerList} from "@point_of_sale/app/screens/partner_list/partner_list";
import {_t} from "@web/core/l10n/translation";
import {EncounterSelectionPopup} from "@ths_medical_pos/popups/encounter_selection_popup";
import {NewOrderSelectionPopup} from "@ths_medical_pos_vet/popups/new_order_selection_popup";

patch(PartnerList.prototype, {

    getPetDisplayName(pet) {
        let name = pet.name;
        const species = pet.ths_species_id;
        if (Array.isArray(species) && species.length > 1) {
            name += ` (${species[1]})`;
        }
        return name;
    },

    async clickPartner(partner) {
        const type = this.pos.models["ths.partner.type"]?.get(partner.ths_partner_type_id?.[0]);
        const isPet = type?.name === "Pet";
        const isOwner = type?.name === "Pet Owner";

        if (isPet) {
            const ownerId = partner.ths_pet_owner_id?.[0];
            const petOwner = this.pos.models["res.partner"]?.get(ownerId);
            if (petOwner) {
                this.notification.add(_t("Selected pet owner '%s' for pet '%s'", petOwner.name, partner.name), {
                    type: 'info', duration: 3000
                });
                partner = petOwner;
            } else {
                this.notification.add(_t("Pet '%s' has no owner assigned.", partner.name), {
                    type: 'warning'
                });
                return;
            }
        }

        const currentOrder = this.pos.get_order();
        const isNewOrder = !currentOrder.get_orderlines().length;

        if (isOwner && isNewOrder) {
            try {
                const popupData = await this.orm.call("pos.order", "_create_new_order_popup", [partner.id]);
                if (!popupData) return await super.clickPartner(partner);

                const result = await this.dialog.add(NewOrderSelectionPopup, {
                    title: _t("Set up Order for %s", partner.name),
                    partner_id: popupData.partner_id,
                    partner_name: popupData.partner_name,
                    existing_encounter: popupData.existing_encounter,
                    pets: popupData.pets || [],
                    practitioners: popupData.practitioners || [],
                    rooms: popupData.rooms || [],
                    selected_pets: popupData.selected_pets || [],
                    selected_practitioner: popupData.selected_practitioner || false,
                    selected_room: popupData.selected_room || false,
                });

                // FIX B: Add await for async function call
                await super.clickPartner(partner);

                if (result.confirmed && !result.skipped) {
                    this.notification.add(_t("Medical context configured for %s", partner.name), {
                        type: 'success', duration: 3000
                    });
                } else if (result.skipped) {
                    this.notification.add(_t("Encounter setup skipped for %s", partner.name), {
                        type: 'info', duration: 2000
                    });
                }
            } catch (error) {
                console.error("Error in vet partner selection:", error);
                return await super.clickPartner(partner);
            }
        } else {
            return await super.clickPartner(partner);
        }
    },

    async openEncounterSelectionPopup() {
        try {
            const encounters = this.pos.models["ths.medical.base.encounter"]?.getAll() || [];

            if (!encounters.length) {
                this.notification.add(_t("No medical encounters found."), {type: 'info'});
                return;
            }

            // Format encounters for vet display
            const formattedEncounters = encounters.map(encounter => {
                const formatted = {...encounter};

                // Format patient names with species for vet display
                if (encounter.patient_ids) {
                    formatted.patient_ids = this.pos.formatPatientIds(encounter.patient_ids);
                }

                // Add partner name for display
                if (encounter.partner_id && Array.isArray(encounter.partner_id)) {
                    formatted.partner_name = encounter.partner_id[1];
                }

                // Add pet owner info for vet context
                if (encounter.ths_pet_owner_id && Array.isArray(encounter.ths_pet_owner_id)) {
                    formatted.pet_owner_name = encounter.ths_pet_owner_id[1];
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
                // FIX B: Add await for async function call
                await this.clickPartner(partner);

                const order = this.pos.get_order();
                if (order) {
                    order.medical_context = {
                        encounter_id: result.payload.encounter_id,
                        encounter_name: result.payload.encounter_name,
                        patient_ids: result.payload.patient_ids,
                        practitioner_id: result.payload.practitioner_id,
                        room_id: result.payload.room_id,
                        pet_owner_id: result.payload.pet_owner_id,
                    };
                }
            }
        } catch (error) {
            console.error("Error in vet encounter selection:", error);
            this.notification.add(_t("Error opening encounter selection"), {type: 'danger'});
        }
    },
});

console.log("VET: PartnerList extended with encounter and vet logic");