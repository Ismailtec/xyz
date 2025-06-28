/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Encounter Selection Popup - Base Medical Module (Odoo 18 OWL 3)
 * Handles encounter selection and partner setting for medical POS orders
 * Uses proper data structure handling to prevent OWL duplicate key errors
 */
export class EncounterSelectionPopup extends Component {
    static template = "ths_medical_pos.EncounterSelectionPopup";
    static props = {
        title: String,
        encounters: Array,
        close: Function,
        onPartnerSelected: { type: Function, optional: true },
    };
    static components = { Dialog };

    setup() {
        this.dialog = useService("dialog");
        this.cancelLabel = _t("Cancel");
        this.notification = useService("notification");
        this.pos = usePos();

        console.log("EncounterSelectionPopup - Encounters received:", this.props.encounters);
        console.log("Sample encounter structure:", this.props.encounters[0]);

        // Debug each encounter structure
        this.props.encounters.forEach((encounter, index) => {
            console.log(`Encounter ${index + 1} (${encounter.name}):`);
            console.log("  ID:", encounter.id);
            console.log("  partner_id:", encounter.partner_id);
            console.log("  patient_ids:", encounter.patient_ids);
            console.log("  practitioner_id:", encounter.practitioner_id);
            console.log("  room_id:", encounter.room_id);
            console.log("  state:", encounter.state);
        });
    }

    /**
     * CRITICAL FIX: Properly format encounters to prevent OWL duplicate key errors
     * Handles the complex Proxy object structure returned from Odoo 18 data models
     */
    get formattedEncounters() {
        return this.props.encounters.map(encounter => {
            // CRITICAL FIX: Handle partner data structure properly
            let partner_name = "No Partner";
            if (encounter.partner_id) {
                if (encounter.partner_id.name) {
                    partner_name = encounter.partner_id.name;
                } else if (Array.isArray(encounter.partner_id) && encounter.partner_id.length >= 2) {
                    partner_name = encounter.partner_id[1];
                } else if (typeof encounter.partner_id === 'object' && encounter.partner_id.id) {
                    partner_name = encounter.partner_id.display_name || encounter.partner_id.name || `Partner #${encounter.partner_id.id}`;
                }
            }

            // CRITICAL FIX: Handle patient_ids data structure to prevent duplicate keys
            let patient_display = [];
            if (encounter.patient_ids && encounter.patient_ids.length > 0) {
                encounter.patient_ids.forEach((patient, index) => {
                    let patient_name = "Unknown Patient";

                    if (patient && patient.name) {
                        // Proxy object with .name property
                        patient_name = patient.name;
                    } else if (Array.isArray(patient) && patient.length >= 2) {
                        // Array format [id, name]
                        patient_name = patient[1];
                    } else if (typeof patient === 'object' && patient.id) {
                        // Object with id property
                        patient_name = patient.display_name || patient.name || `Patient #${patient.id}`;
                    } else if (typeof patient === 'number') {
                        // Just ID number
                        patient_name = `Patient #${patient}`;
                    }

                    // Only add non-empty names to prevent duplicates
                    if (patient_name && patient_name !== "Unknown Patient") {
                        patient_display.push(patient_name);
                    }
                });
            }

            // CRITICAL FIX: Handle practitioner data structure
            let practitioner_name = null;
            if (encounter.practitioner_id) {
                if (encounter.practitioner_id.name) {
                    practitioner_name = encounter.practitioner_id.name;
                } else if (Array.isArray(encounter.practitioner_id) && encounter.practitioner_id.length >= 2) {
                    practitioner_name = encounter.practitioner_id[1];
                } else if (typeof encounter.practitioner_id === 'object' && encounter.practitioner_id.id) {
                    practitioner_name = encounter.practitioner_id.display_name || encounter.practitioner_id.name || `Practitioner #${encounter.practitioner_id.id}`;
                }
            }

            // CRITICAL FIX: Handle room data structure
            let room_name = null;
            if (encounter.room_id) {
                if (encounter.room_id.name) {
                    room_name = encounter.room_id.name;
                } else if (Array.isArray(encounter.room_id) && encounter.room_id.length >= 2) {
                    room_name = encounter.room_id[1];
                } else if (typeof encounter.room_id === 'object' && encounter.room_id.id) {
                    room_name = encounter.room_id.display_name || encounter.room_id.name || `Room #${encounter.room_id.id}`;
                }
            }

            // CRITICAL FIX: Format state display
            const state_display = encounter.state === 'in_progress' ? 'In Progress' :
                                encounter.state === 'done' ? 'Done' :
                                encounter.state ? encounter.state.charAt(0).toUpperCase() + encounter.state.slice(1) : 'Unknown';

            return {
                id: encounter.id,
                name: encounter.name || "Unnamed Encounter",
                encounter_date: encounter.encounter_date || "",
                partner_name: partner_name,
                patient_display: patient_display,
                practitioner_name: practitioner_name,
                room_name: room_name,
                state: encounter.state || "unknown",
                state_display: state_display,
                // Keep original encounter for selection logic
                original_encounter: encounter
            };
        });
    }

    /**
     * CRITICAL FIX: Handle encounter confirmation with proper partner validation
     * Uses the original encounter data for setting the partner
     */
    confirmSelection(formattedEncounter) {
        const encounter = formattedEncounter.original_encounter;
        console.log("confirmSelection called with encounter:", encounter);

        // CRITICAL FIX: Validate partner data structure before setting
        if (!encounter.partner_id) {
            console.log("Invalid partner data:", encounter.partner_id);
            this.notification.add(_t("This encounter has no valid partner assigned."), { type: 'warning' });
            return;
        }

        try {
            let partner_id;

            // CRITICAL FIX: Extract partner ID from various data structures
            if (encounter.partner_id.id) {
                partner_id = encounter.partner_id.id;
            } else if (Array.isArray(encounter.partner_id) && encounter.partner_id.length >= 1) {
                partner_id = encounter.partner_id[0];
            } else if (typeof encounter.partner_id === 'number') {
                partner_id = encounter.partner_id;
            } else {
                throw new Error("Unable to extract partner ID from encounter data");
            }

            console.log("Setting partner with ID:", partner_id);

            // CRITICAL FIX: Use proper partner setting method for Odoo 18 POS
            const partner = this.pos.models['res.partner'].get(partner_id);
            if (partner) {
                this.pos.set_partner(partner);

                // Set encounter context on the current order
                const currentOrder = this.pos.get_order();
                if (currentOrder) {
                    currentOrder.encounter_id = encounter.id;
                    currentOrder.encounter_name = encounter.name;

                    this.notification.add(
                        _t("Partner and encounter selected successfully: %s", partner.name),
                        { type: 'success' }
                    );
                }
            } else {
                throw new Error(`Partner with ID ${partner_id} not found in POS data`);
            }

            // Close popup and trigger callback if provided
            if (this.props.onPartnerSelected) {
                this.props.onPartnerSelected(partner);
            }

            this.props.close();

        } catch (error) {
            console.error("Error setting partner from encounter:", error);
            this.notification.add(
                _t("Failed to set partner from encounter: %s", error.message),
                { type: 'danger' }
            );
        }
    }

    /**
     * Handle popup cancellation
     */
    cancel() {
        this.props.close();
    }
}