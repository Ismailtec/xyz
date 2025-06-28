/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

/**
 * Patch to fix pet species loading and display
 * Addresses issue where pets show as "unknown species" despite having species assigned
 */
patch(PartnerList.prototype, {

    async loadEncountersForPopup() {
        try {
            console.log("VET: Loading encounters with enhanced species data...");

            // Load encounters with vet-specific fields
            const encounters = await this.pos.data.searchRead(
                'ths.medical.base.encounter',
                [
                    ['ths_pet_owner_id', '!=', false],
                    ['state', 'in', ['in_progress', 'done']]
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

            // Format encounters with enhanced pet species data
            this.formattedEncounters = await Promise.all(encounters.map(async (encounter) => {
                console.log(`VET: Formatting encounter ${encounter.name} with species data`);

                // Standard formatting from parent
                await this.formatEncounterData(encounter);

                // Enhanced patient formatting with species data
                if (encounter.patient_ids && encounter.patient_ids.length > 0) {
                    const patientIds = encounter.patient_ids.map(p => Array.isArray(p) ? p[0] : p);

                    try {
                        // Load patients with species information
                        const patientsWithSpecies = await this.pos.data.searchRead(
                            'res.partner',
                            [['id', 'in', patientIds]],
                            ['id', 'name', 'ths_species_id'],
                            { limit: 50 }
                        );

                        console.log("VET: Patients with species:", patientsWithSpecies);

                        // Format patient data with species information
                        encounter.patient_ids = patientsWithSpecies.map(patient => {
                            let speciesInfo = null;

                            if (patient.ths_species_id) {
                                let speciesId;
                                if (Array.isArray(patient.ths_species_id)) {
                                    speciesId = patient.ths_species_id[0];
                                    speciesInfo = [patient.ths_species_id[0], patient.ths_species_id[1]];
                                } else {
                                    speciesId = patient.ths_species_id;
                                    const speciesData = speciesMap[speciesId];
                                    if (speciesData) {
                                        speciesInfo = [speciesData.id, speciesData.name];
                                    }
                                }

                                // Add color information if available
                                if (speciesInfo && speciesMap[speciesId]) {
                                    speciesInfo.push(speciesMap[speciesId].color);
                                }
                            }

                            console.log(`VET: Patient ${patient.name} species:`, speciesInfo);

                            // Return patient data in format: [id, name, species_info]
                            return [
                                patient.id,
                                patient.name,
                                speciesInfo // [species_id, species_name, species_color] or null
                            ];
                        });

                    } catch (error) {
                        console.error("VET: Error loading patient species data:", error);
                        // Fallback to basic formatting
                        encounter.patient_ids = encounter.patient_ids.map(p =>
                            Array.isArray(p) ? p : [p, `Pet #${p}`, null]
                        );
                    }
                }

                // Add vet-specific context
                encounter.vet_context = {
                    is_veterinary: true,
                    pet_owner_id: encounter.ths_pet_owner_id,
                    species_map: speciesMap
                };

                return encounter;
            }));

            console.log("VET: Formatted encounters with enhanced species data:", this.formattedEncounters.length);

        } catch (error) {
            console.error("VET: Error loading encounters with species data:", error);
            this.formattedEncounters = [];
        }
    },

    // Helper method to get species color class
    getSpeciesColorClass(colorIndex) {
        if (!colorIndex) return 'bg-secondary';

        // Odoo color palette mapping
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

console.log("VET: Loaded enhanced species loading patch");