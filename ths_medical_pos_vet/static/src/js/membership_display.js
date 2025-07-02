/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { EncounterSelectionPopup } from "@ths_medical_pos/popups/encounter_selection_popup";

/**
 * Veterinary-specific patch for encounter selection popup
 * Now uses the new vet.pet.membership model instead of the old membership module
 */
patch(EncounterSelectionPopup.prototype, {

    setup() {
        super.setup();
        // Load membership data using new membership model
        this.loadPetMembershipData();
    },

    async loadPetMembershipData() {
        try {
            console.log("VET: Loading pet membership data using new membership model...");

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

            console.log(`VET: Loading membership data for ${allPatientIds.size} pets using new model`);

            // Load pet memberships using new vet.pet.membership model
            const petMemberships = await this.pos.data.searchRead(
                'vet.pet.membership',
                [
                    ('patient_ids', 'in', Array.from(allPatientIds)),
                    ('state', '=', 'running'),
                    ('is_paid', '=', true),
                    ('valid_from', '<=', new Date().toISOString().split('T')[0]),
                    ('valid_to', '>=', new Date().toISOString().split('T')[0])
                ],
                ['id', 'partner_id', 'patient_ids', 'membership_service_id', 'valid_from', 'valid_to'],
                { limit: 200 }
            );

            console.log("VET: Pet memberships loaded using new model:", petMemberships);

            // Create membership lookup map: pet_id -> membership_data
            this.petMembershipMap = {};

            petMemberships.forEach(membership => {
                membership.patient_ids.forEach(petId => {
                    this.petMembershipMap[petId] = {
                        membership_id: membership.id,
                        pet_name: `Pet #${petId}`, // Will be filled from encounter data
                        owner_name: membership.partner_id[1],
                        service_name: membership.membership_service_id[1],
                        membership_state: 'running', // From new model
                        membership_start: membership.valid_from,
                        membership_stop: membership.valid_to,
                        is_valid: true
                    };
                });
            });

            console.log("VET: Pet membership map created using new model:", this.petMembershipMap);

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
                                owner_name: 'Unknown Owner',
                                is_valid: false
                            }
                        };
                    });
                }
            });

            console.log("VET: Enhanced encounters with new membership data");

        } catch (error) {
            console.error("VET: Error loading pet membership data:", error);
            this.petMembershipMap = {};
        }
    },

    getMembershipStatusColor(membershipState) {
        const colorMap = {
            'running': 'bg-success',    // New model uses 'running' instead of 'paid'
            'draft': 'bg-warning',
            'expired': 'bg-danger',
            'none': 'bg-light text-dark'
        };
        return colorMap[membershipState] || 'bg-light text-dark';
    },

    getMembershipStatusText(membershipState) {
        const textMap = {
            'running': 'Active',       // New model terminology
            'draft': 'Pending',
            'expired': 'Expired',
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

console.log("VET: Loaded NEW membership status display patch for encounter popup using vet.pet.membership model");