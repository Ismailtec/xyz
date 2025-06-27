/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

// Simple test to verify partner type data access
patch(PartnerList.prototype, {
    setup() {
        super.setup();

        // Add test button action
        this.testPartnerTypes();
    },

    async testPartnerTypes() {
        try {
            console.log("=== TESTING PARTNER TYPE ACCESS ===");

            // Test 1: Can we read partner types?
            const types = await this.pos.data.searchRead(
                'ths.partner.type',
                [],
                ['id', 'name']
            );
            console.log("✓ Partner types accessible:", types.length, "types");

            // Test 2: Can we read partners with types?
            const partners = await this.pos.data.searchRead(
                'res.partner',
                [['id', 'in', [3, 31, 33, 34, 37]]],  // Test specific partner IDs from your DB
                ['id', 'name', 'ths_partner_type_id']
            );
            console.log("✓ Partners with type field:", partners);

            // Test 3: Show what we got
            partners.forEach(partner => {
                console.log(`Partner ${partner.name} (ID: ${partner.id}): type_id = ${partner.ths_partner_type_id}`);
            });

            console.log("=== END PARTNER TYPE TEST ===");

        } catch (error) {
            console.error("✗ Partner type test failed:", error);
        }
    }
});