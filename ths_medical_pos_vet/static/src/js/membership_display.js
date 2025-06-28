/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { EncounterSelectionPopup } from "@ths_medical_pos/popups/encounter_selection_popup";

/**
 * Veterinary-specific patch for encounter selection popup
 * Adds correct membership status display for each pet
 */
patch(EncounterSelectionPopup.prototype, {

    setup() {
        super.setup();

        // Load membership data for pets
        this.loadPetMembershipData();
    },

    async loadPetMembershipData() {
        try {
            console.log("VET: Loading pet membership data for encounters...");

            // Get all patient IDs from encounters
            const allPatientIds = new Set();
            this.props.encounters.forEach(encounter => {
                if (encounter.patient_ids) {
                    encounter.patient_ids.forEach(patient => {
                        if (Array.isArray(patient) && patient[0]) {
                            allPatientIds.add(patient[0]);
                        }
                    });
                }
            });

            if (allPatientIds.size === 0) {
                console.log("VET: No patients found in encounters");
                return;
            }

            console.log(`VET: Loading membership data for ${allPatientIds.size} pets`);

            // Load pet membership data from their owners
            const petsWithMembership = await this.pos.data.searchRead(
                'res.partner',
                [
                    ['id', 'in', Array.from(allPatientIds)],
                    ['ths_partner_type_id.name', '=', 'Pet']
                ],
                ['id', 'name', 'ths_pet_owner_id'],
                { limit: 200 }
            );

            console.log("VET: Pets with owner data:", petsWithMembership);

            // Get unique owner IDs
            const ownerIds = [...new Set(petsWithMembership
                .map(pet => pet.ths_pet_owner_id)
                .filter(owner => owner && Array.isArray(owner))
                .map(owner => owner[0])
            )];

            if (ownerIds.length === 0) {
                console.log("VET: No pet owners found");
                return;
            }

            // Load membership data for owners
            const ownersWithMembership = await this.pos.data.searchRead(
                'res.partner',
                [['id', 'in', ownerIds]],
                ['id', 'name', 'membership_state', 'membership_start', 'membership_stop'],
                { limit: 100 }
            );

            console.log("VET: Owners with membership data:", ownersWithMembership);

            // Create membership lookup map: pet_id -> membership_data
            this.petMembershipMap = {};

            petsWithMembership.forEach(pet => {
                if (pet.ths_pet_owner_id && Array.isArray(pet.ths_pet_owner_id)) {
                    const ownerId = pet.ths_pet_owner_id[0];
                    const ownerData = ownersWithMembership.find(owner => owner.id === ownerId);

                    if (ownerData) {
                        this.petMembershipMap[pet.id] = {
                            pet_name: pet.name,
                            owner_name: ownerData.name,
                            membership_state: ownerData.membership_state,
                            membership_start: ownerData.membership_start,
                            membership_stop: ownerData.membership_stop,
                            membership_id: ownerId // Owner's membership ID
                        };
                    }
                }
            });

            console.log("VET: Pet membership map created:", this.petMembershipMap);

            // Enhance encounters with pet membership data
            this.props.encounters.forEach(encounter => {
                if (encounter.patient_ids) {
                    encounter.pet_memberships = encounter.patient_ids.map(patient => {
                        const petId = Array.isArray(patient) ? patient[0] : patient;
                        const petName = Array.isArray(patient) ? patient[1] : `Pet #${petId}`;
                        const membershipData = this.petMembershipMap[petId];

                        return {
                            pet_id: petId,
                            pet_name: petName,
                            membership_data: membershipData || {
                                pet_name: petName,
                                membership_state: 'none',
                                owner_name: 'Unknown Owner'
                            }
                        };
                    });
                }
            });

            console.log("VET: Enhanced encounters with membership data");

        } catch (error) {
            console.error("VET: Error loading pet membership data:", error);
            this.petMembershipMap = {};
        }
    },

    getMembershipStatusColor(membershipState) {
        const colorMap = {
            'paid': 'bg-success',
            'free': 'bg-success',
            'invoiced': 'bg-warning',
            'canceled': 'bg-danger',
            'old': 'bg-secondary',
            'none': 'bg-light text-dark'
        };
        return colorMap[membershipState] || 'bg-light text-dark';
    },

    getMembershipStatusText(membershipState) {
        const textMap = {
            'paid': 'Active',
            'free': 'Active (Free)',
            'invoiced': 'Pending Payment',
            'canceled': 'Cancelled',
            'old': 'Expired',
            'none': 'No Membership'
        };
        return textMap[membershipState] || 'Unknown';
    },

    formatMembershipDate(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString();
        } catch (error) {
            return dateString;
        }
    }
});

console.log("VET: Loaded membership status display patch for encounter popup");