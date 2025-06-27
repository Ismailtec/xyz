/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { EncounterSelectionPopup } from "@ths_medical_pos/popups/encounter_selection_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerList.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        // Load partner types and encounters on setup
        this.loadPartnerTypesAndEncounters();
    },

    async loadPartnerTypesAndEncounters() {
        try {
            console.log("=== LOADING PARTNER TYPES AND ENCOUNTERS (FIXED) ===");

            // Load partner types
            await this.loadAndApplyPartnerTypes();

            // Load encounters for the encounter popup
            await this.loadEncountersForPopup();

        } catch (error) {
            console.error("Error loading partner types and encounters:", error);
        }
    },

    async loadAndApplyPartnerTypes() {
        try {
            console.log("Loading partner types...");

            // Step 1: Get partner types directly via searchRead
            const partnerTypes = await this.pos.data.searchRead(
                'ths.partner.type',
                [['active', '=', true]],
                ['id', 'name']
            );

            console.log("Loaded partner types:", partnerTypes);

            // Step 2: Get partners WITH their type IDs directly
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
                    }
                }
            });

            console.log(`=== APPLIED TYPES TO ${appliedCount} PARTNERS ===`);
        } catch (error) {
            console.error("Error loading partner types:", error);
        }
    },

    async loadEncountersForPopup() {
        try {
            console.log("Loading encounters for popup...");

            // Load encounters with proper formatting
            const encounters = await this.pos.data.searchRead(
                'ths.medical.base.encounter',
                [
                    ['partner_id', '!=', false],
                    ['state', 'in', ['in_progress', 'done']]  // FIXED: Only these two states
                ],
                ['id', 'name', 'encounter_date', 'partner_id', 'patient_ids', 'practitioner_id', 'room_id', 'state'],
                {
                    order: 'encounter_date desc',
                    limit: 50
                }
            );

            console.log("Raw encounters loaded:", encounters);

            // Format the data properly for display - Fix Many2one and Many2many formatting
            this.formattedEncounters = await Promise.all(encounters.map(async (encounter) => {
                console.log(`Formatting encounter ${encounter.name}:`, encounter);

                // Fix partner_id formatting if it's just an ID
                if (encounter.partner_id && typeof encounter.partner_id === 'number') {
                    try {
                        const partners = await this.pos.data.searchRead(
                            'res.partner',
                            [['id', '=', encounter.partner_id]],
                            ['id', 'name']
                        );
                        encounter.partner_id = partners.length > 0 ? [partners[0].id, partners[0].name] : false;
                    } catch (error) {
                        console.error("Error loading partner name:", error);
                        encounter.partner_id = [encounter.partner_id, `Partner #${encounter.partner_id}`];
                    }
                }

                // Fix practitioner_id formatting if it's just an ID
                if (encounter.practitioner_id && typeof encounter.practitioner_id === 'number') {
                    try {
                        const practitioners = await this.pos.data.searchRead(
                            'appointment.resource',
                            [['id', '=', encounter.practitioner_id]],
                            ['id', 'name']
                        );
                        encounter.practitioner_id = practitioners.length > 0 ? [practitioners[0].id, practitioners[0].name] : false;
                    } catch (error) {
                        console.error("Error loading practitioner name:", error);
                        encounter.practitioner_id = [encounter.practitioner_id, `Practitioner #${encounter.practitioner_id}`];
                    }
                }

                // Fix room_id formatting if it's just an ID
                if (encounter.room_id && typeof encounter.room_id === 'number') {
                    try {
                        const rooms = await this.pos.data.searchRead(
                            'appointment.resource',
                            [['id', '=', encounter.room_id]],
                            ['id', 'name']
                        );
                        encounter.room_id = rooms.length > 0 ? [rooms[0].id, rooms[0].name] : false;
                    } catch (error) {
                        console.error("Error loading room name:", error);
                        encounter.room_id = [encounter.room_id, `Room #${encounter.room_id}`];
                    }
                }

                // Fix patient_ids formatting
                let patientNames = [];
                if (encounter.patient_ids && encounter.patient_ids.length > 0) {
                    if (typeof encounter.patient_ids[0] === 'number') {
                        try {
                            const patients = await this.pos.data.searchRead(
                                'res.partner',
                                [['id', 'in', encounter.patient_ids]],
                                ['id', 'name']
                            );
                            patientNames = patients.map(p => [p.id, p.name]);
                        } catch (error) {
                            console.error("Error loading patient names:", error);
                            patientNames = encounter.patient_ids.map(id => [id, `Patient #${id}`]);
                        }
                    } else {
                        patientNames = encounter.patient_ids;
                    }
                }
                encounter.patient_ids = patientNames;

                return encounter;
            }));

            console.log("Formatted encounters:", this.formattedEncounters);
        } catch (error) {
            console.error("Error loading encounters:", error);
            this.formattedEncounters = [];
        }
    },

    async openEncounterSelectionPopup() {
        try {
            console.log("=== OPENING ENCOUNTER SELECTION POPUP ===");

            let encounters = this.formattedEncounters || [];

            if (!encounters || encounters.length === 0) {
                // Fallback: try to load encounters if not already loaded
                await this.loadEncountersForPopup();
                encounters = this.formattedEncounters || [];
            }

            if (!encounters || encounters.length === 0) {
                this.notification.add(_t("No medical encounters found."), { type: 'info' });
                return;
            }

            console.log("Opening popup with encounters:", encounters.length);

            // Open encounter selection popup
            const result = await this.dialog.add(EncounterSelectionPopup, {
                title: _t("Select Medical Encounter"),
                encounters: encounters,
            });

            console.log("Result from encounter selection:", result);

            // Handle the result
            if (result.confirmed && result.payload && result.payload.partner) {
                const partner = result.payload.partner;

                console.log("Setting partner:", partner);

                // Set partner on the current order
                this.pos.get_order().set_partner(partner);

                // Also call the standard partner list method for completeness
                this.clickPartner(partner);

                // Success notification
                this.notification.add(_t("Partner selected from encounter: %s", partner.name), {
                    type: 'success',
                });

                // Add medical context to the order
                const order = this.pos.get_order();
                if (order) {
                    order.medical_context = {
                        encounter_id: result.payload.encounter_id,
                        encounter_name: result.payload.encounter_name,
                        patient_ids: result.payload.patient_ids,
                        practitioner_id: result.payload.practitioner_id,
                        room_id: result.payload.room_id,
                    };

                    console.log("Medical context added to order:", order.medical_context);
                }
            }

        } catch (error) {
            console.error("Error in openEncounterSelectionPopup:", error);
            this.notification.add(_t("Error: %s", error.message), { type: 'danger' });
        }
    },
});