/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

/**
 * Patch to fix pet species loading and display using new helper methods
 * Updated to use the new encounter patient formatting helper
 */
patch(PartnerList.prototype, {

    async loadEncountersForPopup() {
        try {
            console.log("VET: Loading encounters with enhanced species data using new helper methods...");

            // Load encounters with vet-specific fields
            const encounters = await this.pos.data.searchRead(
                'ths.medical.base.encounter',
                [
                    ('ths_pet_owner_id', '!=', false),
                    ('state', 'in', ['in_progress', 'done'])
                ],
                [
                    'id', 'name', 'encounter_date', 'partner_id', 'patient_ids',
                    'practitioner_id', 'room_id', 'state', 'ths_pet_owner_id'
                ],
                {
                    order: 'encounter_date desc',
                    limit: 50
                }
            );

            console.log("VET: Raw encounters loaded:", encounters.length);

            // Use new helper method for proper patient_ids formatting
            const encounterIds = encounters.map(enc => enc.id);
            const formattedPatients = await this.pos.data.call(
                'ths.medical.base.encounter',
                'get_formatted_patients_for_encounter_list',
                [encounterIds]
            );

            // Load species data separately for better reliability
            const allSpecies = await this.pos.data.searchRead(
                'ths.species',
                [],
                ['id', 'name', 'color'],
                { limit: 200 }
            );

            console.log("VET: Loaded species data:", allSpecies);

            // Create species lookup map
            const speciesMap = {};
            allSpecies.forEach(species => {
                speciesMap[species.id] = {
                    id: species.id,
                    name: species.name,
                    color: species.color || 0
                };
            });

            // Format encounters with enhanced patient species data
            this.formattedEncounters = encounters.map(encounter => {
                console.log(`VET: Formatting encounter ${encounter.name} with species data`);

                // Use new formatted patients from helper method
                const formattedPatientIds = formattedPatients[encounter.id] || [];

                // Enhanced patient formatting with species data
                encounter.patient_ids = formattedPatientIds.map(patient => {
                    // patient is now [id, name] from helper method
                    const petId = patient[0];
                    const petName = patient[1];

                    // We'll add species data by loading it separately
                    return [petId, petName, null]; // Placeholder for species
                });

                // Load species data for each patient
                this.loadSpeciesDataForPatients(encounter, speciesMap);

                // Format other fields
                this.formatEncounterData(encounter);

                // Add vet-specific context
                encounter.vet_context = {
                    is_veterinary: true,
                    pet_owner_id: encounter.ths_pet_owner_id,
                    species_map: speciesMap
                };

                return encounter;
            });

            console.log("VET: Formatted encounters with enhanced species data:", this.formattedEncounters.length);

        } catch (error) {
            console.error("VET: Error loading encounters with species data:", error);
            this.formattedEncounters = [];
        }
    },

    async loadSpeciesDataForPatients(encounter, speciesMap) {
        try {
            if (!encounter.patient_ids || encounter.patient_ids.length === 0) return;

            const patientIds = encounter.patient_ids.map(p => p[0]);
            const patientsWithSpecies = await this.pos.data.searchRead(
                'res.partner',
                [['id', 'in', patientIds]],
                ['id', 'name', 'ths_species_id'],
                { limit: 50 }
            );

            // Update patient data with species information
            encounter.patient_ids = encounter.patient_ids.map(patient => {
                const petId = patient[0];
                const petName = patient[1];
                const petData = patientsWithSpecies.find(p => p.id === petId);

                let speciesInfo = null;
                if (petData && petData.ths_species_id) {
                    const speciesId = Array.isArray(petData.ths_species_id)
                        ? petData.ths_species_id[0]
                        : petData.ths_species_id;

                    const speciesData = speciesMap[speciesId];
                    if (speciesData) {
                        speciesInfo = [speciesData.id, speciesData.name, speciesData.color];
                    }
                }

                console.log(`VET: Patient ${petName} species:`, speciesInfo);
                return [petId, petName, speciesInfo];
            });

        } catch (error) {
            console.error("VET: Error loading patient species data:", error);
        }
    },

    // Helper method to get species color class
    getSpeciesColorClass(colorIndex) {
        if (!colorIndex) return 'bg-secondary';

        const colorClasses = [
            'bg-secondary',   // 0 - grey
            'bg-danger',      // 1 - red
            'bg-warning',     // 2 - orange
            'bg-success',     // 3 - yellow/green
            'bg-info',        // 4 - light blue
            'bg-primary',     // 5 - blue
            'bg-dark',        // 6 - dark blue
            'bg-success',     // 7 - green
            'bg-warning',     // 8 - yellow
            'bg-info',        // 9 - light blue
            'bg-primary',     // 10 - blue
            'bg-secondary'    // 11+ - grey fallback
        ];

        return colorClasses[colorIndex] || 'bg-secondary';
    },

    // Helper method to check if species should be displayed
    shouldDisplaySpecies(speciesInfo) {
        return speciesInfo &&
               Array.isArray(speciesInfo) &&
               speciesInfo.length >= 2 &&
               speciesInfo[1] &&
               speciesInfo[1].toLowerCase() !== 'unknown';
    }
});

console.log("VET: Loaded enhanced species loading patch using new helper methods");