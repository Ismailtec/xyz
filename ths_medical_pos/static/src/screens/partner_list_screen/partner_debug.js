/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

// Debug patch to show partner data when partner list opens
patch(PartnerList.prototype, {
    setup() {
        super.setup();

        // Debug partner data when partner list opens
        setTimeout(() => {
            console.log("=== PARTNER DEBUG ===");
            const partners = this.getPartners().slice(0, 3); // First 3 partners

            partners.forEach(partner => {
                console.log(`Partner: ${partner.name}`);
                console.log(`  ID: ${partner.id}`);
                console.log(`  ths_partner_type_id:`, partner.ths_partner_type_id);
                console.log(`  raw data:`, partner.raw);
                console.log(`  raw ths_partner_type_id:`, partner.raw?.ths_partner_type_id);
                console.log("  ---");
            });

            console.log("=== END PARTNER DEBUG ===");
        }, 1000);
    }
});