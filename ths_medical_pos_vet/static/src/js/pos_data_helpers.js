/** @odoo-module */

import {patch} from "@web/core/utils/patch";
import {PosStore} from "@point_of_sale/app/store/pos_store";

/**
 * Veterinary-specific extensions to base medical POS
 * Extends base functionality with pet/species/membership logic
 */

patch(PosStore.prototype, {

    // VET: Helper method to get pet with species info (will be used by encounter/partner displays)
    getPetWithSpecies(petId) {
        const pet = this.models["res.partner"]?.get(petId);
        if (!pet || !pet.ths_species_id) return pet;

        const speciesId = Array.isArray(pet.ths_species_id) ? pet.ths_species_id[0] : pet.ths_species_id;
        const species = this.models["ths.species"]?.get(speciesId);

        return {
            ...pet,
            species_info: species,
            display_name: species ? `${pet.name} (${species.name})` : pet.name,
            species_color_index: species ? species.color : 0
        };
    },

    // VET: Helper method to get membership status for pets (will be used by encounter displays)
    getPetMembershipStatus(petId) {
        const memberships = this.models["vet.pet.membership"]?.getAll().filter(m =>
                m.patient_ids && m.patient_ids.some(p =>
                    Array.isArray(p) ? p[0] === petId : p === petId
                )
        ) || [];

        // Find active membership
        const activeMembership = memberships.find(m =>
            m.state === 'running' && m.is_paid === true
        );

        return {
            has_membership: !!activeMembership,
            membership_status: activeMembership ? 'active' : 'none',
            membership_data: activeMembership || null
        };
    },

    // VET: Helper method to get Odoo standard color class from species color index
    getSpeciesColorClass(speciesColorIndex) {
        // Use Odoo's standard color system (o_tag_color_X classes)
        return `o_tag_color_${speciesColorIndex || 0}`;
    }
});

console.log("Vet POS: Species and membership helpers loaded");