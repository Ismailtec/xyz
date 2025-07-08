/** @odoo-module */

import {patch} from "@web/core/utils/patch";
import {ProductScreen} from "@point_of_sale/app/screens/product_screen/product_screen";
import {_t} from "@web/core/l10n/translation";
import {makeAwaitable} from "@point_of_sale/app/store/make_awaitable_dialog";
import {PetOrderSetupPopup} from "@ths_medical_pos_vet/popups/pet_order_setup_popup";

/**
 * Veterinary-specific enhancement of ProductScreen for pet selection
 */
patch(ProductScreen.prototype, {

    setup() {
        super.setup();
        // Store reference more safely for PyCharm
        this.originalOnPartnerChanged = this._onPartnerChanged || null;
    },

    async _onPartnerChanged(partner) {
        // Call parent method if it exists
        if (typeof super._onPartnerChanged === 'function') {
            await super._onPartnerChanged(partner);
        }

        // Trigger pet selection popup for vet context
        if (partner && this._isVetPetOwner(partner)) {
            await this.showPetSelectionPopup(partner);
        } else if (partner && this._isVetPet(partner)) {
            // If pet selected directly, auto-populate and show popup for owner
            await this.handleDirectPetSelection(partner);
        }
    },

    _isVetPetOwner(partner) {
        return partner.ths_partner_type_id &&
            Array.isArray(partner.ths_partner_type_id) &&
            partner.ths_partner_type_id[1] === 'Pet Owner';
    },

    _isVetPet(partner) {
        return partner.ths_partner_type_id &&
            Array.isArray(partner.ths_partner_type_id) &&
            partner.ths_partner_type_id[1] === 'Pet';
    },

    async handleDirectPetSelection(pet) {
        if (!pet.ths_pet_owner_id) {
            this.notification.add(_t("Pet has no owner assigned"), {type: 'warning'});
            return;
        }

        const owner = this.pos.models["res.partner"].get(pet.ths_pet_owner_id[0]);
        if (!owner) {
            this.notification.add(_t("Pet owner not found in POS"), {type: 'danger'});
            return;
        }

        // Set the owner as the billing customer
        const order = this.pos.get_order();
        order.set_partner(owner);

        // Pre-select this pet and show popup
        await this.showPetSelectionPopup(owner, [pet.id]);
    },

    async showPetSelectionPopup(partner, preSelectedPets = []) {
        try {
            // Check for existing encounter
            const encounter = await this.loadDailyEncounter(partner.id);

            const result = await makeAwaitable(this.dialog, PetOrderSetupPopup, {
                title: _t("Select Pets and Service Details"),
                partner: partner,
                encounter: encounter,
                preSelectedPets: preSelectedPets,
                isNewOrder: false, // NEW: Flag for consolidated popup (existing order modification)
            });

            if (result.confirmed) {
                await this.applyPetSelectionToOrder(result.payload);
            }

        } catch (error) {
            console.error("Error in pet selection popup:", error);
            this.notification.add(_t("Error opening pet selection"), {type: 'danger'});
        }
    },

    async loadDailyEncounter(partnerId) {
        try {
            const today = new Date().toISOString().split('T')[0];

            // Use preloaded encounter data instead of RPC
            const encounters = this.pos.models["ths.medical.base.encounter"]?.getAll() || [];
            const todayEncounters = encounters.filter(enc => {
                return enc.partner_id && enc.partner_id[0] === partnerId &&
                    enc.encounter_date === today;
            });

            if (todayEncounters.length > 0) {
                const encounter = todayEncounters[0];
                // Format patient_ids for display
                encounter.patient_ids_formatted = this.pos.formatPatientIds(encounter.patient_ids);
                return encounter;
            }

            return null;
        } catch (error) {
            console.error("Error loading daily encounter:", error);
            return null;
        }
    },

    async applyPetSelectionToOrder(selectionData) {
        const order = this.pos.get_order();

        // Set medical context on order
        order.medical_context = {
            patient_ids: selectionData.patient_ids,
            practitioner_id: selectionData.practitioner_id,
            room_id: selectionData.room_id,
        };

        // Update order header fields
        order.patient_ids = selectionData.patient_ids;
        order.practitioner_id = selectionData.practitioner_id;
        order.room_id = selectionData.room_id;

        console.log("Applied pet selection to order:", selectionData);

        // Load pending items for this context
        await this.loadAndNotifyPendingItems(selectionData);
    },

    async loadAndNotifyPendingItems(selectionData) {
        try {
            const partner = this.pos.get_order().get_partner();
            if (!partner) return;

            // Use preloaded pending items instead of RPC
            const pendingItems = this.pos.getPendingItems(partner.id);

            if (pendingItems.length > 0) {
                this.notification.add(
                    _t('%d pending items found. Please use the Pending Items button to add them.', pendingItems.length),
                    {type: 'info'}
                );
            }
        } catch (error) {
            console.error("Error loading pending items:", error);
        }
    },

    // Override base medical context methods for vet display
    getMedicalContext() {
        const order = this.pos.get_order();
        return order ? order.medical_context || {} : {};
    },

    hasMedicalContext() {
        const context = this.getMedicalContext();
        return !!(context.encounter_id || context.patient_ids?.length);
    },

    formatMedicalContextDisplay() {
        const context = this.getMedicalContext();
        const display = {
            encounter_name: context.encounter_name || '',
            patient_names: [],
            practitioner_name: '',
            room_name: ''
        };

        // Format patient names with species info for vet display
        if (context.patient_ids) {
            display.patient_names = this.pos.formatPatientIds(context.patient_ids);
        }

        // Format practitioner name
        if (context.practitioner_id && Array.isArray(context.practitioner_id)) {
            display.practitioner_name = context.practitioner_id[1];
        }

        // Format room name
        if (context.room_id && Array.isArray(context.room_id)) {
            display.room_name = context.room_id[1];
        }

        return display;
    }
});

console.log("VET: ProductScreen enhanced with consolidated pet order setup popup");