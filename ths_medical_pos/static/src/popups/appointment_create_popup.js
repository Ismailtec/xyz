/** @odoo-module */
console.log("Loading: ths_medical_pos/static/src/popups/appointment_create_popup.js");

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { formatDateTime, formatDate } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";

export class AppointmentCreatePopup extends Component {
    static template = "ths_medical_pos.AppointmentCreatePopup";
    static props = {
        title: { type: String, optional: true },
        start: { type: Date, optional: true },
        end: { type: Date, optional: true },
        close: Function,
        confirm: Function,
    };
    static defaultProps = {
        title: _t("New Appointment"),
        start: null,
        end: null,
    };


    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");

        // Use state for form data
        this.state = useState({
             startDate: this.props.start ? new Date(this.props.start) : new Date(),
             endDate: this.props.end ? new Date(this.props.end) : null,
             name: '', // Subject/Name (Required)
             patientId: null, // Pet ID (Required)
             ownerId: null, // Pet Owner ID (Derived)
             practitionerId: null, // Optional
             roomId: null, // Optional
             reason: '', // Optional reason for visit field
             // Selection lists
             availablePatients: [], // Format: { id: 1, name: "Fido (John Doe)" }
             availablePractitioners: [], // Format: { id: 1, name: "Dr. Smith" }
             availableRooms: [], // Format: { id: 1, name: "Room 1" }
             isLoading: true,
        });

        // Calculate default end date
        if (this.props.start && !this.props.end) {
            const defaultDurationMinutes = this.pos.config.appointment_default_duration || 30; // Use POS config or default
            this.state.endDate = new Date(this.state.startDate.getTime() + defaultDurationMinutes * 60000);
        }

        onMounted(async () => {
            await this.loadSelectionData();
            this.state.isLoading = false;
        });
    }

    // Load data, preferring loaded POS data
    async loadSelectionData() {
        this.state.isLoading = true;
        try {
            // 1. Load Pets (Try using POS partner data first)
            const petTypeId = this.pos.db.partner_type_by_ref?.pet?.id; // Assumes types loaded by ref
            if (petTypeId) {
                 // Filter partners loaded in POS
                 this.state.availablePatients = this.pos.partners
                    .filter(p => p.ths_partner_type_id && p.ths_partner_type_id[0] === petTypeId)
                    .map(p => ({ id: p.id, name: p.name + (p.ths_pet_owner_id ? ` (${p.ths_pet_owner_id[1]})` : '') })) // Show owner in name
                    .sort((a, b) => a.name.localeCompare(b.name));
                 console.log("Loaded patients from pos.partners:", this.state.availablePatients.length);
            } else {
                console.warn("Pet Partner Type ID not found in pos.db.partner_type_by_ref. Falling back to RPC for pets.");
                // Fallback RPC (less efficient if many partners)
                const patients = await this.orm.searchRead(
                    'res.partner',
                    [['ths_partner_type_id.name', '=', 'Pet']], // Less reliable than ID
                    ['id', 'display_name', 'ths_pet_owner_id'], // Fetch owner too
                    { context: this.pos.user.context, limit: 500 } // Add limit
                );
                this.state.availablePatients = patients.map(p => ({ id: p.id, name: p.display_name + (p.ths_pet_owner_id ? ` (${p.ths_pet_owner_id[1]})` : '') }));
            }

            // 2. Load Practitioners (Try using POS employee data first)
            this.state.availablePractitioners = this.pos.employees
                .filter(e => e.ths_is_medical && e.resource_id) // Filter based on loaded fields
                .map(e => ({ id: e.id, name: e.name }))
                .sort((a, b) => a.name.localeCompare(b.name));
            console.log("Loaded practitioners from pos.employees:", this.state.availablePractitioners.length);

            // Fallback RPC if needed (if pos.employees doesn't have required fields/domain)
            if (this.state.availablePractitioners.length === 0) {
                 console.warn("No suitable practitioners found in pos.employees. Falling back to RPC.");
                 const practitioners = await this.orm.searchRead(
                    'hr.employee',
                    [['resource_id', '!=', false], ['ths_is_medical', '=', true]],
                    ['id', 'name'],
                    { context: this.pos.user.context, limit: 100 }
                 );
                 this.state.availablePractitioners = practitioners;
            }

            // 3. Load Rooms (RPC is generally fine here unless list is huge/static)
             const rooms = await this.orm.searchRead(
                'ths.treatment.room',
                [['resource_id', '!=', false], ['active', '=', true]],
                ['id', 'name'],
                { context: this.pos.user.context, limit: 100 }
             );
             this.state.availableRooms = rooms.sort((a, b) => a.name.localeCompare(b.name));
             console.log("Loaded rooms via RPC:", this.state.availableRooms.length);

        } catch (error) {
             console.error("Error loading data for appointment popup:", error);
             this.notification.add(_t("Error loading selection data."), { type: 'danger' });
        } finally {
             this.state.isLoading = false;
        }
    }

    // Handle patient selection change to update owner
    onPatientChange(event) {
        const selectedPetId = parseInt(event.target.value);
        this.state.patientId = selectedPetId || null;
        this.state.ownerId = this.getOwnerIdForPet(selectedPetId);
        console.log(`Patient changed to ${selectedPetId}, derived owner: ${this.state.ownerId}`);
    }

    getOwnerIdForPet(petId) {
        if (!petId) return null;
        // Use data loaded into POS for efficiency
        const pet = this.pos.db.get_partner_by_id(petId);
        // Ensure ths_pet_owner_id was loaded by pos_session override
        if (pet && pet.ths_pet_owner_id) {
             return pet.ths_pet_owner_id[0]; // Return owner ID
        } else {
            // Fallback: Could do an RPC here but less efficient
             console.warn(`Owner ID not found directly for Pet ID ${petId} in pos.db`);
             return null;
        }
    }

    formatDateForDisplay(dateObj) {
        return dateObj ? formatDateTime(dateObj) : '';
    }

    // Confirmation / Save Logic
    async confirm() {
        const startTime = this.state.startDate;
        const endTime = this.state.endDate;
        const derivedOwnerId = this.getOwnerIdForPet(this.state.patientId);

        // Validation
        if (!this.state.name) {
            this.notification.add(_t("Appointment name is required."), { type: 'danger' });
            return;
        }
        if (!this.state.patientId) {
            this.notification.add(_t("Please select a patient."), { type: 'danger' });
            return;
        }
         if (!derivedOwnerId) {
             this.notification.add(_t("Could not determine the Pet Owner for the selected Pet."), { type: 'danger' });
             return;
         }
        if (!startTime || !endTime) {
            this.notification.add(_t("Start and end times are required."), { type: 'danger' });
            return;
        }
        if (endTime <= startTime) {
            this.notification.add(_t("End time must be after start time."), { type: 'danger' });
            return;
        }

        // Convert dates to Odoo/Postgres compatible format (UTC String)
        const formatForOdoo = (date) => date.toISOString().slice(0, 19).replace('T', ' ');

        const vals = {
            'name': this.state.name,
            'start': formatForOdoo(startTime),
            'stop': formatForOdoo(endTime),
            'ths_patient_id': this.state.patientId,
            'partner_id': derivedOwnerId, // Set Owner as main partner
            'ths_practitioner_id': this.state.practitionerId ? parseInt(this.state.practitionerId) : false,
            'ths_room_id': this.state.roomId ? parseInt(this.state.roomId) : false,
            'ths_status': 'scheduled',
            'ths_reason_for_visit': this.state.reason || '',
             // Ensure required attendees (patient/owner/provider) are added if needed by backend model
             'partner_ids': [(6, 0, [derivedOwnerId, this.state.patientId])], // Example: Owner and Pet
        };

        // Add provider to attendees if selected
        if (vals.ths_practitioner_id) {
             const providerPartnerId = this.pos.employees.find(e => e.id === vals.ths_practitioner_id)?.partner_id[0];
             if (providerPartnerId && !vals.partner_ids[0][2].includes(providerPartnerId)) {
                  vals.partner_ids[0][2].push(providerPartnerId);
             }
        }

        console.log("Creating calendar event with vals:", vals);

        try {
            this.state.isLoading = true; // Indicate saving
            const newEventId = await this.orm.create('calendar.event', [vals], { context: this.pos.user.context });
            console.log(`Appointment created successfully with ID: ${newEventId}`);
            this.notification.add(_t("Appointment created successfully."), { type: 'success' });
            super.confirm({ created: true, eventId: newEventId }); // Close popup
        } catch (error) {
            console.error("Error creating appointment:", error);
            this.notification.add(_t("Error creating appointment: %(message)s", {message: error.message || error}), { type: 'danger' });
            this.state.isLoading = false; // Re-enable button on error
        }
    }

    cancel() {
        super.cancel();
    }
}

// Register the popup component
registry.category("popups").add("AppointmentCreatePopup", AppointmentCreatePopup);