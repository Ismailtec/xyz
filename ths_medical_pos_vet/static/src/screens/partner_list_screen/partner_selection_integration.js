/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { NewOrderSelectionPopup } from "@ths_medical_pos_vet/popups/new_order_selection_popup";
import { _t } from "@web/core/l10n/translation";

/**
 * Veterinary Integration for Partner Selection Workflow
 * Intercepts pet owner selection to show new order popup
 */
patch(PartnerList.prototype, {

    /**
     * Override clickPartner to handle vet workflow
     */
    async clickPartner(partner) {
        console.log("VET: Partner selected:", partner);

        // FIRST: Check if selected partner is a pet - if so, get the pet owner
        const isPet = partner.ths_partner_type_id &&
                     Array.isArray(partner.ths_partner_type_id) &&
                     partner.ths_partner_type_id[1] === 'Pet';

        if (isPet) {
            console.log("VET: Pet selected, finding pet owner");

            // Get pet owner from the pet's data
            let petOwner = null;

            if (partner.ths_pet_owner_id && Array.isArray(partner.ths_pet_owner_id)) {
                // Get pet owner from POS models
                const ownerId = partner.ths_pet_owner_id[0];
                petOwner = this.pos.models["res.partner"].get(ownerId);
            }

            if (petOwner) {
                console.log("VET: Found pet owner:", petOwner.name);

                // Show notification about automatic pet owner selection
                this.notification.add(
                    _t("Selected pet owner '%s' for pet '%s'", petOwner.name, partner.name),
                    { type: 'info', duration: 3000 }
                );

                // Use pet owner instead of pet for billing
                partner = petOwner; // Replace partner with pet owner
            } else {
                console.warn("VET: Pet has no owner, cannot proceed with billing");
                this.notification.add(
                    _t("Pet '%s' has no owner assigned. Please assign an owner first.", partner.name),
                    { type: 'warning' }
                );
                return;
            }
        }

        // SECOND: Check if this is a pet owner and order is new/empty
        const currentOrder = this.pos.get_order();
        const isNewOrder = !currentOrder.get_orderlines().length; // Empty order
        const isPetOwner = partner.ths_partner_type_id &&
                          Array.isArray(partner.ths_partner_type_id) &&
                          partner.ths_partner_type_id[1] === 'Pet Owner';

        // If pet owner and new order, show popup first
        if (isPetOwner && isNewOrder) {
            console.log("VET: Showing new order popup for pet owner");
            await this.showNewOrderPopup(partner);
        } else {
            // For non-pet owners or existing orders, use standard flow
            console.log("VET: Using standard partner selection flow");
            super.clickPartner(partner);
        }
    },

    /**
     * Show new order selection popup for pet owners
     */
    async showNewOrderPopup(partner) {
        try {
            console.log("VET: Loading popup data for partner:", partner.id);

            // Call backend to get popup data
            const popupData = await this.orm.call(
                'pos.order',
                '_create_new_order_popup',
                [partner.id]
            );

            if (!popupData) {
                console.log("VET: No popup data returned, using standard flow");
                super.clickPartner(partner);
                return;
            }

            console.log("VET: Popup data received:", popupData);

            // Show the new order selection popup
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

            console.log("VET: Popup result:", result);

            // Always set the partner (regardless of popup result)
            super.clickPartner(partner);

            // If popup was confirmed, show success message
            if (result.confirmed && !result.skipped) {
                this.notification.add(
                    _t("Medical context configured for %s", partner.name),
                    { type: 'success', duration: 3000 }
                );
            } else if (result.skipped) {
                this.notification.add(
                    _t("Encounter setup skipped for %s", partner.name),
                    { type: 'info', duration: 2000 }
                );
            }

        } catch (error) {
            console.error("VET: Error in new order popup workflow:", error);

            // Fallback to standard flow if popup fails
            this.notification.add(
                _t("Encounter setup failed, proceeding with standard order"),
                { type: 'warning' }
            );
            super.clickPartner(partner);
        }
    }
});

console.log("VET: Partner selection integration loaded");