/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { _t } from "@web/core/l10n/translation";

/**
 * VET EXTENSION: ths_medical_pos_vet/static/src/screens/partner_list_screen/partner_list_screen.js
 * Same filename as base module for proper extension
 *
 * Veterinary-specific extension of PartnerList
 * Extends the medical base functionality with vet-specific features
 */
patch(PartnerList.prototype, {

    async loadAndApplyPartnerTypes() {
        try {
            console.log("=== VET: Loading partner types with vet extensions ===");

            // Call parent method first
            await super.loadAndApplyPartnerTypes();

            // Add vet-specific type loading
            await this.loadVetSpecificData();

        } catch (error) {
            console.error("VET: Error loading partner types:", error);
        }
    },

    async loadVetSpecificData() {
        try {
            console.log("VET: Loading vet-specific partner data...");

            // Load pet-owner relationships for better display
            const petsWithOwners = await this.pos.data.searchRead(
                'res.partner',
                [
                    ['ths_partner_type_id.name', '=', 'Pet'],
                    ['ths_pet_owner_id', '!=', false]
                ],
                ['id', 'name', 'ths_pet_owner_id', 'ths_species_id']
            );

            console.log("VET: Loaded pets with owners:", petsWithOwners);

            // Apply enhanced display names for pets in POS
            const posPartners = this.pos.models["res.partner"].getAll();

            petsWithOwners.forEach(petData => {
                const posPartner = posPartners.find(p => p.id === petData.id);
                if (posPartner) {
                    // Store vet-specific data for better display
                    posPartner.vet_data = {
                        is_pet: true,
                        owner_id: petData.ths_pet_owner_id,
                        species_id: petData.ths_species_id
                    };
                    console.log(`VET: Enhanced pet data for ${posPartner.name}`);
                }
            });

            // Load pet owners data
            const petOwners = await this.pos.data.searchRead(
                'res.partner',
                [['ths_partner_type_id.name', '=', 'Pet Owner']],
                ['id', 'name', 'membership_state', 'membership_start', 'membership_stop']
            );

            console.log("VET: Loaded pet owners:", petOwners);

            // Apply membership data for pet owners
            petOwners.forEach(ownerData => {
                const posPartner = posPartners.find(p => p.id === ownerData.id);
                if (posPartner) {
                    posPartner.vet_data = {
                        is_pet_owner: true,
                        membership_state: ownerData.membership_state,
                        membership_start: ownerData.membership_start,
                        membership_stop: ownerData.membership_stop
                    };
                    console.log(`VET: Enhanced owner data for ${posPartner.name} - membership: ${ownerData.membership_state}`);
                }
            });

        } catch (error) {
            console.error("VET: Error loading vet-specific data:", error);
        }
    },

    async loadEncountersForPopup() {
        try {
            console.log("VET: Loading encounters with vet context...");

            // Load encounters with vet-specific fields
            const encounters = await this.pos.data.searchRead(
                'ths.medical.base.encounter',
                [
                    ['ths_pet_owner_id', '!=', false],  // VET: Use pet owner field
                    ['state', 'in', ['in_progress', 'done']]
                ],
                [
                    'id', 'name', 'encounter_date', 'partner_id', 'patient_ids',
                    'practitioner_id', 'room_id', 'state',
                    'ths_pet_owner_id'  // VET: Include pet owner field
                ],
                {
                    order: 'encounter_date desc',
                    limit: 50
                }
            );

            console.log("VET: Raw vet encounters loaded:", encounters);

            // Format with vet-specific logic
            this.formattedEncounters = await Promise.all(encounters.map(async (encounter) => {
                console.log(`VET: Formatting encounter ${encounter.name}:`, encounter);

                // Standard formatting from parent
                await this.formatEncounterData(encounter);

                // VET: Add vet-specific context
                encounter.vet_context = {
                    is_veterinary: true,
                    pet_owner_id: encounter.ths_pet_owner_id,
                };

                return encounter;
            }));

            console.log("VET: Formatted vet encounters:", this.formattedEncounters);
        } catch (error) {
            console.error("VET: Error loading vet encounters:", error);
            this.formattedEncounters = [];
        }
    },

    async formatEncounterData(encounter) {
        // Helper method to format encounter data (DRY principle)

        // Fix partner_id formatting
        if (encounter.partner_id && typeof encounter.partner_id === 'number') {
            try {
                const partners = await this.pos.data.searchRead(
                    'res.partner',
                    [['id', '=', encounter.partner_id]],
                    ['id', 'name']
                );
                encounter.partner_id = partners.length > 0 ? [partners[0].id, partners[0].name] : false;
            } catch (error) {
                encounter.partner_id = [encounter.partner_id, `Pet Owner #${encounter.partner_id}`];
            }
        }

        // Fix practitioner_id formatting
        if (encounter.practitioner_id && typeof encounter.practitioner_id === 'number') {
            try {
                const practitioners = await this.pos.data.searchRead(
                    'appointment.resource',
                    [['id', '=', encounter.practitioner_id]],
                    ['id', 'name']
                );
                encounter.practitioner_id = practitioners.length > 0 ? [practitioners[0].id, practitioners[0].name] : false;
            } catch (error) {
                encounter.practitioner_id = [encounter.practitioner_id, `Practitioner #${encounter.practitioner_id}`];
            }
        }

        // Fix room_id formatting
        if (encounter.room_id && typeof encounter.room_id === 'number') {
            try {
                const rooms = await this.pos.data.searchRead(
                    'appointment.resource',
                    [['id', '=', encounter.room_id]],
                    ['id', 'name']
                );
                encounter.room_id = rooms.length > 0 ? [rooms[0].id, rooms[0].name] : false;
            } catch (error) {
                encounter.room_id = [encounter.room_id, `Room #${encounter.room_id}`];
            }
        }

        // Fix patient_ids formatting
        let patientNames = [];
        if (encounter.patient_ids && encounter.patient_ids.length > 0) {
            if (typeof encounter.patient_ids[0] === 'number') {
                try {
                    const patients = await this.pos.data.searchRead(
                        'res.partner',
                        [['id', 'in', encounter.patient_ids]],
                        ['id', 'name', 'ths_species_id']  // VET: Include species
                    );
                    patientNames = patients.map(p => [p.id, p.name, p.ths_species_id]);
                } catch (error) {
                    patientNames = encounter.patient_ids.map(id => [id, `Pet #${id}`, null]);
                }
            } else {
                patientNames = encounter.patient_ids;
            }
        }
        encounter.patient_ids = patientNames;
    },

    // VET: Override encounter selection to add vet-specific context
    async openEncounterSelectionPopup() {
        try {
            console.log("VET: Opening vet encounter selection popup");

            // Call parent method but with vet context
            await super.openEncounterSelectionPopup();

        } catch (error) {
            console.error("VET: Error in vet encounter selection:", error);
            this.notification.add(_t("VET: Error opening encounter selection: %s", error.message), { type: 'danger' });
        }
    },

    // VET: Helper method to get pet display name with species
    getVetPetDisplayName(petData) {
        if (!petData || petData.length < 2) return 'Unknown Pet';

        const petName = petData[1];
        const speciesData = petData[2]; // [species_id, species_name] or null

        if (speciesData && Array.isArray(speciesData) && speciesData.length > 1) {
            return `${petName} (${speciesData[1]})`;
        }

        return petName;
    },

    // VET: Helper method to check membership validity
    isValidMembership(partner) {
        if (!partner.vet_data || !partner.vet_data.is_pet_owner) {
            return true; // Non-pet-owners don't need membership validation
        }

        const membershipState = partner.vet_data.membership_state;
        return ['paid', 'free'].includes(membershipState);
    }
});

console.log("VET: Loaded vet partner list screen extensions", "vet_partner_list_screen.js");