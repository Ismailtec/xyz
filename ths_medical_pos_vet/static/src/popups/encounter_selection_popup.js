/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {EncounterSelectionPopup} from "@ths_medical_pos/popups/encounter_selection_popup";

patch(EncounterSelectionPopup.prototype, {
    setup() {
        super.setup();

        // FIX 2: Declare properties on the component instance to avoid PyCharm warnings
        Object.defineProperty(this, 'speciesById', {
            value: {},
            writable: true,
            configurable: true
        });

        Object.defineProperty(this, 'membershipByPetId', {
            value: {},
            writable: true,
            configurable: true
        });

        // Build species lookup for vet enhancements
        const allSpecies = this.pos.models["ths.species"]?.getAll() || [];
        for (const species of allSpecies) {
            this.speciesById[species.id] = species.name;
        }

        // Build membership lookup for vet enhancements
        const allMemberships = this.pos.models["vet.pet.membership"]?.getAll() || [];
        for (const membership of allMemberships) {
            if (membership.patient_ids && Array.isArray(membership.patient_ids)) {
                for (const patient of membership.patient_ids) {
                    const petId = Array.isArray(patient) ? patient[0] : (patient.id || patient);
                    if (petId) {
                        this.membershipByPetId[petId] = membership.state === 'running' && membership.is_paid ? 'active' : 'inactive';
                    }
                }
            }
        }
    },

    getEnhancedPatientName(patientData) {
        let petName = "Unknown Pet";
        let petId = null;

        // Extract pet info from different formats
        if (Array.isArray(patientData) && patientData.length >= 2) {
            petId = patientData[0];
            petName = patientData[1];
        } else if (patientData && typeof patientData === 'object') {
            petId = patientData.id;
            petName = patientData.name;
        } else if (typeof patientData === 'string') {
            petName = patientData;
        }

        if (!petId) return petName;

        // Get pet details from preloaded data
        const pet = this.pos.models["res.partner"]?.get(petId);
        if (!pet) return petName;

        // Add species info - don't show if species not found
        let displayName = petName;
        if (pet.ths_species_id) {
            const speciesId = Array.isArray(pet.ths_species_id) ? pet.ths_species_id[0] : pet.ths_species_id;
            const speciesName = this.speciesById[speciesId];
            if (speciesName) {
                displayName = `${petName} (${speciesName})`;
            }
        }

        // Add membership badge
        const membershipStatus = this.membershipByPetId[petId];
        if (membershipStatus === "active") {
            displayName += " 🌟";
        } else if (membershipStatus === "inactive") {
            displayName += " ⚠️";
        }

        return displayName;
    },

    get formattedEncounters() {
        return (this.props.encounters || []).map(encounter => {
            const formatted = {...encounter};

            // Enhanced patient formatting for vet context
            if (Array.isArray(encounter.patient_ids)) {
                formatted.patient_ids = encounter.patient_ids.map(patientData =>
                    this.getEnhancedPatientName(patientData)
                ).filter(Boolean);
            }

            return formatted;
        });
    },

    // Override confirmSelection to add vet-specific payload fields
    confirmSelection(encounter) {
        console.log("Vet encounter selected:", encounter);

        // Get partner from preloaded data
        const partnerId = Array.isArray(encounter.partner_id) ? encounter.partner_id[0] : encounter.partner_id;
        const partner = this.pos.models["res.partner"]?.get(partnerId) || null;

        console.log("Resolved partner:", partner);

        // Format encounter data for payload - VET ENHANCED
        const payload = {
            partner,
            encounter_id: encounter.id,
            encounter_name: encounter.name,
            patient_ids: encounter.patient_ids || [],
            practitioner_id: encounter.practitioner_id || null,
            room_id: encounter.room_id || null,
            // Add vet-specific fields
            pet_owner_id: encounter.ths_pet_owner_id || null,
        };

        this.props.close({
            confirmed: true,
            payload: payload,
        });
    },
});

console.log("VET: EncounterSelectionPopup enhanced with species and membership info");