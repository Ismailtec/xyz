import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PetSelectionPopup } from "@ths_medical_pos_vet/popups/pet_selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(ProductScreen.prototype, {

    async _onPartnerChanged(partner) {
        // Call parent logic first
        if (super._onPartnerChanged) {
            await super._onPartnerChanged(partner);
        }

        // Trigger pet selection popup for vet context
        if (partner && partner.ths_partner_type_id?.[1] === 'Pet Owner') {
            await this.showPetSelectionPopup(partner);
        }
    },

    async showPetSelectionPopup(partner) {
        try {
            // Check for existing encounter
            const encounter = await this.loadDailyEncounter(partner.id);

            const result = await makeAwaitable(this.dialog, PetSelectionPopup, {
                title: _t("Select Pets and Service Details"),
                partner: partner,
                encounter: encounter,
            });

            if (result.confirmed) {
                await this.applyPetSelectionToOrder(result.payload);
            }

        } catch (error) {
            console.error("Error in pet selection popup:", error);
        }
    },

    async loadDailyEncounter(partnerId) {
        const today = new Date().toISOString().split('T')[0];
        const encounters = await this.orm.searchRead(
            'ths.medical.base.encounter',
            [
                ('partner_id', '=', partnerId),
                ('encounter_date', '=', today)
            ],
            ['id', 'patient_ids', 'practitioner_id', 'room_id'],
            { limit: 1 }
        );

        return encounters.length > 0 ? encounters[0] : null;
    },

    async applyPetSelectionToOrder(selectionData) {
        const order = this.pos.get_order();

        // Set medical context on order
        order.medical_context = {
            patient_ids: selectionData.patient_ids,
            practitioner_id: selectionData.practitioner_id,
            room_id: selectionData.room_id,
        };

        // Load pending items for this encounter
        await this.loadAndApplyPendingItems(selectionData);
    },

    async loadAndApplyPendingItems(selectionData) {
        // Load pending items for the encounter
        const partner = this.pos.get_order().get_partner();
        if (!partner) return;

        const pendingItems = await this.orm.searchRead(
            'ths.pending.pos.item',
            [
                ('partner_id', '=', partner.id),
                ('state', '=', 'pending')
            ],
            ['id', 'product_id', 'qty', 'price_unit', 'description']
        );

        // Auto-add pending items to order
        for (const item of pendingItems) {
            // Use the existing pending items methodology to add products
            // This should follow the same logic as in pending_items_list_popup.js
        }
    }

    // TODO: Add encounter creation integration
    // TODO: Add pending items auto-population
});