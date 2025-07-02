/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { registry } from "@web/core/registry";

const orm = registry.category("services").get("orm");
const posModel = registry.category("pos_models").get("pos.model");

async function refreshModels(modelNames = []) {
    for (const model of modelNames) {
        const result = await orm.call(model, "_load_pos_data", [{}, {}]);
        if (result && result.data) {
            posModel.db.addData(model, result.data);
        }
    }
}

/**
 * Patch PartnerList to filter only customer type partners
 * Shows only partners with ths_partner_type_id.is_customer = True
 * Also refreshes required models when screen mounts
 */

patch(PartnerList.prototype, {

    async willStart() {
        await refreshModels([
            'res.partner',
            'ths.partner.type',
            'ths.medical.base.encounter',
            'ths.pending.pos.item',
            'ths.treatment.room',
            'appointment.resource',
            'calendar.event',
            'ths.species',
            'vet.pet.membership',
            'park.checkin',
        ]);
        return super.willStart();
    },

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
                return partnerType?.is_customer;
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
                return partnerType?.is_customer;
            }
            return false;
        });

        console.log(`Filtered new partners: ${filteredNewPartners.length} customer partners out of ${newPartners.length} total`);

        return filteredNewPartners;
    }
});

console.log("Partner list patched with customer filtering");