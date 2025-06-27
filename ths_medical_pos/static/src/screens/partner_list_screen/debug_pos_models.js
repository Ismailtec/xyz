/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

// Debug patch to log model loading for medical POS
patch(PosStore.prototype, {
    async processServerData() {
        const result = await super.processServerData();

        // Debug: Log all loaded models
        console.log("=== POS Models Debug (Updated) ===");
        console.log("All loaded models:", Object.keys(this.models));

        // Check specifically for medical models
        const medicalModels = [
            'ths.medical.base.encounter',
            'ths.partner.type',
            'appointment.resource',
            'res.partner'
        ];

        medicalModels.forEach(modelName => {
            if (this.models[modelName]) {
                const records = this.models[modelName].getAll();
                console.log(`✓ ${modelName} loaded with ${records.length} records`);

                if (modelName === 'res.partner' && records.length > 0) {
                    // Debug partner data structure
                    const samplePartners = records.slice(0, 2);
                    console.log("Sample partner data:", samplePartners);
                    samplePartners.forEach(partner => {
                        console.log(`Partner ${partner.name} - ths_partner_type_id:`, partner.ths_partner_type_id);
                    });
                }

                if (modelName === 'ths.medical.base.encounter' && records.length > 0) {
                    // Debug encounter data structure
                    const sampleEncounters = records.slice(0, 2);
                    console.log("Sample encounter data:", sampleEncounters);
                    sampleEncounters.forEach(encounter => {
                        console.log(`Encounter ${encounter.name}:`);
                        console.log(`  - partner_id:`, encounter.partner_id);
                        console.log(`  - patient_ids:`, encounter.patient_ids);
                        console.log(`  - practitioner_id:`, encounter.practitioner_id);
                        console.log(`  - room_id:`, encounter.room_id);
                    });
                }

                if (modelName === 'ths.partner.type' && records.length > 0) {
                    console.log("Partner types loaded:", records.map(pt => `${pt.id}: ${pt.name}`));
                }

            } else {
                console.log(`✗ ${modelName} NOT loaded`);
            }
        });

        console.log("=== End POS Models Debug (Updated) ===");

        return result;
    }
});