/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

/**
 * Patch PartnerList to filter only customer type partners
 * Shows only partners with ths_partner_type_id.is_customer = True
 */
patch(PartnerList.prototype, {

    getPartners() {
        // Get all partners using the parent method
        const allPartners = super.getPartners();

        // Filter to show only customer type partners
        const customerPartners = allPartners.filter(partner => {
            // Check if partner has a type and if it's a customer type
            if (partner.ths_partner_type_id && Array.isArray(partner.ths_partner_type_id)) {
                // We need to check if this partner type has is_customer = True
                // Since we have partner type ID, we need to check the actual type
                const partnerTypeId = partner.ths_partner_type_id[0];

                // Get partner type from POS models
                const partnerTypes = this.pos.models["ths.partner.type"]?.getAll() || [];
                const partnerType = partnerTypes.find(pt => pt.id === partnerTypeId);

                if (partnerType && partnerType.is_customer) {
                    return true;
                }
            }

            // For vet module: also include pets (since they're linked to pet owners who are customers)
            // and pet owners (who are customers)
            if (partner.ths_partner_type_id && Array.isArray(partner.ths_partner_type_id)) {
                const typeName = partner.ths_partner_type_id[1];
                if (typeName === 'Pet' || typeName === 'Pet Owner' || typeName === 'Patient' || typeName === 'Walk-in') {
                    return true;
                }
            }

            return false;
        });

        console.log(`Filtered partners: ${customerPartners.length} customer partners out of ${allPartners.length} total`);

        return customerPartners;
    },

    // Also apply filtering in search results
    async getNewPartners() {
        const newPartners = await super.getNewPartners();

        // Apply same customer filter to new search results
        const filteredNewPartners = newPartners.filter(partner => {
            // Check if partner type has is_customer flag
            if (partner.ths_partner_type_id) {
                // For new partners from search, we need to check the type
                const partnerTypes = this.pos.models["ths.partner.type"]?.getAll() || [];
                const typeId = Array.isArray(partner.ths_partner_type_id)
                    ? partner.ths_partner_type_id[0]
                    : partner.ths_partner_type_id;

                const partnerType = partnerTypes.find(pt => pt.id === typeId);

                if (partnerType && partnerType.is_customer) {
                    return true;
                }

                // Also check by name for vet-specific types
                const typeName = Array.isArray(partner.ths_partner_type_id)
                    ? partner.ths_partner_type_id[1]
                    : null;

                if (typeName && ['Pet', 'Pet Owner', 'Patient', 'Walk-in'].includes(typeName)) {
                    return true;
                }
            }

            return false;
        });

        console.log(`Filtered new partners: ${filteredNewPartners.length} customer partners out of ${newPartners.length} total`);

        return filteredNewPartners;
    }
});

console.log("Partner list patched with customer filtering");