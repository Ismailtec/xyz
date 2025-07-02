/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { _t } from "@web/core/l10n/translation";
import { EncounterSelectionPopup } from "@ths_medical_pos_vet/popups/encounter_selection_popup";
import { NewOrderSelectionPopup } from "@ths_medical_pos_vet/popups/new_order_selection_popup";
import { registry } from "@web/core/registry";

const orm = registry.category("services").get("orm");

patch(PartnerList.prototype, {

    async willStart() {
        await Promise.all([
            orm.call("ths.medical.base.encounter", "_load_pos_data", [{}, {}]),
            orm.call("vet.pet.membership", "_load_pos_data", [{}, {}]),
            orm.call("ths.species", "_load_pos_data", [{}, {}]),
            orm.call("appointment.resource", "_load_pos_data", [{}, {}]),
            orm.call("calendar.event", "_load_pos_data", [{}, {}]),
            orm.call("ths.treatment.room", "_load_pos_data", [{}, {}]),
            orm.call("ths.pending.pos.item", "_load_pos_data", [{}, {}]),
            orm.call("park.checkin", "_load_pos_data", [{}, {}]),
        ]).then(results => {
            const models = [
                "ths.medical.base.encounter", "vet.pet.membership", "ths.species",
                "appointment.resource", "calendar.event", "ths.treatment.room",
                "ths.pending.pos.item", "park.checkin"
            ];
            results.forEach((res, idx) => {
                this.pos.models[models[idx]]?.add(res.data || []);
            });
        });

        return super.willStart();
    },

    getPetDisplayName(pet) {
        let name = pet.name;
        const species = pet.ths_species_id;
        if (Array.isArray(species) && species.length > 1) {
            name += ` (${species[1]})`;
        }
        return name;
    },

    async clickPartner(partner) {
        const type = this.pos.models["ths.partner.type"].get(partner.ths_partner_type_id?.[0]);
        const isPet = type?.name === "Pet";
        const isOwner = type?.name === "Pet Owner";

        if (isPet) {
            const ownerId = partner.ths_pet_owner_id?.[0];
            const petOwner = this.pos.models["res.partner"].get(ownerId);
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
            const popupData = await orm.call("pos.order", "_create_new_order_popup", [partner.id]);
            if (!popupData) return super.clickPartner(partner);

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

            super.clickPartner(partner);

            if (result.confirmed && !result.skipped) {
                this.notification.add(_t("Medical context configured for %s", partner.name), {
                    type: 'success', duration: 3000
                });
            } else if (result.skipped) {
                this.notification.add(_t("Encounter setup skipped for %s", partner.name), {
                    type: 'info', duration: 2000
                });
            }
        } else {
            return super.clickPartner(partner);
        }
    },

    async openEncounterSelectionPopup() {
        const encounters = this.pos.models["ths.medical.base.encounter"]?.getAll() || [];

        if (!encounters.length) {
            this.notification.add(_t("No medical encounters found."), { type: 'info' });
            return;
        }

        const result = await this.dialog.add(EncounterSelectionPopup, {
            title: _t("Select Medical Encounter"),
            encounters,
        });

        if (result.confirmed && result.payload?.partner) {
            const partner = result.payload.partner;
            this.pos.get_order().set_partner(partner);
            this.clickPartner(partner);

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
    },
});

console.log("VET: PartnerList extended with encounter and vet logic");
