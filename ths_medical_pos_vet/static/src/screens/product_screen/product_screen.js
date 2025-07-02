/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { formatDateTime, formatDate } from "@web/core/l10n/dates";
//import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { _t } from "@web/core/l10n/translation";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { PetSelectionPopup } from "@ths_medical_pos_vet/popups/pet_selection_popup";

/**
 * Veterinary-specific enhancement of OrderWidget for membership display
 */
//patch(OrderWidget.prototype, {
//    formatMembershipDate(dateString) {
//        if (!dateString) {
//            return "";
//        }
//
//        try {
//            let date;
//            if (typeof dateString === 'string') {
//                date = new Date(dateString + 'T00:00:00');
//            } else if (dateString instanceof Date) {
//                date = dateString;
//            } else {
//                console.warn("Vet POS: Invalid membership date type:", typeof dateString, dateString);
//                return dateString.toString();
//            }
//
//            if (isNaN(date.getTime())) {
//                console.warn("Vet POS: Invalid membership date format:", dateString);
//                return dateString.toString();
//            }
//
//            return formatDate(date);
//        } catch (error) {
//            console.error("Vet POS: Error formatting membership date:", error);
//            return dateString.toString();
//        }
//    },
//
//    setup() {
//        super.setup();
//        console.log("Vet POS: OrderWidget enhanced with veterinary membership features for Odoo 18");
//
//        try {
//            this.vetEnhancementsLoaded = true;
//        } catch (error) {
//            console.error("Vet POS: Error during veterinary setup:", error);
//            this.vetEnhancementsLoaded = false;
//        }
//    },
//
//    getMembershipStatusColor(membershipState) {
//        const colorMap = {
//            'running': 'text-success',    // New model uses 'running'
//            'draft': 'text-warning',
//            'expired': 'text-danger',
//            'none': 'text-muted'
//        };
//        return colorMap[membershipState] || 'text-muted';
//    },
//
//    getMembershipStatusText(membershipState) {
//        const textMap = {
//            'running': 'Active Member',   // New model terminology
//            'draft': 'Membership Pending',
//            'expired': 'Membership Expired',
//            'none': 'No Membership'
//        };
//        return textMap[membershipState] || `Membership: ${membershipState}`;
//    }
//});

/**
 * Veterinary-specific enhancement of ProductScreen for pet selection
 */
patch(ProductScreen.prototype, {

    setup() {
        super.setup();
        this._originalOnPartnerChanged = this._onPartnerChanged;
    },

    async _onPartnerChanged(partner) {
        // Call parent logic first if it exists
        if (this._originalOnPartnerChanged) {
            await this._originalOnPartnerChanged(partner);
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
            this.notification.add(_t("Pet has no owner assigned"), { type: 'warning' });
            return;
        }

        const owner = this.pos.models["res.partner"].get(pet.ths_pet_owner_id[0]);
        if (!owner) {
            this.notification.add(_t("Pet owner not found in POS"), { type: 'danger' });
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

            const result = await makeAwaitable(this.dialog, PetSelectionPopup, {
                title: _t("Select Pets and Service Details"),
                partner: partner,
                encounter: encounter,
                preSelectedPets: preSelectedPets,
            });

            if (result.confirmed) {
                await this.applyPetSelectionToOrder(result.payload);
            }

        } catch (error) {
            console.error("Error in pet selection popup:", error);
            this.notification.add(_t("Error opening pet selection"), { type: 'danger' });
        }
    },

    async loadDailyEncounter(partnerId) {
        try {
            const today = new Date().toISOString().split('T')[0];
            const encounters = await this.orm.searchRead(
                'ths.medical.base.encounter',
                [
                    ('partner_id', '=', partnerId),
                    ('encounter_date', '=', today)
                ],
                ['id', 'name', 'patient_ids', 'practitioner_id', 'room_id'],
                { limit: 1 }
            );

            if (encounters.length > 0) {
                const encounter = encounters[0];
                // Format patient_ids using new helper method
                const formattedPatients = await this.pos.data.call(
                    'ths.medical.base.encounter',
                    'get_formatted_patients_for_encounter_list',
                    [[encounter.id]]
                );
                encounter.patient_ids = formattedPatients[encounter.id] || [];
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

        // Load pending items for this encounter
        await this.loadAndApplyPendingItems(selectionData);
    },

    async loadAndApplyPendingItems(selectionData) {
        try {
            const partner = this.pos.get_order().get_partner();
            if (!partner) return;

            const pendingItems = await this.orm.searchRead(
                'ths.pending.pos.item',
                [
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'pending')
                ],
                ['id', 'encounter_id', 'product_id', 'qty', 'price_unit', 'description', 'patient_id', 'practitioner_id', 'commission_pct', 'room_id'],
                { limit: 50 }
            );

            if (pendingItems.length > 0) {
                this.notification.add(
                    _t('%d pending items found. Please use the Pending Items button to add them.', pendingItems.length),
                    { type: 'info' }
                );
            }
        } catch (error) {
            console.error("Error loading pending items:", error);
        }
    }
});

console.log("Loaded vet product screen JS - compatible with Odoo 18 OWL 3:", "product_screen.js");