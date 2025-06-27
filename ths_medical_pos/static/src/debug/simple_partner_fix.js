/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(PartnerList.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();

        // Load partner types and apply them immediately
        this.loadAndApplyPartnerTypes();
    },

    async loadAndApplyPartnerTypes() {
        try {
            console.log("=== LOADING PARTNER TYPES DIRECTLY ===");

            // Step 1: Get partner types directly via searchRead
            const partnerTypes = await this.pos.data.searchRead(
                'ths.partner.type',
                [['active', '=', true]],
                ['id', 'name']
            );

            console.log("Loaded partner types:", partnerTypes);

            // Step 2: Get partners WITH their type IDs directly (bypass POS models)
            const partnersWithTypes = await this.pos.data.searchRead(
                'res.partner',
                [['ths_partner_type_id', '!=', false]],
                ['id', 'name', 'ths_partner_type_id']
            );

            console.log("Partners with types from database:", partnersWithTypes);

            // Step 3: Create type map for quick lookup
            const typeMap = {};
            partnerTypes.forEach(type => {
                typeMap[type.id] = type.name;
            });

            // Step 4: Apply types to POS partners
            const posPartners = this.pos.models["res.partner"].getAll();
            console.log(`Applying types to ${posPartners.length} POS partners...`);

            let appliedCount = 0;
            posPartners.forEach(partner => {
                // Find this partner in our database results
                const dbPartner = partnersWithTypes.find(p => p.id === partner.id);

                if (dbPartner && dbPartner.ths_partner_type_id) {
                    const typeId = Array.isArray(dbPartner.ths_partner_type_id)
                        ? dbPartner.ths_partner_type_id[0]
                        : dbPartner.ths_partner_type_id;

                    const typeName = typeMap[typeId];

                    if (typeName) {
                        // Apply the type as [id, name] format
                        partner.ths_partner_type_id = [typeId, typeName];
                        console.log(`✓ Applied type "${typeName}" to partner "${partner.name}"`);
                        appliedCount++;
                    } else {
                        console.log(`✗ Partner "${partner.name}" has type ID ${typeId} but type name not found`);
                    }
                } else {
                    console.log(`- Partner "${partner.name}" has no type in database`);
                }
            });

            console.log(`=== APPLIED TYPES TO ${appliedCount} PARTNERS ===`);

        } catch (error) {
            console.error("Error loading partner types:", error);
        }
    },
});