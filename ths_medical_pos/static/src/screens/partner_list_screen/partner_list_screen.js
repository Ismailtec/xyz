/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { registry } from "@web/core/registry";

const orm = registry.category("services").get("orm");

patch(PartnerList.prototype, {

    async willStart() {
        await Promise.all([
            orm.call("res.partner", "_load_pos_data", [{}, {}]),
            orm.call("ths.partner.type", "_load_pos_data", [{}, {}])
        ]).then(([partners, partnerTypes]) => {
            this.pos.models["res.partner"]?.add(partners.data || []);
            this.pos.models["ths.partner.type"]?.add(partnerTypes.data || []);
        });
        return super.willStart();
    },

    getPartners() {
        const allPartners = super.getPartners();
        const types = this.pos.models["ths.partner.type"]?.getAll() || [];

        return allPartners.filter(partner => {
            const type = types.find(t => t.id === partner.ths_partner_type_id?.[0]);
            return type?.is_customer;
        });
    },

    async clickPartner(partner) {
        return super.clickPartner(partner);
    },

    async openEncounterSelectionPopup() {
        // Placeholder for vet extension
    },
});
