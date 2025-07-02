/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {ControlButtons} from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import {useService} from "@web/core/utils/hooks";
import {useState} from "@odoo/owl";
import {EncounterSelectionPopup} from "@ths_medical_pos/popups/encounter_selection_popup";
import {_t} from "@web/core/l10n/translation";

/**
 * Patch ControlButtons to add encounter search functionality
 * Moves encounter search from partner list to control buttons area
 */
/**
 * Patch ControlButtons to add encounter search functionality
 * Moves encounter search from partner list to control buttons area
 */
patch(ControlButtons.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        // Properly declare component state
        this.state = useState({
            formattedEncounters: []
        });

        // Load encounters on setup
        this.loadEncountersForPopup().catch(error => {
            console.error("Error loading encounters in setup:", error);
        });
    },

    async loadEncountersForPopup() {
        try {
            console.log("Loading encounters from preloaded data...");

            // Get encounters from preloaded data
            const encounters = this.pos.models["ths.medical.base.encounter"].getAll().filter(enc =>
                enc.partner_id && enc.state && ['in_progress', 'done'].includes(enc.state)
            );

            console.log("Raw encounters from preloaded data:", encounters);

            // Format the data for display
            this.state.formattedEncounters = encounters.map(encounter => {
                console.log(`Formatting encounter ${encounter.name}:`, encounter);

                // Create a copy to avoid modifying original data
                const formattedEncounter = {...encounter};

                // patient_ids should already be formatted as [id, name] pairs from patient_name method
                // If not, use the original patient_ids
                formattedEncounter.patient_ids = encounter.patient_ids || [];

                return formattedEncounter;
            });

            console.log("Formatted encounters stored:", this.state.formattedEncounters.length);
        } catch (error) {
            console.error("Error loading encounters:", error);
            this.state.formattedEncounters = [];
        }
    },

    async openEncounterSelectionPopup() {
        try {
            console.log("=== OPENING ENCOUNTER SELECTION FROM CONTROL BUTTONS ===");

            // Always get fresh data from preloaded models
            await this.loadEncountersForPopup();

            if (!this.state.formattedEncounters || this.state.formattedEncounters.length === 0) {
                this.notification.add(_t("No medical encounters found."), {type: 'info'});
                return;
            }

            console.log("Opening popup with encounters:", this.state.formattedEncounters.length);

            const result = await this.dialog.add(EncounterSelectionPopup, {
                title: _t("Select Medical Encounter"),
                encounters: this.state.formattedEncounters,
            });

            console.log("Result from encounter selection:", result);

            if (result.confirmed && result.payload && result.payload.partner) {
                const partner = result.payload.partner;

                console.log("Setting partner:", partner);
                this.pos.get_order().set_partner(partner);

                // Auto-load pending items notification
                const pendingItems = this.pos.getPendingItems(partner.id);
                if (pendingItems.length > 0) {
                    this.notification.add(
                        _t('%d pending items found. Use Pending Items button to add them.', pendingItems.length),
                        {type: 'info'}
                    );
                }

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
            this.notification.add(_t("Error: %s", error.message), {type: 'danger'});
        }
    },
});

console.log("Control buttons patched with encounter search functionality");